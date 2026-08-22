# ADR 011 — Visual UI as an optional, additive interface

**Status:** Accepted
**Narrows:** [ADR 005](005-single-cli.md) — specifically its "one command-line
interface" framing. The rest of ADR 005 (stdlib `argparse`, flat `elif` dispatch,
`colorama` as the only *required* runtime dependency) still stands and is not
reopened here.
**Date:** 2026-08-23

## Context

[ADR 005](005-single-cli.md) established applyr as one CLI, built on the standard
library, with `colorama` as its only runtime dependency — chosen so `pip install applyr`
is instant, cannot fail on a dependency conflict, and stays permanently easy to run from
any AI coding agent's shell.

The project owner wants a local, visual dashboard on top of applyr: paste/upload job
offers, watch them move through the existing Matcher/Recruiter pipeline, review and
approve without hand-typing JSON into `applyr add` every time. That requires an HTTP
server and a browser-rendered frontend — neither expressible as "one CLI, stdlib only."

Full scope, stack decisions, and the accepted-as-permanent invariants for this feature
live in `docs/visual-ui/AGENTS.md` (single user, local process, no LLM calls from the
backend, no Postgres/Redis/Celery/auth) and `specs/visual-ui/spec.md` (this slice's
concrete data model and API contract). This ADR records only the one thing that changes
project-wide: applyr now has a second, optional interface.

Overriding an accepted ADR requires a new ADR, not a silent edit — this is that ADR.

## Decision

Add an **opt-in, additive** interface: `applyr ui`, gated behind a new
`pip install applyr[ui]` extra (`fastapi`, `uvicorn`; `httpx` for tests only). The base
`applyr` install is unaffected — zero new required dependencies, `import applyr.cli`
must succeed with `fastapi`/`uvicorn` absent (enforced by
`tests/test_ui_cli.py::TestUiCommand::test_importing_cli_does_not_require_fastapi`).

The narrowing is deliberately scoped:

- **Additive, not a replacement.** Every existing command keeps working exactly as
  before. `applyr ui` is a new command in the same flat `elif` dispatch (ADR 005's
  routing style is unchanged), not a new entry point or a parallel tool.
- **Opt-in by install, not just by flag.** A user who never runs
  `pip install applyr[ui]` never has FastAPI/uvicorn on disk at all — closer to ADR 010's
  "off by default" precedent than to a feature flag on an always-installed dependency.
- **The CLI stays the source of truth.** The dashboard reads/writes the same
  `~/.applyr/jobs.db` through `applyr/db.py` and the new `applyr/intake.py`; it never
  bypasses `applyr add`'s validation, and it never calls an LLM itself (ADR 003 is fully
  intact — the AI coding agent remains the only reasoner, now optionally handed offers
  through a dashboard form instead of a pasted JSON blob).
- **Local, unauthenticated, loopback-only.** `applyr ui` binds `127.0.0.1` with no
  `--host` override (see `specs/visual-ui/spec.md`'s security NFR) — the same
  single-user threat model as the CLI itself, not a step toward a hosted/multi-user
  product.

## Consequences

### Positive

- Users who want a visual pipeline view get one without the CLI-only majority paying any
  cost — no dependency growth, no slower `pip install applyr`, no new attack surface for
  anyone who doesn't opt in.
- Keeps the two concerns cleanly separated: `applyr/` (core, stdlib-only, ADR 005) vs.
  `applyr/ui/` (optional, FastAPI). A contributor auditing "does this need a dependency
  review" can answer it by which directory changed.

### Negative

- ADR 005's "a single CLI" is no longer literally true — applyr now has two entry points
  (`applyr <command>` and `applyr ui` serving HTTP). Any documentation or marketing copy
  that claims applyr is "just a CLI, nothing else to run" needs the same qualification
  ADR 010 required for "100% offline": true unless the optional extra is installed and
  used.
- Introduces the codebase's first HTTP server and first web frontend. Future
  contributors must not treat this as precedent for adding other services (a second
  API, a mobile app, etc.) without their own ADR — the narrowness (one optional extra,
  reuses the existing DB and CLI validation, loopback-only, no LLM calls) is what made
  this acceptable, not "add services" in general.

### Neutral

- `applyr/ui/` deliberately imports `fastapi`/`uvicorn` only inside function bodies,
  never at module level, so the *code* for the UI ships in the base package (small,
  pure-Python, no import cost) while the *dependency* only activates when `[ui]` is
  installed and `applyr ui` is actually run.

## Alternatives considered

**Separate PyPI package (`applyr-ui`), depending on `applyr`.** Rejected for this slice.
Would fully preserve ADR 005's "one package" framing, but adds release/versioning
overhead (two packages to keep in sync) for a feature still being scoped slice by slice
on `feat/cc-visual-ui`. Revisit if the UI grows large enough that shipping it separately
becomes worth that overhead.

**Bundle FastAPI/uvicorn as required dependencies.** Rejected. Directly contradicts
ADR 005's reason for existing — "pip install applyr is instant and cannot fail on a
dependency" — for the ~all users who only want the CLI an AI agent drives.

**A second CLI-only interface (TUI) instead of a web UI.** Rejected by the project
owner during scoping (see chat session 2026-08-22/23): the goal is a visually
"llamativo" dashboard offers can be pasted into directly, which a terminal UI does not
deliver.

## Notes

This ADR does not reopen ADR 003 (no LLM calls) or ADR 002 (SQLite) — both are fully
intact and this feature is designed around preserving them (see Decision above). The
single clause narrowed is ADR 005's "one CLI" framing, and only for the specific,
optional, loopback-only case described here.
