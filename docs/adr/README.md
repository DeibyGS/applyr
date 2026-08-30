# Architecture Decision Records

Why applyr is built the way it is. Read these before proposing a change that
reverses one of them.

| ADR | Decision | Status |
|-----|----------|--------|
| [001](001-local-first.md) | Local-first storage — everything in `~/.applyr/`, no server | Accepted |
| [002](002-why-sqlite.md) | SQLite as the storage engine | Accepted |
| [003](003-no-llm-calls.md) | No LLM API calls — the agent reasons, applyr remembers | Accepted |
| [004](004-weighted-scoring.md) | Configurable weighted scoring over six topics | Accepted |
| [005](005-single-cli.md) | A single CLI on the standard library, one dependency | Accepted |
| [006](006-errors-to-stderr.md) | Errors and warnings to stderr, data to stdout | Accepted |
| [007](007-structured-json-errors.md) | Structured JSON errors on stderr with stable codes | Accepted |
| [008](008-md-first-cv-pipeline.md) | MD-first CV pipeline — markdown drafts, HTML+PDF at render | Accepted |
| [009](009-weight-versioning-and-rebalance.md) | Weight versioning + rescore + rebalanced `DEFAULT_WEIGHTS` — supersedes 004 | Accepted |
| [010](010-opt-in-pypi-update-check.md) | Opt-in, default-off PyPI version check in `doctor` — narrowly supersedes 001 | Accepted |
| [011](011-visual-ui-optional-interface.md) | Visual UI as an optional, additive interface — narrows 005 | Accepted |
| [012](012-applyr-world-pixijs-engine.md) | PixiJS as the rendering engine for Office's "Applyr World" scene — narrows 011's Stack table, engine decision only, implementation not yet scoped | Accepted |
| [013](013-applyr-world-movement-and-push-transport.md) | Cross-zone offer movement + SSE push transport for "Applyr World" — partially supersedes 012's "no WebSocket, polling only" constraint | Accepted |
| [014](014-async-intake-pipeline-agent-attended-scoring.md) | Async intake pipeline — SQLite job queue + in-process worker, `PENDING_AGENT` scoring state, reaffirms 003 (no server-side LLM calls) | Accepted |

## Conventions

- **Immutable once accepted.** A new decision creates a new ADR that supersedes
  the old one; it never edits it. The record of what was believed and when is
  the point.
- **Format:** Status · Context · Decision · Consequences (positive, negative,
  neutral) · Alternatives considered.
- **Naming:** `NNN-short-slug.md`, numbered sequentially.

## When to write one

Write an ADR when the decision would be **costly to reverse** — roughly, when
undoing it in six months would take more than two weeks of rework, or when it
changes a contract in [`../contracts.md`](../contracts.md).

Concretely, these need an ADR before a PR:

- Replacing the storage engine
- Adding a runtime dependency
- Adding a network call or an LLM API call
- Changing the scoring formula or `DEFAULT_WEIGHTS`
- Redesigning the CLI or the `--json` shape
- Routing output to stderr (see the known limitation in
  [`../contracts.md`](../contracts.md))

Routine work does not need one. Adding a command, an export format or a config
option is covered by [`../agent-workflow.md`](../agent-workflow.md).

## A note on these five

ADRs 001–005 were written retroactively, in August 2026, for decisions made at
project start. They reconstruct reasoning rather than record it live, so where
a rationale was reconstructed after the fact — or where the original reasoning
turned out not to hold — the ADR says so explicitly rather than presenting a
tidy story. See the closing sections of [002](002-why-sqlite.md) and
[004](004-weighted-scoring.md).

Future ADRs should be written **before** the decision is implemented.
