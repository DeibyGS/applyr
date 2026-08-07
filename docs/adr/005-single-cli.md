# ADR 005 — A single CLI, built on the standard library

**Status:** Accepted
**Date:** 2026-08-07 (recorded retroactively; decision made at project start)

## Context

Applyr's primary caller is an AI coding agent, which already has a shell and
uses it constantly. Its secondary caller is the author, checking the state of
an active job search several times a day.

The tool was built while being used daily. That imposed two constraints most
side projects do not have: it had to be fast to develop, and it could never be
broken for long, because a broken applyr meant losing track of real
applications in progress.

## Decision

One command-line interface, `applyr`, built on `argparse` from the standard
library. Commands route through a flat `elif` chain in `applyr/cli.py`.

The only runtime dependency is `colorama` (>= 0.4.6), and only for Windows
terminal color support.

## Consequences

### Positive

- **`pip install applyr` is instant and cannot fail on a dependency.** One
  small, stable package. No build step, no wheels to compile, no version
  conflicts with whatever else is in the user's environment.
- **Agents already know how to use it.** Every agent can run a shell command
  and read stdout. No SDK to learn, no import path to discover.
- **Composable.** `applyr list --json | jq`, cron, shell scripts — all free.
- **Nothing to break on upgrade.** Fewer dependencies means fewer external
  changes that can break a tool in daily use.
- **`argparse` is boring and permanent.** It will not have a 2.0 that
  reorganizes its API.

### Negative

- **`argparse` is verbose.** Click or Typer would express the same CLI in
  noticeably less code, with better help output and free shell completion.
- **The `elif` chain in `cli.py` scales poorly.** At ~21 commands it is still
  readable; it will not stay that way indefinitely. A dispatch table is the
  obvious refactor when it stops being readable.
- **No importable Python API.** Using applyr from another program means
  shelling out and parsing `--json`, not importing a function.

### Neutral

- The internal functions are importable in practice, but are not a contract
  and may change. See [`contracts.md`](../contracts.md).

## Alternatives considered

**Click or Typer.** Rejected on the dependency constraint alone. Both are
excellent and would have produced cleaner code, but they add a dependency tree
to a project whose selling point is having almost none. `argparse` costs more
lines and zero installs.

**A Python library first, CLI as a wrapper.** Rejected. It doubles the public
surface — every change then has to preserve both an API and a CLI. Given
[ADR 003](003-no-llm-calls.md), the consumer is an agent with a shell, which
does not need an importable API.

**A TUI.** Rejected. It is worse for the primary user: an agent cannot drive an
interactive interface, and it is not scriptable. It also requires a framework,
contradicting the dependency constraint.

**A web UI.** Rejected. It contradicts [ADR 001](001-local-first.md) and is
disproportionate work for a single-user tool.

## Notes

The author's stated reasoning: keep it lightweight, keep dependencies near
zero because the use case is simple, and be able to develop it as fast as
possible — the tool is in daily use during an active job search.

That last point is the real constraint behind this ADR and worth preserving.
Applyr is dogfooded continuously by its author. Anything that slows down
shipping, or that can break on somebody else's release schedule, has a cost
this project is unusually sensitive to.

Related: [ADR 001](001-local-first.md), [ADR 002](002-why-sqlite.md),
[ADR 003](003-no-llm-calls.md).
