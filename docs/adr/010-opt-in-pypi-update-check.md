# ADR 010 — Opt-in PyPI update check

**Status:** Accepted
**Supersedes:** [ADR 001](001-local-first.md) — narrowly, its "no network call of any
kind" clause. Everything else ADR 001 established (all state in `~/.applyr/`, no account,
no server, no sync, no telemetry) still stands and is not reopened here.
**Date:** 2026-08-21

## Context

Users who install `applyr` via `pip install applyr` have no way to learn a new version was
published, short of manually running `pip list --outdated` or checking PyPI/GitHub by hand.
The project owner wants users to be able to find out automatically.

[ADR 001](001-local-first.md) states applyr makes "no network call of any kind" — written
to protect sensitive job-search data (an employer discovering an employee is interviewing)
and to guarantee the tool works fully offline, including with no connectivity at all. A
version check against PyPI's public JSON API is a direct, literal conflict with that clause:
it is an outbound HTTP request, even though it carries no user data and queries a public,
unauthenticated endpoint.

Overriding an accepted ADR requires a new ADR, not a silent edit — this is that ADR.

## Decision

Add an **opt-in, default-off** version check: a new `check_updates` key in `applyr.toml`'s
`[general]` section, defaulting to `false`. When `true`, `applyr doctor` — and only
`doctor`, no other command — queries `https://pypi.org/pypi/applyr/json` (cached 24h on
disk, stdlib `urllib.request` only, no new dependency), compares the result against the
installed version, and prints a single non-blocking line if a newer version exists. Any
failure (no connection, timeout, malformed response) is silent — it never affects `doctor`'s
exit code or its other checks.

Full detail — cache shape, failure modes, `--json` contract — lives in
[`specs/pypi-update-check/spec.md`](../../specs/pypi-update-check/spec.md), not duplicated
here.

The exception is deliberately narrow:

- **Off by default.** A fresh `applyr init` makes zero network calls, exactly as ADR 001
  promised. The exception only applies to users who explicitly turn it on.
- **No data leaves the machine.** The request carries no offer data, no CV data, no
  identifying payload beyond what any HTTP GET inherently carries (IP, User-Agent) — it is
  equivalent to a user manually opening the PyPI package page in a browser.
- **One endpoint, one purpose.** This does not open the door to telemetry or analytics; it
  answers exactly one question ("what's the latest published version?") and nothing else.

## Consequences

### Positive

- Users who opt in learn about new releases without manually checking PyPI, without
  applyr auto-updating anything on their behalf (it only informs, never acts).
- The exception is scoped tightly enough that ADR 001's core guarantees — local-first
  storage, no account, no server, no sync, no telemetry — remain fully true for every user
  who does not explicitly enable `check_updates`.

### Negative

- ADR 001's "no network call of any kind" is no longer literally true for users who opt in.
  Any documentation (README, `AGENT_INSTRUCTIONS.md`, marketing copy) that claims applyr is
  "100% offline" or "makes no network calls" without qualification must be corrected to
  "no network calls unless `check_updates` is explicitly enabled."
- Introduces the codebase's first network-call code path. Future contributors must not
  treat this as precedent for adding other network calls without their own ADR — the
  narrowness (opt-in, single public endpoint, no payload) is what made this acceptable, not
  network calls in general.

### Neutral

- The check surfaces only in `doctor`, not in every command — a user who enables it but
  never runs `doctor` again simply never sees the notice. Accepted as consistent with
  `doctor` already being the designated health-check surface run "every session" per
  `AGENT_INSTRUCTIONS.md`.

## Alternatives considered

**Opt-out, default-on.** Rejected. Maximizes discoverability (most users, like the project
owner, would never think to enable a flag), but breaks "offline by default" for every user,
not just those who want the feature — the exact guarantee ADR 001 exists to protect. Too
broad a violation for what the feature is worth.

**Do nothing — document `pip list --outdated` instead.** Rejected as insufficient. Fully
preserves ADR 001 with zero exception, but does not solve the actual problem (users, in
practice, do not run that command on their own).

**Check on every command, not just `doctor`.** Rejected. Maximizes visibility further than
opt-out/default-on already would, at the cost of a potential network call (even if cached)
on latency-sensitive, frequently-run commands like `add` or `list`. `doctor` is already the
one command whose job is environment/health reporting — the natural, narrowest home for this.

## Notes

This ADR does not reopen or change anything else in ADR 001 — local-first storage, no
account, no server, no sync, and no telemetry all remain exactly as decided. The single
clause narrowed is "no network call of any kind," and only for the specific, auditable case
described above.
