# Google Colab CLI Spike Plan

Date: 2026-06-12

Purpose: define the first safe Mythify slice for Google Colab CLI without
provisioning a runtime, requesting an accelerator, uploading data, executing a
notebook, or retrieving artifacts.

## Current Support

Mythify supports a probe-only execution adapter through the MCP tool
`execution_probe` with `adapter: "google-colab-cli"`.

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

## Non-Goals

This slice does not:

- Run `colab run` or any equivalent remote execution command.
- Start or attach to a Colab runtime.
- Request GPUs, TPUs, or other accelerators.
- Execute notebooks, Python scripts, shells, or cells.
- Upload project files or notebooks.
- Retrieve artifacts or logs.
- Write Mythify state.
- Count as verification evidence.

## Future Adapter Contract

A later execution adapter may run remote work only after a separate design slice
adds an explicit contract for billable and data-moving operations.

Required evidence fields for future remote execution:

- Local command and full argument vector.
- Remote command exit code.
- Runtime or session id.
- Accelerator type and allocation status.
- Start time, end time, and duration.
- Log path or log artifact id.
- Output artifact ids or local retrieval paths.
- Upload manifest with file count and byte count.
- Teardown status.
- Billing acknowledgement.
- Data movement acknowledgement.

## Guardrails

- Default to probe-only behavior.
- Require an explicit user request before any remote execution command.
- Require explicit billing and data movement acknowledgement before accelerator
  or upload work.
- Treat remote logs and artifacts as material until an executed verifier consumes
  them.
- Never let `execution_probe` become a hidden executor.
