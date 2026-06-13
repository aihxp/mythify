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
  const client = new Client({ name: "mythify-execution-probe-test", version: "2.5.0" });
  await client.connect(transport);
  try {
    await fn(client);
  } finally {
    await client.close();
  }
}

test("execution_probe detects Google Colab CLI without provisioning a runtime", async () => {
  const { root, stateDir, homeDir, binDir } = makeProject("mythify-exec-colab-");
  const logPath = path.join(root, "colab-args.jsonl");
  const colabBin = path.join(binDir, "colab");
  writeStub(
    colabBin,
    [
      "#!/usr/bin/env node",
      'const fs = require("node:fs");',
      `fs.appendFileSync(${JSON.stringify(logPath)}, JSON.stringify(process.argv.slice(2)) + "\\n");`,
      'const args = process.argv.slice(2);',
      'if (args.length === 1 && args[0] === "--version") { console.log("colab 0.1.0"); process.exit(0); }',
      'if (args.length === 1 && args[0] === "--help") { console.log("usage: colab [auth|runtime|run]"); process.exit(0); }',
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
            name: "execution_probe",
            arguments: { adapter: "google-colab-cli", bin: colabBin, format: "json" },
          })
        );
        assert.ok(probedText.startsWith("[OK]"), `execution_probe reports [OK]: ${probedText}`);
        const probed = JSON.parse(probedText.replace(/^\[OK\] /, ""));
        assert.equal(probed.adapter, "google-colab-cli");
        assert.equal(probed.adapter_kind, "execution_substrate");
        assert.equal(probed.status, "available");
        assert.equal(probed.material_not_evidence, true);
        assert.equal(probed.evidence_status, "probe_only_not_verification");
        assert.equal(probed.non_billable, true);
        assert.equal(probed.job_execution_enabled, false);
        assert.equal(probed.can_run_remote_job, false);
        assert.equal(probed.remote_runtime_provisioned, false);
        assert.equal(probed.accelerator_requested, false);
        assert.equal(probed.data_uploaded, false);
        assert.equal(probed.artifact_retrieval_enabled, false);
        assert.equal(probed.billing_guard, "probe_only_no_runtime_provisioning");
        assert.match(probed.feature_evidence, /no remote runtime/);
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

test("execution_probe reports missing binaries without writing verification evidence", async () => {
  const { root, stateDir, homeDir } = makeProject("mythify-exec-missing-");
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
            name: "execution_probe",
            arguments: {
              adapter: "google-colab-cli",
              bin: path.join(root, "missing-colab"),
              format: "json",
            },
          })
        );
        assert.ok(missing.startsWith("[FAIL]"), `execution_probe refuses: ${missing}`);
        const parsed = JSON.parse(missing.replace(/^\[FAIL\] /, ""));
        assert.equal(parsed.adapter, "google-colab-cli");
        assert.equal(parsed.status, "blocked");
        assert.equal(parsed.binary_source, "explicit");
        assert.equal(parsed.material_not_evidence, true);
        assert.equal(parsed.non_billable, true);
        assert.equal(parsed.job_execution_enabled, false);
        assert.equal(parsed.can_run_remote_job, false);
        assert.equal(parsed.checks.length, 0);
        assert.match(parsed.error, /not executable/);
        assert.equal(fs.existsSync(path.join(stateDir, "verifications.jsonl")), false);
      }
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("execution_run refuses before remote work without acknowledgements", async () => {
  const { root, stateDir, homeDir, binDir } = makeProject("mythify-exec-run-refuse-");
  const logPath = path.join(root, "colab-run-args.jsonl");
  const colabBin = path.join(binDir, "colab");
  const scriptPath = path.join(root, "train.py");
  fs.writeFileSync(scriptPath, "print('train')\n", "utf8");
  writeStub(
    colabBin,
    [
      "#!/usr/bin/env node",
      'const fs = require("node:fs");',
      `fs.appendFileSync(${JSON.stringify(logPath)}, JSON.stringify(process.argv.slice(2)) + "\\n");`,
      'console.log("should not run");',
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
        const refused = textOf(
          await client.callTool({
            name: "execution_run",
            arguments: {
              adapter: "google-colab-cli",
              bin: colabBin,
              script_path: scriptPath,
              format: "json",
            },
          })
        );
        assert.ok(refused.startsWith("[FAIL]"), `execution_run refuses: ${refused}`);
        const parsed = JSON.parse(refused.replace(/^\[FAIL\] /, ""));
        assert.equal(parsed.adapter, "google-colab-cli");
        assert.equal(parsed.status, "blocked");
        assert.equal(parsed.job_execution_enabled, true);
        assert.equal(parsed.billing_acknowledged, false);
        assert.equal(parsed.data_movement_acknowledged, false);
        assert.equal(parsed.cleanup_acknowledged, false);
        assert.equal(parsed.remote_runtime_requested, false);
        assert.match(parsed.error, /billing_ack=true/);
        assert.equal(fs.existsSync(logPath), false);
        assert.equal(fs.existsSync(path.join(stateDir, "verifications.jsonl")), false);
      }
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("execution_run can run a fully acknowledged fake Colab ephemeral job", async () => {
  const { root, stateDir, homeDir, binDir } = makeProject("mythify-exec-run-ok-");
  const logPath = path.join(root, "colab-run-args.jsonl");
  const colabBin = path.join(binDir, "colab");
  const scriptPath = path.join(root, "train.py");
  fs.writeFileSync(scriptPath, "print('train')\n", "utf8");
  writeStub(
    colabBin,
    [
      "#!/usr/bin/env node",
      'const fs = require("node:fs");',
      `fs.appendFileSync(${JSON.stringify(logPath)}, JSON.stringify(process.argv.slice(2)) + "\\n");`,
      'const args = process.argv.slice(2);',
      'if (args[0] === "run" && args.includes("--gpu") && args.includes("T4") && !args.includes("--keep")) {',
      '  console.log("remote job complete");',
      "  process.exit(0);",
      "}",
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
        const ranText = textOf(
          await client.callTool({
            name: "execution_run",
            arguments: {
              adapter: "google-colab-cli",
              bin: colabBin,
              script_path: scriptPath,
              accelerator_type: "gpu",
              accelerator: "T4",
              script_args: ["--epochs", "1"],
              billing_ack: true,
              data_movement_ack: true,
              cleanup_ack: true,
              format: "json",
            },
          })
        );
        assert.ok(ranText.startsWith("[OK]"), `execution_run reports [OK]: ${ranText}`);
        const ran = JSON.parse(ranText.replace(/^\[OK\] /, ""));
        assert.equal(ran.adapter, "google-colab-cli");
        assert.equal(ran.status, "succeeded");
        assert.equal(ran.material_not_evidence, true);
        assert.equal(ran.evidence_status, "remote_output_not_verification");
        assert.equal(ran.writes_state, false);
        assert.equal(ran.verification_recorded, false);
        assert.equal(ran.billing_acknowledged, true);
        assert.equal(ran.data_movement_acknowledged, true);
        assert.equal(ran.cleanup_acknowledged, true);
        assert.equal(ran.remote_runtime_requested, true);
        assert.equal(ran.accelerator_requested, true);
        assert.equal(ran.accelerator_type, "gpu");
        assert.equal(ran.accelerator, "T4");
        assert.equal(ran.cleanup_guard, "colab_run_without_keep");
        assert.match(ran.started_at, /T/);
        assert.match(ran.ended_at, /T/);
        assert.match(ran.output_tail, /remote job complete/);

        const logged = fs.readFileSync(logPath, "utf8").trim().split(/\n/).map((line) => JSON.parse(line));
        assert.deepEqual(logged, [["run", "--gpu", "T4", scriptPath, "--epochs", "1"]]);
        assert.equal(fs.existsSync(path.join(stateDir, "verifications.jsonl")), false);
      }
    );
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
