# ADR 001 — Local-first storage

**Status:** Accepted
**Date:** 2026-08-07 (recorded retroactively; decision made at project start)

## Context

Applyr tracks job applications: companies applied to, rejection reasons,
salary expectations, self-assessed skill gaps. This is personal and sensitive
data. A leak is not embarrassing in the abstract — it is a current employer
learning their employee is interviewing elsewhere.

The project also had to be built and shipped quickly, by one person, while
being used daily during an active job search. Time spent on infrastructure is
time not spent on features the author needs that week.

## Decision

All state lives on the user's machine in `~/.applyr/` — a SQLite database and
a TOML config file. No account, no server, no sync, no telemetry, no network
call of any kind.

`APPLYR_HOME` can relocate the directory, which is how tests and CI isolate
themselves from real data.

## Consequences

### Positive

- Sensitive data never leaves the machine. There is no breach surface because
  there is no server.
- No infrastructure to build, pay for, secure, or keep running.
- Works offline, including on a plane or during an outage.
- Uninstalling is deleting a directory. No account deletion flow to implement.
- No GDPR posture to maintain — the project never becomes a data controller.

### Negative

- No sync across devices. Using two machines means two separate databases.
- No backup. If the user loses the machine without a copy of `~/.applyr/`,
  the history is gone. Migrations are additive partly for this reason: there is
  no restore path.
- No shared or team view — the tool is single-user by construction.

### Neutral

- Sync could be added later without breaking this decision, as an explicit
  opt-in export/import rather than a background service.

## Alternatives considered

**Cloud-hosted with an account.** Rejected. It solves sync, but requires a
backend, authentication, hosting cost and a security posture for exactly the
kind of data least suited to being centralized. Disproportionate for a
single-user tracker.

**Local files synced via Dropbox/iCloud.** Not rejected so much as unnecessary:
`~/.applyr/` is a plain directory, so a user who wants this already has it. It
required no design decision.

## Notes

Simplicity was the strongest driver, with privacy close behind. The author's
framing: the tool had to be developed as fast as possible because it was in
daily use during an active job search — infrastructure work would have
competed directly with that.

Related: [ADR 002](002-why-sqlite.md), [ADR 005](005-single-cli.md).
