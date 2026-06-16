import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  COLAB_GPU_ACCELERATORS,
  COLAB_TPU_ACCELERATORS,
  EXECUTION_ADAPTER_IDS,
  formatExecutionProbe,
  formatExecutionRun,
  probeExecutionAdapter,
  runExecutionAdapter,
} from "../src/execution-adapter.js";

test("execution adapter module exposes stable ids and guarded failures", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "mythify-execution-module-"));
  const scriptPath = path.join(root, "train.py");
  fs.writeFileSync(scriptPath, "print('train')\n", "utf8");
  try {
    assert.deepEqual(EXECUTION_ADAPTER_IDS, ["google-colab-cli"]);
    assert.ok(COLAB_GPU_ACCELERATORS.includes("T4"));
    assert.ok(COLAB_TPU_ACCELERATORS.includes("v5e1"));

    const missingProbe = probeExecutionAdapter({
      adapter: "google-colab-cli",
      bin: path.join(root, "missing-colab"),
      timeout_seconds: 1,
    });
    assert.equal(missingProbe.status, "blocked");
    assert.match(missingProbe.error, /not executable/);
    assert.match(formatExecutionProbe(missingProbe), /Execution probe blocked/);

    const refusedRun = runExecutionAdapter({
      adapter: "google-colab-cli",
      bin: "",
      script_path: scriptPath,
      default_cwd: root,
      accelerator_type: "cpu",
    });
    assert.equal(refusedRun.status, "blocked");
    assert.match(refusedRun.error, /billing_ack=true/);
    assert.match(formatExecutionRun(refusedRun), /Execution run blocked/);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
