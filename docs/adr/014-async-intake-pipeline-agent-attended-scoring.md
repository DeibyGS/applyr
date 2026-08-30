# ADR 014 — Async intake pipeline with agent-attended scoring (reaffirms ADR-003)

**Status:** Accepted
**Reaffirms:** [ADR-003](003-no-llm-calls.md) (no LLM API calls) — evaluated against an external
proposal that would have reversed it, and explicitly not reversed.
**Narrows:** [ADR-011](011-visual-ui-optional-interface.md) (Visual UI optional interface) — the
UI's "paste and process" flow gains a persisted queue/worker model instead of the SSE-triggered
daemon hack shipped in PR #115.
**Date:** 2026-08-31

## Context

- PR #115 (`feat/oc-autopilot-and-ui-start`) added `applyr/ui/autopilot.py`, a daemon that
  listens on the existing `/api/events/enriched` SSE stream for a "procesala" keyword and then
  runs the intake → add → `cv generate` pipeline via CLI subprocess calls.
- That daemon fabricates the Matcher step: it derives `company`/`title` by taking the first two
  non-blank lines of the pasted offer text, and calls `applyr add` with no `topics` at all — no
  real compatibility score. This violates `AGENTS.md`'s core principle #1 ("cv-master.md is the
  only source of truth — never invent") and defeats the point of the Matcher role described in
  `applyr/templates/AGENT_INSTRUCTIONS.md`.
- Separately, the project owner brought an external architecture proposal for the same underlying
  problem (UI "Enviar" should not block on the LLM, should show live progress, should be
  provider-agnostic), modeled on a typical SaaS stack: Redis + BullMQ job queue, PostgreSQL, and
  an `Agent` interface (`ClaudeAgent` / `OpenCodeAgent`) that a background worker calls directly
  with an API key.
- That proposal's `Agent.execute()` step — the backend invoking a model itself — is exactly what
  ADR-003 forbids, for the same reasons ADR-003 already gives: it would pay to re-derive judgment
  the attended coding agent (Claude Code, OC, Cursor...) already has in its context, and it would
  add an API key, a network layer, and a cost model to a project whose whole premise (ADR-001,
  ADR-005) is local-first and dependency-light.
- The project owner explicitly chose, after seeing this trade-off laid out, to keep ADR-003 intact
  rather than reverse it (chat decision, 2026-08-31: "opcion a").

## Decision

1. **The reasoning boundary from ADR-003 does not move.** No component introduced by this
   decision calls an LLM API. The worker described below only performs deterministic work.
2. **A SQLite-backed job table replaces ad hoc SSE-triggered subprocess calls.** Submitting an
   offer from the UI ("Enviar") inserts a job row driven by the state machine below, instead of
   the daemon reacting to a chat keyword after the fact.
3. **Pipeline states, persisted in DB (source of truth, not SSE):**
   `QUEUED → DEDUPING → STRUCTURING → PENDING_AGENT → (agent completes scoring/CV externally) →
   READY → applied/discarded`, with `FAILED` reachable from any step and the failed step name
   recorded.
   - `DEDUPING` and `STRUCTURING` are pure code: company/title/tech-stack extraction from the
     pasted text, duplicate check against existing offers — the deterministic slice of what
     `autopilot.py` does today, done properly instead of as a byproduct of a regex match on a
     chat message.
   - `PENDING_AGENT` is the step ADR-003 reserves for the attended agent: the job stops there and
     waits. No timeout auto-advances it, no fallback score gets invented.
4. **A worker runs in-process** with the existing `uvicorn` process `applyr ui` already starts —
   no Redis, no separate worker process, no new runtime dependency. The `ui` extra (`fastapi`,
   `uvicorn`, `httpx`) already installed for the Visual UI stays sufficient.
5. **No `Agent` provider abstraction.** There is exactly one kind of executor for the
   `PENDING_AGENT` step — whichever coding-agent session is attended when the job reaches that
   state — so a swappable `ClaudeAgent` / `OpenCodeAgent` interface has no second implementation
   to abstract over. If a real second executor appears later, this decision is revisited then, not
   speculatively now.
6. **Idempotency and retries apply only to the deterministic steps.** A double "Enviar" click must
   not create two job rows for the same pasted text; a `FAILED` job at `DEDUPING` / `STRUCTURING`
   can be retried without re-creating the intake row (mirrors `ui_intake`'s existing
   `pending → promoted` guard in `intake.py`).
7. **`applyr/ui/autopilot.py` is rewritten, not extended**, to stop faking the Matcher step: it
   becomes the deterministic worker (step 3's `DEDUPING` / `STRUCTURING` only), and it stops
   calling `applyr add` on its own. Progress still reaches the UI over the existing SSE stream
   (`/api/events/enriched`); this decision does not reopen ADR-013's transport choice.

## Consequences

### Positive

- Closes a real correctness bug already in code bound for `main` (fabricated scores, invented
  company/title) without waiting for a separate bugfix pass — the redesign and the fix are the
  same change.
- No new runtime dependency, no API cost, no key management — stays inside
  ADR-001 / ADR-003 / ADR-005's local-first, dependency-light envelope.
- The DB becomes the actual source of truth for pipeline progress (what the external proposal
  correctly called out), not an artifact of whichever SSE listener happens to be connected.
- Reuses the transport ADR-013 already justified (SSE, not WebSocket, not polling) instead of
  introducing a second real-time mechanism.

### Negative

- The UI's "Enviar" flow does not become truly fire-and-forget: a human (or attended agent
  session) must still be present to clear `PENDING_AGENT`, the same limitation ADR-003 already
  accepts project-wide. Users who want zero-touch batch processing don't get it from this
  decision.
- New DB surface: a job table and a state machine, plus the migration to add it — the same
  category of cost ADR-013 flagged for `pipeline_stage` (schema surface keeps growing).
- `autopilot.py`'s existing (if crude) behavior — the only thing giving today's UI any automatic
  progress at all — is being replaced, so this is a rewrite with regression risk, not a pure
  addition.

### Neutral

- This does not change the CLI's own contract (`applyr add`, `--json`, etc.) — the job table is
  UI-only plumbing, the same treatment ADR-013 gave the CLI→UI POST endpoint (private, no
  compatibility guarantee).

## Alternatives considered

**Reverse ADR-003 — give the backend its own Claude API key (the external proposal's literal
`Agent.execute()`).** Rejected by the project owner: reintroduces API cost and key management for
a local single-user tool, and duplicates judgment the attended agent already has in context — the
exact argument ADR-003 already made, re-evaluated here and not overturned.

**Redis + BullMQ (the external proposal's literal queue choice).** Rejected: Node-specific tooling
in a Python project, and a new infrastructure dependency (a running Redis instance) for a single
local user, where an in-process SQLite-backed queue does the same job with nothing new to install
or keep running.

**Keep `autopilot.py` as-is, patch the scoring gap in place.** Rejected: the daemon's design
(react to a chat keyword over SSE, then improvise structured data from raw pasted text) is the
root cause, not an edge case of it — patching it would keep inventing data on every path that
isn't the one bug fixed, and would still leave no persisted job state for the UI to recover after
a reload, the exact "DB is not source of truth" gap the external proposal correctly flagged.

## Notes

- The next artifact is the implementation `/sdd` spec: the exact job-table schema, the migration
  version, the worker's polling/wake mechanism inside the existing process, the new/changed API
  endpoints, and the `autopilot.py` rewrite's test plan.
- Per this project's `/adversarial-test` gate (state machine, data integrity), the job table's
  state transitions should go through adversarial verification before merge, the same as
  ADR-013's `pipeline_stage`.
- Engram summary saved under topic key `adr:applyr:async-intake-pipeline-agent-attended-scoring`.
