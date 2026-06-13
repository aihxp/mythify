# Google Colab CLI Spike Plan

Date: 2026-06-12

Purpose: define Mythify's safe Google Colab CLI support. The first slice was
probe-only; the current slice adds a guarded ephemeral run path without
persistent sessions, Drive mounting, manual upload or download commands, or
notebook log export.

## Current Support

Mythify supports a non-billable probe through the MCP tool `execution_probe`
with `adapter: "google-colab-cli"`.

The probe is intentionally narrow:

- Resolve a CLI binary from `bin`, `MYTHIFY_COLAB_BIN`, PATH, or common install
  paths.
- Run `--version`.
- Run `--help`.
- Return binary resolution, command output tails, status, and guard fields.
- Mark the result as material, not verification evidence.

The probe always reports:

- `non_billable: true`
- `job_execution_enabled: false`
- `can_run_remote_job: false`
- `remote_runtime_provisioned: false`
- `accelerator_requested: false`
- `data_uploaded: false`
- `artifact_retrieval_enabled: false`
- `billing_guard: "probe_only_no_runtime_provisioning"`

Mythify also supports a guarded remote execution adapter through the MCP tool
`execution_run` with `adapter: "google-colab-cli"`.

The run path is intentionally narrow:

- Resolve a CLI binary from `bin`, `MYTHIFY_COLAB_BIN`, PATH, or common install
  paths.
- Resolve a local `script_path` from `cwd`.
- Require `billing_ack: true`.
- Require `data_movement_ack: true`.
- Require `cleanup_ack: true`.
- Run `colab run` with optional `--gpu` or `--tpu` accelerator flags.
- Never pass `--keep`; use the official ephemeral runner teardown path.
- Return stdout and stderr tails, duration, timeout status, exit code, and
  acknowledgement fields.
- Mark the result as material, not verification evidence.
- Write no Mythify state.

The run path always reports:

- `job_execution_enabled: true`
- `material_not_evidence: true`
- `evidence_status: "remote_output_not_verification"`
- `writes_state: false`
- `verification_recorded: false`
- `cleanup_guard: "colab_run_without_keep"`
- `billing_guard: "requires_billing_ack"`
- `data_movement_guard: "requires_data_movement_ack"`

## Non-Goals

This slice does not:

- Start or attach to a Colab runtime.
- Keep a Colab runtime alive after completion.
- Run manual `colab exec`, `colab repl`, `colab console`, `colab upload`,
  `colab download`, `colab drivemount`, or `colab log` commands.
- Retrieve artifacts or logs outside whatever the official ephemeral runner
  returns.
- Write Mythify state.
- Count as verification evidence.

## Remote Execution Contract

Remote execution may run only through a command with explicit billing, data
movement, and cleanup acknowledgement fields.

Required output fields for remote execution:

- Local command and full argument vector.
- Remote command exit code.
- Accelerator type and requested accelerator.
- Start time, end time, and duration.
- Billing acknowledgement.
- Data movement acknowledgement.
- Cleanup acknowledgement.
- Timeout status.

Future manual session, upload, download, Drive mount, log export, or artifact
retrieval commands need their own design slice before they are exposed.

## Guardrails

- Default to probe-only behavior.
- Require an explicit user request before `execution_run`.
- Require explicit billing and data movement acknowledgement before accelerator
  or upload work.
- Treat remote logs and artifacts as material until an executed verifier consumes
  them.
- Never let `execution_probe` become a hidden executor.
- Never pass `--keep` from the initial adapter.
