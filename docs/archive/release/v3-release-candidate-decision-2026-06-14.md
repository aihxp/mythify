# v3.0 Release Candidate Decision

Date: 2026-06-14

This decision reviewed the final pushed release-readiness state after
`docs/v3-release-readiness-sweep.md`. It did not tag, publish, or mutate any
release artifact.

## Decision

Do not create a `v3.0` release-candidate tag yet.

The safe next action is release version alignment: decide whether the next
artifact should remain on the `2.5.x` line, move to `2.6.0`, or intentionally
bump to `3.0.0`, then update package metadata, changelog anchors, and release
docs before any tag is created.

## Evidence

Fresh readiness still reports `ready_for_release_review` with all recorded
gates passing:

- Total gates: 9
- Passed gates: 9
- Failed gates: 0
- Missing gates: 0
- Unknown gates: 0

Version and tag state:

- `mcp-server/package.json` reports version `2.5.0`.
- The latest matching release tag is `v2.5.0`.
- `CHANGELOG.md` has an `Unreleased` section above `2.5.0`.
- `docs/v3-release-readiness-sweep.md` records MCP package version `2.5.0`.

## Rationale

The readiness gates are green, but a `v3.0` release-candidate tag would imply
that the release artifact, changelog, and tag line are already aligned to a
3.0.0 release. They are not. Creating that tag now would make release metadata
less honest even though the code and tests are healthy.

## Guardrail

Before any release-candidate tag:

- Package metadata must match the intended release version.
- Changelog anchors must match the intended release version.
- Release docs must name the intended release version.
- The full release gate must be executed on the final commit.
- Tagging and publishing still require explicit user intent.
