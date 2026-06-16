import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  LIFECYCLE_ADAPTER_IDS,
  formatLifecycleProbe,
  lifecycleLaneContract,
  probeLifecycleAdapter,
} from "../src/lifecycle-adapter.js";

test("lifecycle adapter module exposes probe-only contract and missing-binary failure", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "mythify-lifecycle-adapter-"));
  try {
    assert.deepEqual(LIFECYCLE_ADAPTER_IDS, ["google-agents-cli", "google-adk-cli"]);

    const contract = lifecycleLaneContract("google-agents-cli", {});
    assert.equal(contract.version, 1);
    assert.equal(contract.lane, "agent_lifecycle");
    assert.equal(contract.current_policy, "probe_only");
    assert.equal(contract.material_not_evidence, true);
    assert.equal(contract.writes_state, false);
    assert.equal(contract.verification_recorded, false);
    assert.equal(contract.eval_execution_enabled, false);
    assert.equal(contract.deployment_enabled, false);
    assert.ok(contract.required_before_eval_execution.includes("eval_dataset_or_eval_set"));
    assert.ok(contract.required_before_deployment.includes("billing_ack"));

    const missing = probeLifecycleAdapter({
      adapter: "google-agents-cli",
      bin: path.join(root, "missing-agents-cli"),
      timeout_seconds: 1,
    });
    assert.equal(missing.status, "blocked");
    assert.equal(missing.binary_source, "explicit");
    assert.equal(missing.checks.length, 0);
    assert.equal(missing.lifecycle_lane_contract.current_policy, "probe_only");
    assert.match(missing.error, /not executable/);
    assert.match(formatLifecycleProbe(missing), /Lifecycle probe blocked/);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
