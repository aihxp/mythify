# Summary

Describe what this PR changes and why. If it fixes an issue, link it.

# Checklist

- [ ] Python suite passes locally: `python3 -m unittest discover -s tests -v`
- [ ] MCP server suite passes locally: `cd mcp-server && npm ci && npm test`
- [ ] If any CLI command, MCP tool, or on-disk format changed, `docs/design.md` is updated to match (it is the authoritative contract)
- [ ] If shared CLI and MCP behavior changed, both runtimes were updated or the intentional asymmetry is documented, with a shared manifest update, cross-runtime fixture, or interop assertion
- [ ] If `protocol/PROTOCOL.md` changed, variants were rebuilt with `python3 scripts/build_variants.py` and the regenerated `CLAUDE.md`, `AGENTS.md`, and `.cursorrules` are committed
- [ ] ASCII only: no emojis, no em dashes, no en dashes in any file or program output
- [ ] PR title follows Conventional Commits (for example `feat: ...`, `fix: ...`, `docs: ...`)
