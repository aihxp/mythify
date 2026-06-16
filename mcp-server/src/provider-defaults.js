import {
  ADAPTER_CANDIDATES,
  ADAPTER_INTERFACE_FIELDS,
  ADAPTER_INTERFACE_LANES,
  ADAPTER_INTERFACE_VERSION,
  HOSTED_PROVIDER_FANOUT_ENGINES,
  HOSTED_PROVIDER_REQUIRED_ACKS,
  ROLE_PROVIDER_ALLOWED,
  ROLE_PROVIDER_DEFAULTS,
  ROLE_PROVIDER_ENV_NAMES,
  ROLE_PROVIDER_FALLBACK_POLICY,
  ROLE_PROVIDER_PROFILES,
  ROLE_COST_METADATA_FIELDS,
  ROLE_TIMEOUT_DEFAULTS,
  ROLE_TIMEOUT_METADATA_FIELDS,
  buildAdapterInterfaceCatalog,
} from "./capability-registry.js";

const ROLE_PROVIDER_ORDER = [
  "session",
  "triage",
  "reader",
  "fanout_worker",
  "reviewer",
  "verifier",
];
const ROLE_ASSIGNMENT_VERSION = 1;
const ROLE_ASSIGNMENT_ADAPTER_LANES = {
  session: ["host"],
  triage: ["host", "model_provider", "custom_adapter"],
  reader: ["host", "model_provider"],
  fanout_worker: ["host", "api_provider", "custom_adapter"],
  reviewer: ["host", "api_provider", "custom_adapter"],
  verifier: [],
};
const ROLE_ASSIGNMENT_EXTRA_ROLES = {
  remote_execution: {
    status: "metadata_supported",
    default_provider: null,
    selected_provider: null,
    provider_source: "not_enabled",
    allowed_providers: [],
    eligible_adapter_lanes: ["execution_substrate"],
    adapter_interface_role: "remote_execution",
    assignment_order: ["future_explicit_role_input", "built_in_disabled"],
    fallback_policy: ROLE_PROVIDER_FALLBACK_POLICY,
    execution_policy: "guarded_explicit_acknowledgement_only",
    runtime_routing_changed: false,
    writes_state_allowed: false,
    material_not_evidence_required: true,
    required_evidence_status: "remote_output_not_verification",
    required_acknowledgements: [
      "billing_ack_required",
      "data_movement_ack_required",
      "cleanup_ack_required",
    ],
    guardrails: [
      ROLE_PROVIDER_FALLBACK_POLICY,
      "explicit_acknowledgements_required",
      "material_not_verification",
      "no_mythify_state_write",
    ],
  },
  agent_lifecycle: {
    status: "metadata_supported",
    default_provider: null,
    selected_provider: null,
    provider_source: "not_enabled",
    allowed_providers: [],
    eligible_adapter_lanes: ["agent_lifecycle"],
    adapter_interface_role: "agent_lifecycle",
    assignment_order: ["future_explicit_role_input", "built_in_disabled"],
    fallback_policy: ROLE_PROVIDER_FALLBACK_POLICY,
    execution_policy: "probe_only_no_eval_or_deploy",
    runtime_routing_changed: false,
    writes_state_allowed: false,
    material_not_evidence_required: true,
    required_evidence_status: "lifecycle_probe_output_not_verification",
    guardrails: [
      ROLE_PROVIDER_FALLBACK_POLICY,
      "probe_only",
      "no_eval_execution",
      "no_deploy",
      "no_publish",
      "no_cloud_mutation",
      "no_mythify_state_write",
      "material_not_verification",
    ],
  },
};

function resolveRoleProvider(role) {
  const defaultProvider = ROLE_PROVIDER_DEFAULTS[role];
  const allowed = ROLE_PROVIDER_ALLOWED[role] || [];
  const envName = ROLE_PROVIDER_ENV_NAMES[role];
  const requested = (process.env[envName] || "").trim();
  let provider = defaultProvider;
  let source = "built_in";
  let status = "selected";
  if (requested !== "") {
    if (allowed.includes(requested)) {
      provider = requested;
      source = `env:${envName}`;
    } else {
      status = "invalid_env_ignored";
    }
  }
  return {
    role,
    provider,
    provider_source: source,
    default_provider: defaultProvider,
    allowed_providers: allowed,
    requested_provider: requested || null,
    status,
    fallback_policy: ROLE_PROVIDER_FALLBACK_POLICY,
    provider_profile: ROLE_PROVIDER_PROFILES[provider] || {},
    selection: "advisory_metadata_only",
  };
}

export function roleProviderCatalog() {
  const catalog = {};
  for (const [provider, profile] of Object.entries(ROLE_PROVIDER_PROFILES).sort(([left], [right]) =>
    left.localeCompare(right)
  )) {
    catalog[provider] = {
      ...profile,
      fallback_policy: profile.fallback_policy || ROLE_PROVIDER_FALLBACK_POLICY,
    };
  }
  return catalog;
}

export function apiProviderContract() {
  const providers = {};
  for (const [name, candidate] of Object.entries(ADAPTER_CANDIDATES).sort(([left], [right]) =>
    left.localeCompare(right)
  )) {
    if (candidate.kind !== "api_provider") {
      continue;
    }
    providers[name] = {
      status: candidate.status,
      protocol: candidate.protocol || "unknown",
      openai_compatible: Boolean(candidate.openai_compatible),
      default_base_url: candidate.default_base_url || "",
      base_url_env: candidate.base_url_env || "",
      api_key_env: candidate.api_key_env || "",
      model_env: candidate.model_env || "",
      auth_header: candidate.auth_header || "",
      version_header: candidate.version_header || "",
      billing: candidate.billing || "unknown",
      explicit_enable_required: candidate.explicit_enable_required === true,
      execution_enabled: candidate.can_run_api_worker === true,
      default_timeout_seconds: candidate.default_timeout_seconds || 600,
      cost_metadata_supported: candidate.cost_metadata_supported === true,
      pricing_url: candidate.pricing_url || "",
      pricing_url_env: candidate.pricing_url_env || "",
      fallback_policy: candidate.fallback_policy || ROLE_PROVIDER_FALLBACK_POLICY,
    };
  }
  return {
    version: 1,
    status: "metadata_supported",
    execution_enabled: false,
    fanout_execution_enabled: true,
    fanout_engines: HOSTED_PROVIDER_FANOUT_ENGINES,
    required_fanout_acknowledgements: HOSTED_PROVIDER_REQUIRED_ACKS,
    fanout_audit_log: ".mythify/provider-audit.jsonl",
    fanout_output_material_status: "material_not_verification",
    billing_policy: "explicit_provider_required",
    fallback_policy: ROLE_PROVIDER_FALLBACK_POLICY,
    timeout_metadata_fields: ["provider", "timeout_seconds", "timeout_source"],
    cost_metadata_fields: [
      "provider",
      "model",
      "input_tokens",
      "cached_input_tokens",
      "output_tokens",
      "pricing_url",
    ],
    providers,
  };
}

function customAdapterContract() {
  const command = ADAPTER_CANDIDATES["custom-command"] || {};
  const http = ADAPTER_CANDIDATES["custom-http"] || {};
  return {
    version: 1,
    status: "metadata_supported",
    fallback_policy: ROLE_PROVIDER_FALLBACK_POLICY,
    execution_policy: "explicit_only_no_hidden_fallback",
    evidence_status: "adapter_output_not_verification",
    command: {
      adapter: "custom-command",
      status: command.status || "bounded_execution_supported",
      execution_enabled: command.execution_enabled === true,
      tools: ["classify_task triage_engine=command", "fanout_start engine=command"],
      command_env: command.command_env || ["MYTHIFY_TRIAGE_COMMAND", "MYTHIFY_FANOUT_COMMAND"],
      input_contract: command.input_contract || "prompt_on_stdin",
      default_timeout_seconds: {
        triage: ROLE_TIMEOUT_DEFAULTS.triage.timeout_seconds,
        fanout_worker: ROLE_TIMEOUT_DEFAULTS.fanout_worker.timeout_seconds,
        reviewer: ROLE_TIMEOUT_DEFAULTS.reviewer.timeout_seconds,
      },
      billing: command.billing || "user_defined",
      writes_state: command.writes_state === true,
      output_is_evidence: command.output_is_evidence === true,
      evidence_status: command.evidence_status || "command_output_not_verification",
    },
    http: {
      adapter: "custom-http",
      status: http.status || "metadata_only",
      execution_enabled: http.execution_enabled === true,
      explicit_enable_required: http.explicit_enable_required === true,
      base_url_env: http.base_url_env || "MYTHIFY_CUSTOM_HTTP_BASE_URL",
      api_key_env: http.api_key_env || "MYTHIFY_CUSTOM_HTTP_API_KEY",
      model_env: http.model_env || "MYTHIFY_CUSTOM_HTTP_MODEL",
      pricing_url_env: http.pricing_url_env || "MYTHIFY_CUSTOM_HTTP_PRICING_URL",
      required_before_execution: [
        "method_allowlist",
        "auth_from_env_only",
        "bounded_timeout",
        "request_body_template",
        "response_extraction",
        "cost_metadata",
        "no_state_write",
        "material_not_evidence",
      ],
      billing: http.billing || "metered_external_account_or_user_defined",
      writes_state: http.writes_state === true,
      output_is_evidence: http.output_is_evidence === true,
      evidence_status: http.evidence_status || "http_output_not_verification",
    },
  };
}

function adapterInterfaceContract() {
  return {
    version: ADAPTER_INTERFACE_VERSION,
    status: "metadata_supported",
    fields: ADAPTER_INTERFACE_FIELDS,
    lanes: ADAPTER_INTERFACE_LANES,
    fallback_policy: ROLE_PROVIDER_FALLBACK_POLICY,
    execution_policy: "metadata_shape_only_no_runtime_change",
    guardrail: "interface_does_not_enable_fallback_or_state_writes",
    candidates: buildAdapterInterfaceCatalog(),
  };
}

function roleAssignmentCandidateGroups(adapterRole, lanes, catalog) {
  const eligible = [];
  const executionEnabled = [];
  const metadataOnly = [];
  for (const [id, candidate] of Object.entries(catalog)) {
    if (!lanes.includes(candidate.kind) || !(candidate.roles || []).includes(adapterRole)) {
      continue;
    }
    eligible.push(id);
    if (candidate.execution_enabled === true) {
      executionEnabled.push(id);
    } else {
      metadataOnly.push(id);
    }
  }
  return {
    eligible_candidate_ids: eligible,
    execution_enabled_candidate_ids: executionEnabled,
    metadata_only_candidate_ids: metadataOnly,
  };
}

function roleAssignmentCoreContract(role, resolvedRole, catalog) {
  const profile = resolvedRole.provider_profile || ROLE_PROVIDER_PROFILES[resolvedRole.provider] || {};
  const evidenceStatus = profile.evidence_status || "unknown";
  const guardrails = [
    ROLE_PROVIDER_FALLBACK_POLICY,
    "advisory_metadata_only",
    "no_hidden_provider_fallback",
  ];
  if (evidenceStatus !== "executed_verification") {
    guardrails.push("material_not_verification");
  }
  if (role === "reviewer") {
    guardrails.push("stronger_model_requires_explicit_opt_in");
  }
  const record = {
    role,
    status: "metadata_supported",
    default_provider: resolvedRole.default_provider,
    selected_provider: resolvedRole.provider,
    provider_source: resolvedRole.provider_source,
    allowed_providers: resolvedRole.allowed_providers,
    eligible_adapter_lanes: ROLE_ASSIGNMENT_ADAPTER_LANES[role],
    adapter_interface_role: role === "session" ? "host_session" : role,
    assignment_order: ["future_explicit_role_input", "env", "built_in"],
    fallback_policy: ROLE_PROVIDER_FALLBACK_POLICY,
    execution_policy: "advisory_metadata_only_no_runtime_routing",
    runtime_routing_changed: false,
    writes_state_allowed: profile.writes_state === true,
    material_not_evidence_required: evidenceStatus !== "executed_verification",
    required_evidence_status: evidenceStatus,
    guardrails,
  };
  if (role === "reviewer") {
    record.stronger_model_policy = "explicit_opt_in_required";
  }
  return {
    ...record,
    ...roleAssignmentCandidateGroups(record.adapter_interface_role, record.eligible_adapter_lanes, catalog),
  };
}

function roleAssignmentExtraContract(record, catalog) {
  return {
    ...record,
    allowed_providers: [...record.allowed_providers],
    eligible_adapter_lanes: [...record.eligible_adapter_lanes],
    assignment_order: [...record.assignment_order],
    required_acknowledgements: record.required_acknowledgements
      ? [...record.required_acknowledgements]
      : undefined,
    guardrails: [...record.guardrails],
    ...roleAssignmentCandidateGroups(record.adapter_interface_role, record.eligible_adapter_lanes, catalog),
  };
}

function roleAssignmentContract(resolvedRoles) {
  const catalog = buildAdapterInterfaceCatalog();
  const roles = {};
  for (const role of ROLE_PROVIDER_ORDER) {
    roles[role] = roleAssignmentCoreContract(role, resolvedRoles[role], catalog);
  }
  for (const [role, record] of Object.entries(ROLE_ASSIGNMENT_EXTRA_ROLES)) {
    roles[role] = roleAssignmentExtraContract(record, catalog);
  }
  return {
    version: ROLE_ASSIGNMENT_VERSION,
    status: "metadata_supported",
    source: "adapter_interface_contract",
    assignment_order: ["future_explicit_role_input", "env", "built_in"],
    fallback_policy: ROLE_PROVIDER_FALLBACK_POLICY,
    execution_policy: "metadata_shape_only_no_runtime_change",
    runtime_routing_changed: false,
    guardrail: "role_contract_does_not_enable_hidden_fallback",
    candidate_id_source: "mcp_adapter_interface_catalog",
    roles,
  };
}

export function buildProviderDefaults() {
  const roles = {};
  for (const role of ROLE_PROVIDER_ORDER) {
    roles[role] = resolveRoleProvider(role);
  }
  return {
    version: 1,
    precedence: ["future_explicit_role_input", "env", "built_in"],
    fallback_policy: ROLE_PROVIDER_FALLBACK_POLICY,
    timeout_metadata_fields: ROLE_TIMEOUT_METADATA_FIELDS,
    cost_metadata_fields: ROLE_COST_METADATA_FIELDS,
    provider_catalog: roleProviderCatalog(),
    adapter_interface_contract: adapterInterfaceContract(),
    role_assignment_contract: roleAssignmentContract(roles),
    api_provider_contract: apiProviderContract(),
    custom_adapter_contract: customAdapterContract(),
    roles,
  };
}

export function roleProviderFields(providerDefaults, role) {
  const provider = providerDefaults.roles[role];
  return {
    provider: provider.provider,
    provider_source: provider.provider_source,
    provider_default: provider.default_provider,
    provider_status: provider.status,
    provider_fallback_policy: provider.fallback_policy,
    provider_profile: provider.provider_profile || {},
  };
}

function roleTimeoutMetadata(role, timeoutSeconds, timeoutSource) {
  const metadata = { ...(ROLE_TIMEOUT_DEFAULTS[role] || {}) };
  if (timeoutSeconds !== undefined) {
    metadata.timeout_seconds = timeoutSeconds;
  }
  if (timeoutSource !== undefined) {
    metadata.timeout_source = timeoutSource;
  }
  return metadata;
}

function roleCostMetadata(providerDefaults, role, pricingUrl = "") {
  const providerRecord = providerDefaults.roles[role];
  const provider = providerRecord.provider;
  const profile = providerRecord.provider_profile || {};
  return {
    billing: profile.billing || "unknown",
    cost_estimate_supported: false,
    cost_estimate_status: "not_estimated",
    cost_estimate_cents: null,
    pricing_url: pricingUrl,
    usage_metadata_fields: provider === "api_provider" ? apiProviderContract().cost_metadata_fields : [],
  };
}

export function roleBudgetFields(providerDefaults, role, timeoutSeconds, timeoutSource, pricingUrl = "") {
  return {
    timeout: roleTimeoutMetadata(role, timeoutSeconds, timeoutSource),
    cost: roleCostMetadata(providerDefaults, role, pricingUrl),
  };
}
