import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const SERVER_PATH = fileURLToPath(new URL("../src/index.js", import.meta.url));

function cleanEnv(extra = {}) {
  const env = { ...process.env };
  for (const key of Object.keys(env)) {
    if (key.startsWith("MYTHIFY_")) {
      delete env[key];
    }
  }
  return { ...env, ...extra };
}

function makeProject(prefix) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  const stateDir = path.join(root, ".mythify");
  const homeDir = path.join(root, "home");
  const binDir = path.join(root, "bin");
  fs.mkdirSync(stateDir, { recursive: true });
  fs.mkdirSync(homeDir, { recursive: true });
  fs.mkdirSync(binDir, { recursive: true });
  return { root, stateDir, homeDir, binDir };
}

function writeStub(filePath, source) {
  fs.writeFileSync(filePath, source, "utf8");
  fs.chmodSync(filePath, 0o755);
}

function textOf(result) {
  assert.ok(Array.isArray(result.content), "tool result has a content array");
  const texts = result.content.filter((c) => c.type === "text").map((c) => c.text);
  assert.ok(texts.length > 0, "tool result has at least one text block");
  return texts.join("\n");
}

async function withClient(env, fn) {
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [SERVER_PATH],
    env,
  });
  const client = new Client({ name: "mythify-host-cli-probe-test", version: "2.5.0" });
  await client.connect(transport);
  try {
    await fn(client);
  } finally {
    await client.close();
  }
}

test("host_cli_probe detects Kimi Code prompt mode without running a prompt", async () => {
  const { root, stateDir, homeDir, binDir } = makeProject("mythify-host-kimi-");
  const logPath = path.join(root, "kimi-args.jsonl");
  const kimiBin = path.join(binDir, "kimi");
  writeStub(
    kimiBin,
    [
      "#!/usr/bin/env node",
      'const fs = require("node:fs");',
      `fs.appendFileSync(${JSON.stringify(logPath)}, JSON.stringify(process.argv.slice(2)) + "\\n");`,
      'const args = process.argv.slice(2);',
      'if (args.length === 1 && args[0] === "--version") { console.log("kimi 0.2.0"); process.exit(0); }',
      'if (args.length === 1 && args[0] === "--help") { console.log("usage: kimi [-p prompt]"); process.exit(0); }',
      'console.error("unexpected args: " + args.join(" "));',
      "process.exit(3);",
      "",
    ].join("\n")
  );
  try {
    await withClient(
      cleanEnv({
        MYTHIFY_DIR: stateDir,
        HOME: homeDir,
      }),
      async (client) => {
        const probedText = textOf(
          await client.callTool({
            name: "host_cli_probe",
            arguments: { host: "kimi-code", bin: kimiBin, format: "json" },
          })
        );
        assert.ok(probedText.startsWith("[OK]"), `host_cli_probe reports [OK]: ${probedText}`);
        const probed = JSON.parse(probedText.replace(/^\[OK\] /, ""));
        assert.equal(probed.host, "kimi-code");
        assert.equal(probed.status, "available");
        assert.equal(probed.material_not_evidence, true);
        assert.equal(probed.evidence_status, "probe_only_not_verification");
        assert.equal(probed.can_run_noninteractive_prompt, true);
        assert.match(probed.feature_evidence, /-p/);
        assert.deepEqual(probed.checks.map((item) => item.args), [["--version"], ["--help"]]);
        assert.equal(fs.existsSync(path.join(stateDir, "verifications.jsonl")), false);

        const logged = fs.readFileSync(logPath, "utf8").trim().split(/\n/).map((line) => JSON.parse(line));
        assert.deepEqual(logged, [["--version"], ["--help"]]);
      }
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("host_cli_probe detects OpenCode run help without starting a worker", async () => {
  const { root, stateDir, homeDir, binDir } = makeProject("mythify-host-opencode-");
  const logPath = path.join(root, "opencode-args.jsonl");
  const opencodeBin = path.join(binDir, "opencode");
  writeStub(
    opencodeBin,
    [
      "#!/usr/bin/env node",
      'const fs = require("node:fs");',
      `fs.appendFileSync(${JSON.stringify(logPath)}, JSON.stringify(process.argv.slice(2)) + "\\n");`,
      'const args = process.argv.slice(2);',
      'if (args.length === 1 && args[0] === "--version") { console.log("opencode 1.15.13"); process.exit(0); }',
      'if (args.length === 2 && args[0] === "run" && args[1] === "--help") { console.log("usage: opencode run [message] --model <model>"); process.exit(0); }',
      'console.error("unexpected args: " + args.join(" "));',
      "process.exit(3);",
      "",
    ].join("\n")
  );
  try {
    await withClient(
      cleanEnv({
        MYTHIFY_DIR: stateDir,
        HOME: homeDir,
      }),
      async (client) => {
        const probedText = textOf(
          await client.callTool({
            name: "host_cli_probe",
            arguments: { host: "opencode", bin: opencodeBin, format: "json" },
          })
        );
        assert.ok(probedText.startsWith("[OK]"), `host_cli_probe reports [OK]: ${probedText}`);
        const probed = JSON.parse(probedText.replace(/^\[OK\] /, ""));
        assert.equal(probed.host, "opencode");
        assert.equal(probed.status, "available");
        assert.equal(probed.material_not_evidence, true);
        assert.equal(probed.can_run_noninteractive_prompt, true);
        assert.equal(probed.feature_evidence, "run --help succeeded");
        assert.deepEqual(probed.checks.map((item) => item.args), [["--version"], ["run", "--help"]]);
        assert.equal(fs.existsSync(path.join(stateDir, "verifications.jsonl")), false);

        const logged = fs.readFileSync(logPath, "utf8").trim().split(/\n/).map((line) => JSON.parse(line));
        assert.deepEqual(logged, [["--version"], ["run", "--help"]]);
      }
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("host_cli_probe reports missing binaries without writing verification evidence", async () => {
  const { root, stateDir, homeDir } = makeProject("mythify-host-missing-");
  try {
    await withClient(
      cleanEnv({
        MYTHIFY_DIR: stateDir,
        HOME: homeDir,
        PATH: "/usr/bin:/bin",
      }),
      async (client) => {
        const missing = textOf(
          await client.callTool({
            name: "host_cli_probe",
            arguments: {
              host: "kimi-code",
              bin: path.join(root, "missing-kimi"),
              format: "json",
            },
          })
        );
        assert.ok(missing.startsWith("[FAIL]"), `host_cli_probe refuses: ${missing}`);
        const parsed = JSON.parse(missing.replace(/^\[FAIL\] /, ""));
        assert.equal(parsed.host, "kimi-code");
        assert.equal(parsed.status, "blocked");
        assert.equal(parsed.binary_source, "explicit");
        assert.equal(parsed.material_not_evidence, true);
        assert.equal(parsed.checks.length, 0);
        assert.match(parsed.error, /not executable/);
        assert.equal(fs.existsSync(path.join(stateDir, "verifications.jsonl")), false);
      }
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
