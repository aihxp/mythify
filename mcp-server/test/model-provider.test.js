import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_MODEL_PROVIDER,
  LOCAL_MODEL_ROLES,
  MODEL_PROVIDER_IDS,
  formatLocalModelRun,
  formatProviderProbe,
  probeOpenAICompatibleProvider,
  runLocalModelRole,
} from "../src/model-provider.js";

test("model provider module exposes stable ids and guarded failures", async () => {
  assert.equal(DEFAULT_MODEL_PROVIDER, "generic-openai-compatible");
  assert.deepEqual(LOCAL_MODEL_ROLES, ["reader", "triage"]);
  assert.ok(MODEL_PROVIDER_IDS.includes("ollama"));

  const missingProvider = await probeOpenAICompatibleProvider({
    provider: DEFAULT_MODEL_PROVIDER,
    base_url: "",
    model: "local-test",
    check: "chat",
  });
  assert.equal(missingProvider.status, "blocked");
  assert.match(missingProvider.error, /requires base_url/);
  assert.match(formatProviderProbe(missingProvider), /Provider probe blocked/);

  const refusedLocalRun = await runLocalModelRole({
    provider: "ollama",
    role: "reader",
    base_url: "https://example.com/v1",
    model: "local-test",
    prompt: "Summarize this.",
  });
  assert.equal(refusedLocalRun.status, "blocked");
  assert.match(refusedLocalRun.error, /requires a localhost/);
  assert.match(formatLocalModelRun(refusedLocalRun), /Local model run blocked/);
});
