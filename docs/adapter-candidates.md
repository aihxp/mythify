<!-- Generated from mcp-server/src/capability-registry.js by scripts/build_registry_docs.mjs. Edit the registry, then rebuild. -->

# Adapter Candidates

This file is generated from `mcp-server/src/capability-registry.js`. Do not edit it by hand.

| Adapter | Kind | Status | Local | OpenAI Compatible | Probe | Run Path | Current Chat Apply | Current Chat Confirm | Worker Model Override | Thinking Override | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| anthropic-api | api_provider | metadata_supported | no | no | no | metadata only; no API worker | unknown | unknown | unknown | unknown | metadata only, not evidence |
| antigravity | host | worker_supported | no | no | yes | bounded worker | unsupported | unsupported | supported | unsupported | material, not evidence |
| custom-command | custom_adapter | bounded_execution_supported | yes | no | no | bounded worker | unknown | unknown | unknown | unknown | material, not evidence |
| custom-http | custom_adapter | metadata_only | no | no | no | metadata only; no API worker | unknown | unknown | unknown | unknown | metadata only, not evidence |
| generic-openai-compatible | model_provider | local_backend_supported | yes | yes | yes | local roles: reader, triage | unknown | unknown | unknown | unknown | material, not evidence |
| google-adk-cli | agent_lifecycle | probe_supported | no | no | yes | eval probe; no eval run; no deploy | unknown | unknown | unknown | unknown | probe material, not evidence |
| google-agents-cli | agent_lifecycle | probe_supported | no | no | yes | eval probe; no eval run; no deploy | unknown | unknown | unknown | unknown | probe material, not evidence |
| google-colab-cli | execution_substrate | guarded_remote_execution_supported | no | no | yes | remote job | unknown | unknown | unknown | unknown | material, not evidence |
| kimi-code | host | worker_supported | no | no | yes | bounded worker | unsupported | unsupported | unsupported | unsupported | material, not evidence |
| kimi-work | desktop_agent | metadata_only | yes | no | no | metadata only | unsupported | unsupported | unsupported | unsupported | metadata only, not evidence |
| llama-cpp | model_provider | local_profile_supported | yes | yes | yes | local roles: reader, triage | unknown | unknown | unknown | unknown | material, not evidence |
| lm-studio | model_provider | local_profile_supported | yes | yes | yes | local roles: reader, triage | unknown | unknown | unknown | unknown | material, not evidence |
| ollama | model_provider | local_profile_supported | yes | yes | yes | local roles: reader, triage | unknown | unknown | unknown | unknown | material, not evidence |
| openai-api | api_provider | metadata_supported | no | yes | no | metadata only; no API worker | unknown | unknown | unknown | unknown | metadata only, not evidence |
| openai-compatible-hosted | api_provider | metadata_supported | no | yes | no | metadata only; no API worker | unknown | unknown | unknown | unknown | metadata only, not evidence |
| opencode | host | worker_supported | no | no | yes | bounded worker | unsupported | unsupported | supported | unsupported | material, not evidence |
| opencode-desktop | desktop_agent | metadata_only | yes | no | no | metadata only | unsupported | unsupported | unsupported | unsupported | metadata only, not evidence |
| vllm | model_provider | local_profile_supported | yes | yes | yes | local roles: reader, triage | unknown | unknown | unknown | unknown | material, not evidence |
