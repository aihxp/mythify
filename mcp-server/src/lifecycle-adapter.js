import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { ADAPTER_CANDIDATES } from "./capability-registry.js";

function tailText(text, limit = 4000) {
  const value = String(text || "");
  if (value.length <= limit) {
    return value;
  }
  return value.slice(value.length - limit);
}

function envValue(name) {
  return (process.env[name] || "").trim();
}

function isExecutableFile(filePath) {
  try {
    fs.accessSync(filePath, fs.constants.X_OK);
    return fs.statSync(filePath).isFile();
  } catch {
    return false;
  }
}

function findExecutableOnPath(binaryName) {
  const pathValue = process.env.PATH || "";
  for (const entry of pathValue.split(path.delimiter)) {
    if (!entry) {
      continue;
    }
    const candidate = path.join(entry, binaryName);
    if (isExecutableFile(candidate)) {
      return candidate;
    }
  }
  return null;
}

function runCliProbeCommand(bin, args, timeoutSeconds) {
  const startedAt = process.hrtime.bigint();
  const run = spawnSync(bin, args, {
    shell: false,
    encoding: "utf8",
    timeout: Math.round(timeoutSeconds * 1000),
    maxBuffer: 1024 * 1024,
  });
  const durationSeconds = Number(process.hrtime.bigint() - startedAt) / 1e9;
  const timedOut = Boolean(run.error && run.error.code === "ETIMEDOUT");
  const exitCode = typeof run.status === "number" ? run.status : -1;
  let error = "";
  if (timedOut) {
    error = `timed out after ${timeoutSeconds} seconds`;
  } else if (exitCode !== 0) {
    error = tailText(run.stderr) || `command exited ${exitCode}`;
  } else if (run.error) {
    error = run.error.message;
  }
  return {
    command: [path.basename(bin), ...args].join(" "),
    args,
    ok: exitCode === 0,
    exit_code: exitCode,
    duration_seconds: Number(durationSeconds.toFixed(3)),
    stdout_tail: tailText(run.stdout, 2000),
    stderr_tail: tailText(run.stderr, 2000),
    error,
    timed_out: timedOut,
  };
}

export const LIFECYCLE_ADAPTER_IDS = ["google-agents-cli", "google-adk-cli"];

const LIFECYCLE_PROBES = {
  "google-agents-cli": {
    envName: "MYTHIFY_AGENTS_CLI_BIN",
    binaryNames: ["agents-cli"],
    fallbacks: [
      path.join(os.homedir(), ".local", "bin", "agents-cli"),
      "/opt/homebrew/bin/agents-cli",
      "/usr/local/bin/agents-cli",
    ],
    checks: [
      { name: "version", args: ["--version"] },
      { name: "help", args: ["--help"] },
      { name: "eval_help", args: ["eval", "--help"] },
    ],
  },
  "google-adk-cli": {
    envName: "MYTHIFY_ADK_BIN",
    binaryNames: ["adk"],
    fallbacks: [
      path.join(os.homedir(), ".local", "bin", "adk"),
      "/opt/homebrew/bin/adk",
      "/usr/local/bin/adk",
    ],
    checks: [
      { name: "version", args: ["--version"] },
      { name: "help", args: ["--help"] },
      { name: "eval_help", args: ["eval", "--help"] },
    ],
  },
};

const LIFECYCLE_CONTRACT_VERSION = 1;
const LIFECYCLE_REQUIRED_BEFORE_EVAL_EXECUTION = [
  "explicit_user_request",
  "agent_project_path",
  "eval_dataset_or_eval_set",
  "bounded_timeout",
  "credential_source_summary",
  "project_mutation_ack",
  "material_not_verification",
  "artifact_or_report_path",
];
const LIFECYCLE_REQUIRED_BEFORE_DEPLOYMENT = [
  "explicit_user_request",
  "target_platform",
  "project_id",
  "region",
  "billing_ack",
  "data_movement_ack",
  "cloud_mutation_ack",
  "rollback_or_teardown_posture",
  "material_not_verification",
];

export function lifecycleLaneContract(adapter, adapterInfo = {}) {
  const commonDisabledActions = [
    "project_scaffold",
    "project_create",
    "agent_run",
    "eval_execution",
    "deployment",
    "publishing",
    "cloud_mutation",
    "project_mutation",
  ];
  const adapterDisabledActions = adapterInfo.lifecycle_disabled_actions || [];
  return {
    version: LIFECYCLE_CONTRACT_VERSION,
    adapter,
    lane: "agent_lifecycle",
    status: adapterInfo.status || "probe_supported",
    current_policy: "probe_only",
    allowed_probe_actions: adapterInfo.lifecycle_allowed_probe_actions || [
      "probe_version",
      "probe_help",
      "probe_eval_help",
    ],
    allowed_probe_commands: adapterInfo.lifecycle_allowed_probe_commands || [
      "--version",
      "--help",
      "eval --help",
    ],
    adapter_specific_disabled_actions: adapterDisabledActions,
    disabled_actions: [...new Set([...commonDisabledActions, ...adapterDisabledActions])],
    future_guarded_actions: adapterInfo.lifecycle_future_guarded_actions || [
      "eval_execution",
      "deployment",
      "publishing",
    ],
    required_before_eval_execution: LIFECYCLE_REQUIRED_BEFORE_EVAL_EXECUTION,
    required_before_deployment: LIFECYCLE_REQUIRED_BEFORE_DEPLOYMENT,
    mutation_policy: adapterInfo.lifecycle_mutation_policy || "probe_only_no_project_or_cloud_mutation",
    material_not_evidence: true,
    evidence_status: adapterInfo.evidence_status || "lifecycle_probe_output_not_verification",
    writes_state: false,
    verification_recorded: false,
    eval_execution_enabled: false,
    deployment_enabled: false,
    scaffold_enabled: false,
    run_enabled: false,
    cloud_mutation_enabled: false,
    project_mutation_enabled: false,
  };
}

function resolveLifecycleProbeBinary(adapter, explicitBin) {
  const config = LIFECYCLE_PROBES[adapter];
  if (!config) {
    return { bin: "", source: "unsupported", error: `Unsupported lifecycle adapter ${adapter}.` };
  }
  const explicit = String(explicitBin || "").trim();
  if (explicit !== "") {
    return isExecutableFile(explicit)
      ? { bin: explicit, source: "explicit", error: "" }
      : { bin: "", source: "explicit", error: `Configured binary is not executable: ${explicit}` };
  }
  const envBin = envValue(config.envName);
  if (envBin !== "") {
    return isExecutableFile(envBin)
      ? { bin: envBin, source: `env:${config.envName}`, error: "" }
      : { bin: "", source: `env:${config.envName}`, error: `Configured binary is not executable: ${envBin}` };
  }
  for (const binaryName of config.binaryNames) {
    const found = findExecutableOnPath(binaryName);
    if (found !== null) {
      return { bin: found, source: "path", error: "" };
    }
  }
  for (const candidate of config.fallbacks) {
    if (isExecutableFile(candidate)) {
      return { bin: candidate, source: "fallback", error: "" };
    }
  }
  return {
    bin: "",
    source: "missing",
    error: `No ${adapter} binary found. Set ${config.envName} or pass bin.`,
  };
}

function inferLifecycleProbeFeatures(adapter, checks) {
  const evalHelp = checks.find((item) => item.name === "eval_help");
  const checksOk = checks.length > 0 && checks.every((item) => item.ok);
  if (adapter === "google-agents-cli") {
    return {
      can_probe_eval: Boolean(evalHelp && evalHelp.ok),
      feature_evidence: checksOk
        ? "version, help, and eval help commands succeeded; no scaffold, run, eval execution, deploy, publish, or cloud mutation was requested"
        : "version, help, or eval help command failed before any lifecycle action was executed",
    };
  }
  if (adapter === "google-adk-cli") {
    return {
      can_probe_eval: Boolean(evalHelp && evalHelp.ok),
      feature_evidence: checksOk
        ? "version, help, and eval help commands succeeded; no create, run, eval execution, deploy, web server, or project mutation was requested"
        : "version, help, or eval help command failed before any lifecycle action was executed",
    };
  }
  return { can_probe_eval: false, feature_evidence: "unsupported lifecycle adapter" };
}

export function probeLifecycleAdapter({ adapter, bin, timeout_seconds }) {
  const selectedAdapter = adapter || "google-agents-cli";
  const config = LIFECYCLE_PROBES[selectedAdapter];
  const timeoutSeconds =
    typeof timeout_seconds === "number" && timeout_seconds > 0 ? timeout_seconds : 10;
  const adapterInfo = ADAPTER_CANDIDATES[selectedAdapter] || {};
  const lifecycleContract = lifecycleLaneContract(selectedAdapter, adapterInfo);
  const resolved = resolveLifecycleProbeBinary(selectedAdapter, bin);
  const result = {
    adapter: selectedAdapter,
    adapter_kind: adapterInfo.kind || "agent_lifecycle",
    status: "blocked",
    binary: resolved.bin,
    binary_source: resolved.source,
    material_not_evidence: true,
    evidence_status: lifecycleContract.evidence_status,
    writes_state: lifecycleContract.writes_state,
    verification_recorded: lifecycleContract.verification_recorded,
    lifecycle_lane_contract: lifecycleContract,
    allowed_probe_actions: lifecycleContract.allowed_probe_actions,
    allowed_probe_commands: lifecycleContract.allowed_probe_commands,
    disabled_lifecycle_actions: lifecycleContract.disabled_actions,
    future_guarded_actions: lifecycleContract.future_guarded_actions,
    can_probe_eval: false,
    eval_execution_enabled: lifecycleContract.eval_execution_enabled,
    deployment_enabled: lifecycleContract.deployment_enabled,
    scaffold_enabled: lifecycleContract.scaffold_enabled,
    run_enabled: lifecycleContract.run_enabled,
    cloud_mutation_enabled: lifecycleContract.cloud_mutation_enabled,
    project_mutation_enabled: lifecycleContract.project_mutation_enabled,
    billing_guard: lifecycleContract.mutation_policy,
    feature_evidence: "",
    checks: [],
    error: resolved.error,
  };
  if (!config) {
    result.error = `lifecycle_probe does not support ${selectedAdapter}.`;
    return result;
  }
  if (resolved.bin === "") {
    return result;
  }
  result.checks = config.checks.map((check) => ({
    name: check.name,
    ...runCliProbeCommand(resolved.bin, check.args, timeoutSeconds),
  }));
  const features = inferLifecycleProbeFeatures(selectedAdapter, result.checks);
  result.can_probe_eval = features.can_probe_eval;
  result.feature_evidence = features.feature_evidence;
  const checksOk = result.checks.every((item) => item.ok);
  result.status = checksOk && result.can_probe_eval ? "available" : "blocked";
  result.error = result.status === "available"
    ? ""
    : result.checks.find((item) => !item.ok)?.error || features.feature_evidence || "lifecycle probe failed";
  return result;
}

export function formatLifecycleProbe(result) {
  const prefix = result.status === "available" ? "[OK]" : "[FAIL]";
  const lines = [
    `${prefix} Lifecycle probe ${result.status}.`,
    `adapter: ${result.adapter}`,
    `binary: ${result.binary || "not found"}`,
    `binary source: ${result.binary_source}`,
    `eval help probe: ${result.can_probe_eval ? "yes" : "no"}`,
    `eval execution enabled: ${result.eval_execution_enabled ? "yes" : "no"}`,
    `deployment enabled: ${result.deployment_enabled ? "yes" : "no"}`,
    `scaffold enabled: ${result.scaffold_enabled ? "yes" : "no"}`,
    `run enabled: ${result.run_enabled ? "yes" : "no"}`,
    `cloud mutation enabled: ${result.cloud_mutation_enabled ? "yes" : "no"}`,
    `project mutation enabled: ${result.project_mutation_enabled ? "yes" : "no"}`,
    `writes state: ${result.writes_state ? "yes" : "no"}`,
    `verification recorded: ${result.verification_recorded ? "yes" : "no"}`,
    `allowed probe actions: ${result.allowed_probe_actions.join(", ")}`,
    `disabled lifecycle actions: ${result.disabled_lifecycle_actions.join(", ")}`,
    `future guarded actions: ${result.future_guarded_actions.join(", ")}`,
    `feature evidence: ${result.feature_evidence || "none"}`,
    `billing guard: ${result.billing_guard}`,
    "evidence: probe output is material, not verification evidence.",
  ];
  for (const item of result.checks || []) {
    const details = [
      `${item.name}: ${item.ok ? "ok" : "failed"}`,
      `exit=${item.exit_code}`,
      `command=${item.command}`,
    ];
    if (item.error) {
      details.push(`error=${item.error}`);
    }
    lines.push(details.join("; "));
  }
  if (result.error && (!result.checks || result.checks.length === 0)) {
    lines.push(`error: ${result.error}`);
  }
  return lines.join("\n");
}
