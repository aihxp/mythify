import test from "node:test";
import assert from "node:assert/strict";
import {
  ADAPTER_TOOL_NAMES,
  registerAdapterTools,
} from "../src/adapter-tools.js";

test("adapter tool registrar wires stable adapter tool names", async () => {
  const registered = [];
  let storedHostModel = null;
  let cleared = false;
  const server = {
    registerTool(name, config, handler) {
      registered.push({ name, config, handler });
    },
  };

  registerAdapterTools(server, {
    guarded: (handler) => async (args) => handler(args || {}),
    isoNow: () => "2026-06-16T00:00:00.000Z",
    readHostModelState: () => storedHostModel,
    clearHostModelState: () => {
      cleared = true;
      storedHostModel = null;
    },
    writeHostModelState: (record) => {
      storedHostModel = record;
    },
    resolveStateDir: () => "/tmp/mythify-test/.mythify",
  });

  assert.deepEqual(registered.map((entry) => entry.name), ADAPTER_TOOL_NAMES);
  const hostSwitch = registered.find((entry) => entry.name === "host_model_switch");
  assert.ok(hostSwitch.config.inputSchema.target_model);

  const switchResult = await hostSwitch.handler({
    target_model: "gpt-5.4",
    platform: "codex-desktop",
    format: "json",
  });
  assert.match(switchResult, /^\[OK\] /);
  assert.equal(storedHostModel.target_model, "gpt-5.4");
  assert.equal(storedHostModel.platform, "codex-desktop");

  const statusResult = await hostSwitch.handler({ action: "status" });
  assert.match(statusResult, /target model: gpt-5.4/);

  const clearResult = await hostSwitch.handler({ action: "clear", format: "json" });
  assert.match(clearResult, /^\[OK\] /);
  assert.equal(cleared, true);
  assert.equal(storedHostModel, null);
});

test("adapter tool registrar rejects missing required deps", () => {
  assert.throws(
    () => registerAdapterTools({ registerTool() {} }, {}),
    /requires deps\.guarded/
  );
});
