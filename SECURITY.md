# Security Policy

## Supported versions

| Version | Supported |
| :--- | :--- |
| 2.x | Yes |
| Anything earlier | No (unreleased prototypes) |

## Reporting a vulnerability

Do not open a public issue for security problems.

Report privately through GitHub Security Advisories:
https://github.com/aihxp/mythify/security/advisories/new

If you cannot use GitHub, email hprincivil@gmail.com with a description, a
reproduction, and the impact you believe it has.

What to expect:

- Acknowledgment within 7 days.
- A fix or documented mitigation within 30 days for confirmed issues, with
  credit to the reporter in the changelog unless you ask otherwise.

## Mythify's execution model (read before reporting)

Some behavior is by design and is not a vulnerability:

- `verify run` (CLI) and `verify_run` (MCP tool) execute arbitrary shell
  commands. That is the feature: verification means running real commands and
  recording real exit codes. The commands run with the privileges of whoever
  runs the CLI or the MCP server.
- Mythify is not a sandbox and does not try to be one. It does not restrict
  what a model asks it to run. The boundary is the operating-system user the
  server runs as.

Hardening guidance for users:

- Set `MYTHIFY_DISABLE_RUN=1` in the MCP server environment to disable
  `verify_run` entirely (the tool refuses and records nothing).
- Never run the MCP server with elevated privileges.
- Do not store secrets in memory entries or lessons. Everything under
  `.mythify/` is plain text on disk.

A report is in scope when Mythify does something other than what this model
describes: for example, executing commands while `MYTHIFY_DISABLE_RUN=1` is
set, writing state outside the resolved `.mythify/` directory, or any path
traversal in state-file handling.
