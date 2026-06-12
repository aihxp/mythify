"""Interoperability test: the Python CLI and the Node MCP server share state.

Stdlib only. Skips (unittest skip, not failure) unless node is on PATH and
mcp-server/node_modules exists. Flow:

1. Temp project dir and temp HOME. Via the CLI: init, plan create "Interop
   goal" with one step, memory set color blue.
2. Spawn node mcp-server/src/index.js with MYTHIFY_DIR pointing at the
   project's .mythify. Speak newline-delimited JSON-RPC 2.0 over stdio:
   initialize (accepting whatever protocolVersion the server negotiates),
   notifications/initialized, then tools/call:
   - plan_status result text contains "Interop goal".
   - memory_recall with query "blue" finds the key color.
   - memory_store writes key from_mcp.
3. Terminate the server. Via the CLI: memory get from_mcp finds the entry.
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "scripts" / "mythify.py"
SERVER = REPO_ROOT / "mcp-server" / "src" / "index.js"
NODE_MODULES = REPO_ROOT / "mcp-server" / "node_modules"
NODE = shutil.which("node")

RESPONSE_TIMEOUT_SECONDS = 30


class McpStdioClient:
    """Minimal newline-delimited JSON-RPC 2.0 client for an MCP stdio server."""

    def __init__(self, command, env, cwd):
        self.process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.next_id = 1
        self.messages = queue.Queue()
        self.stderr_lines = []
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self):
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self.messages.put(json.loads(line))
            except ValueError:
                self.stderr_lines.append("non-JSON stdout line: " + line)

    def _read_stderr(self):
        for line in self.process.stderr:
            self.stderr_lines.append(line.rstrip("\n"))

    def _send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def notify(self, method, params=None):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def request(self, method, params=None):
        request_id = self.next_id
        self.next_id += 1
        message = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)
        return self._wait_for(request_id)

    def _wait_for(self, request_id):
        while True:
            try:
                message = self.messages.get(timeout=RESPONSE_TIMEOUT_SECONDS)
            except queue.Empty:
                raise AssertionError(
                    "No JSON-RPC response for id {0} within {1}s. "
                    "Server stderr:\n{2}".format(
                        request_id,
                        RESPONSE_TIMEOUT_SECONDS,
                        "\n".join(self.stderr_lines),
                    )
                )
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise AssertionError(
                    "JSON-RPC error for id {0}: {1}".format(
                        request_id, json.dumps(message["error"])
                    )
                )
            return message.get("result")

    def close(self):
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        for stream in (self.process.stdout, self.process.stderr):
            try:
                stream.close()
            except OSError:
                pass


@unittest.skipUnless(NODE, "node is not on PATH")
@unittest.skipUnless(
    NODE_MODULES.is_dir(),
    "mcp-server/node_modules does not exist; run npm install inside mcp-server/",
)
class TestCliMcpInterop(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="mythify-interop-proj-"))
        self.home = Path(tempfile.mkdtemp(prefix="mythify-interop-home-"))
        self.addCleanup(shutil.rmtree, str(self.project), True)
        self.addCleanup(shutil.rmtree, str(self.home), True)

    def run_cli(self, *args):
        env = dict(os.environ)
        env.pop("MYTHIFY_DIR", None)
        env["HOME"] = str(self.home)
        return subprocess.run(
            [sys.executable, str(CLI)] + list(args),
            cwd=str(self.project),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def tool_text(self, result):
        self.assertIsInstance(result, dict, "tools/call returns a result object")
        content = result.get("content")
        self.assertIsInstance(content, list, "tool result has a content array")
        texts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        self.assertTrue(texts, "tool result has at least one text block")
        return "\n".join(texts)

    def test_cli_and_mcp_server_share_one_state_directory(self):
        # 1. Seed state through the CLI.
        init = self.run_cli("init")
        self.assertEqual(init.returncode, 0, init.stderr)
        steps = json.dumps([{"title": "A", "success_criteria": "x"}])
        plan = self.run_cli("plan", "create", "Interop goal", "--steps", steps)
        self.assertEqual(plan.returncode, 0, plan.stderr)
        memory = self.run_cli("memory", "set", "color", "blue")
        self.assertEqual(memory.returncode, 0, memory.stderr)

        # 2. Read and write the same state through the MCP server.
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["MYTHIFY_DIR"] = str(self.project / ".mythify")
        client = McpStdioClient([NODE, str(SERVER)], env=env, cwd=self.project)
        try:
            init_result = client.request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "mythify-interop-test",
                        "version": "2.0.0",
                    },
                },
            )
            # Accept whatever protocolVersion the server negotiates.
            self.assertIn("protocolVersion", init_result)
            client.notify("notifications/initialized")

            status_text = self.tool_text(
                client.request(
                    "tools/call", {"name": "plan_status", "arguments": {}}
                )
            )
            self.assertIn("Interop goal", status_text)

            recall_text = self.tool_text(
                client.request(
                    "tools/call",
                    {"name": "memory_recall", "arguments": {"query": "blue"}},
                )
            )
            self.assertIn("color", recall_text)

            store_text = self.tool_text(
                client.request(
                    "tools/call",
                    {
                        "name": "memory_store",
                        "arguments": {
                            "key": "from_mcp",
                            "value": "written by the MCP server",
                        },
                    },
                )
            )
            self.assertIn("[OK]", store_text)
        finally:
            client.close()

        # 3. Read the server's write back through the CLI.
        got = self.run_cli("memory", "get", "from_mcp")
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertIn("from_mcp", got.stdout)
        self.assertIn("written by the MCP server", got.stdout)


if __name__ == "__main__":
    unittest.main()
