# Antigravity MCP Setup Guide

Date: 2026-06-12

This guide records the safe setup path for using Mythify with Google
Antigravity. It is a setup guide and probe contract, not a worker adapter.

## Current Support

Mythify supports `host_cli_probe` with `host: "antigravity"`.

The probe:

- resolves `agy` through `MYTHIFY_ANTIGRAVITY_BIN`, PATH, or common install
  paths.
- runs `agy --version` and `agy --help`.
- reports whether help output exposes non-interactive prompt mode.
- returns `material_not_evidence: true`.
- does not execute prompts.
- does not write MCP config.
- does not start workers.

## MCP Config Paths

Antigravity documentation and codelabs reference these MCP config locations:

- `~/.gemini/config/mcp_config.json`
- `~/.gemini/antigravity-cli/mcp_config.json`
- `.agents/mcp_config.json`

Use the project-level `.agents/mcp_config.json` path when you want a repo-local
setup. Use the home-level paths only when you intentionally want Mythify
available across projects.

## Mythify Server Entry

Add a Mythify MCP server entry that points at the local checkout:

```json
{
  "mcpServers": {
    "mythify": {
      "command": "node",
      "args": ["/absolute/path/to/mythify/mcp-server/src/index.js"],
      "env": {
        "MYTHIFY_DIR": "/absolute/path/to/project/.mythify"
      }
    }
  }
}
```

Then verify from a terminal before relying on the host:

```bash
cd /absolute/path/to/mythify
node mcp-server/src/index.js
```

That command starts the MCP server over stdio. It will wait for an MCP client,
so stop it manually after confirming it starts without a Node import error.

## Probe Command

Once Antigravity can see the Mythify MCP server, call:

```json
{
  "host": "antigravity",
  "format": "json"
}
```

If `agy` is not on PATH, set:

```json
{
  "host": "antigravity",
  "bin": "/absolute/path/to/agy",
  "format": "json"
}
```

The probe result is not verification evidence. Use `verify_run` for actual
claims about a project, build, test, or command outcome.

## Guardrails

- Do not treat a passing probe as worker support.
- Do not claim Mythify can switch the current Antigravity model unless a future
  adapter confirms that capability.
- Do not run `agy -p` from Mythify until a separate worker slice adds timeout,
  workspace, permission, output, and model controls.
- Keep MCP config edits explicit and reviewable.
