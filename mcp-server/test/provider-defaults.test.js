import { test } from "node:test";
import assert from "node:assert/strict";
import {
  apiProviderContract,
  buildProviderDefaults,
  roleBudgetFields,
  roleProviderCatalog,
  roleProviderFields,
} from "../src/provider-defaults.js";

function withEnv(updates, fn) {
  const previous = {};
  for (const key of Object.keys(updates)) {
    previous[key] = process.env[key];
    if (updates[key] === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = updates[key];
    }
  }
  try {
    fn();
  } finally {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  }
}

test("provider defaults expose role metadata and adapter contracts directly", () => {
  withEnv({ MYTHIFY_ROLE_TRIAGE_PROVIDER: "command" }, () => {
    const defaults = buildProviderDefaults();

    assert.equal(defaults.version, 1);
    assert.equal(defaults.roles.session.provider, "host");
    assert.equal(defaults.roles.triage.provider, "command");
    assert.equal(defaults.roles.triage.provider_source, "env:MYTHIFY_ROLE_TRIAGE_PROVIDER");
    assert.equal(defaults.roles.verifier.provider_profile.evidence_status, "executed_verification");

    assert.equal(roleProviderCatalog().local_command.evidence_status, "executed_verification");
    assert.equal(roleProviderFields(defaults, "reader").provider, "local_openai_compatible");

    const triageBudget = roleBudgetFields(defaults, "triage", 42, "explicit_test");
    assert.equal(triageBudget.timeout.timeout_seconds, 42);
    assert.equal(triageBudget.timeout.timeout_source, "explicit_test");
    assert.equal(triageBudget.cost.billing, "user_defined");

    assert.equal(defaults.adapter_interface_contract.version, 1);
    assert.ok(defaults.adapter_interface_contract.lanes.includes("agent_lifecycle"));
    assert.equal(
      defaults.adapter_interface_contract.candidates["google-colab-cli"].kind,
      "execution_substrate"
    );

    assert.equal(defaults.role_assignment_contract.roles.remote_execution.runtime_routing_changed, false);
    assert.ok(
      defaults.role_assignment_contract.roles.remote_execution.execution_enabled_candidate_ids.includes(
        "google-colab-cli"
      )
    );
    assert.ok(
      defaults.role_assignment_contract.roles.agent_lifecycle.metadata_only_candidate_ids.includes(
        "google-agents-cli"
      )
    );

    assert.equal(defaults.api_provider_contract.providers["openai-api"].api_key_env, "OPENAI_API_KEY");
    assert.equal(defaults.custom_adapter_contract.command.input_contract, "prompt_on_stdin");
  });
});

test("api provider contract exposes hosted provider guardrails", () => {
  const contract = apiProviderContract();
  assert.equal(contract.execution_enabled, false);
  assert.equal(contract.fanout_execution_enabled, true);
  assert.deepEqual(contract.fanout_engines, ["anthropic", "openai"]);
  assert.ok(contract.required_fanout_acknowledgements.includes("hosted_provider_billing_ack"));
  assert.equal(contract.providers["anthropic-api"].auth_header, "x-api-key");
  assert.equal(contract.providers["openai-compatible-hosted"].openai_compatible, true);
});
