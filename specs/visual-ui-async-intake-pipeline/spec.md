## Spec: Async intake pipeline (ADR-014)

### Status: APPROVED
### Version: 1.0

### Recovered context

- **`docs/adr/003-no-llm-calls.md` (Accepted)** — applyr contains no LLM API calls, no
  keys, no network layer. The reasoning happens in the attended coding agent; applyr only
  stores results and computes deterministic aggregates. Non-negotiable for this spec.
- **`docs/adr/005-single-cli.md` / `docs/adr/011-visual-ui-optional-interface.md`** — the
  base CLI stays dependency-light (stdlib + colorama); the Visual UI is an optional
  `applyr[ui]` extra (`fastapi`, `uvicorn`, `httpx`). No new runtime dependency is
  introduced here.
- **`docs/adr/013-applyr-world-movement-and-push-transport.md`** — established the SSE
  transport (`GET /api/events`, `/api/events/enriched`) and the CLI→backend best-effort
  notification pattern (`applyr/ui_events.py`: 0.2s timeout, swallows all failures, never
  affects the calling command's exit code). Reused here, not reopened.
- **`docs/adr/014-async-intake-pipeline-agent-attended-scoring.md` (Accepted)** — the
  decision this spec implements. Job states `QUEUED → DEDUPING → STRUCTURING →
  PENDING_AGENT → READY/FAILED`, in-process worker (no Redis/Celery), no `Agent`
  provider abstraction, `PENDING_AGENT` only advances via an attended agent's
  `applyr add --intake-id`.
- **`docs/visual-ui/AGENTS.md`** — non-negotiable invariant #2 ("Claude Code / OpenCode /
  Cursor remains the brain... never re-implements Matcher/Recruiter scoring logic") and
  invariant #4 ("no infrastructure beyond a single process... no Celery"). This spec's
  design was checked against the "Explicitly rejected" list (Postgres, Redis, Celery +
  queues, an `LLMProvider` abstraction) — none of those are introduced. Invariant #3
  ("Data flow for a new offer") is **narrowed** by this spec, not reversed: the
  deterministic sub-steps become automatic on submit; only the `PENDING_AGENT` step still
  requires "user tells their AI agent... to process."
- **PR #115** (`feat/oc-autopilot-and-ui-start`) shipped `applyr/ui/autopilot.py`, an
  SSE-keyword-triggered daemon that fabricates the Matcher step (company/title from the
  first 2 lines of pasted text, `applyr add` with no `topics`). This spec replaces it.
- Corrected assumptions from Step 2 (all confirmed by the project owner, 2026-08-31):
  new table `ui_jobs` (not a `ui_intake` status extension); `STRUCTURING` runs before
  `DEDUPING` (need the extracted company to dedupe by); a distinct `duplicate` terminal
  state (not lumped into `failed`); SSE broadcast on every state transition (not only
  `PENDING_AGENT`); retries are manual-only; `GET /api/jobs` (existing, offers/Kanban) is
  untouched — job state is exposed via `GET /api/intake`; `docs/visual-ui/AGENTS.md`
  invariant #3 gets updated explicitly as part of this work; PR budget will exceed 500
  lines — split into chained sub-PRs at execution time (`/chained-pr`), not decided here.

### What does it do? (observable behavior, not implementation)

- A user pastes an offer and clicks "Enviar" in the Visual UI. The request returns
  immediately (no LLM call, no blocking).
- Behind the scenes, applyr automatically deduplicates and extracts structured data
  (company/title/tech stack) from the pasted text — no manual step required.
- If the offer is a duplicate of an existing one, the UI shows that immediately, no
  further action needed from anyone.
- If it's new, the job stops in `PENDING_AGENT` and the UI shows "waiting for agent" —
  the same state `applyr doctor` already surfaces to an attended coding-agent session
  today, now also pushed live over SSE. Once the agent scores it and runs `applyr add
  --intake-id`, the job becomes `READY` and the UI updates live, no reload, no polling.
- If the deterministic steps fail (bad input, DB error), the UI shows the failure and a
  manual "Retry" button — never an automatic retry loop.
- `applyr autopilot` no longer exists as a separate command/process; `applyr ui` starts
  everything needed on its own.

### Acceptance criteria

- `[MUST]` WHEN a user submits the intake form (`POST /api/intake`) THE system SHALL
  create the `ui_intake` row and a paired `ui_jobs` row (`state='queued'`) in one
  transaction, and respond `201` without waiting for any pipeline step.
- `[MUST]` WHEN the same `raw_text` is submitted again within 10 seconds while the
  original intake row is still `pending` THE system SHALL NOT create a second
  intake/job pair — it SHALL return the existing pending row instead.
- `[MUST]` WHILE a job is `state='queued'` THE in-process worker SHALL claim it within
  its next poll tick (≤2s, and near-instantly via an in-process wake signal on the
  common path) and transition it toward `structuring`.
- `[MUST]` WHEN `structuring` finds labeled fields (`Empresa:`/`Company:`,
  `Puesto:`/`Título:`/`Cargo:`/`Position:`/`Role:`/`Rol:`, case-insensitive, ES/EN) THE
  system SHALL extract company/title from those labels and record
  `extraction_method="labeled"`.
- `[SHOULD]` WHEN no labeled fields are found THE system SHALL fall back to today's
  heuristic (first two non-blank lines) and record `extraction_method="heuristic"`.
- `[COULD]` WHERE a `Stack:`/`Tech:`/`Tecnologías:` label is present THE system SHALL
  capture it into `structured_data.tech_stack` as an informational hint for the agent —
  never used to auto-fill a score.
- `[MUST]` WHEN `structuring` produces a company that case-insensitively exact-matches
  an existing offer's company AND that offer's title also matches THE system SHALL
  transition the job to `state='duplicate'`, set `duplicate_of_offer_id`, and SHALL NOT
  proceed further.
- `[MUST]` WHEN `structuring` succeeds and no duplicate is found THE system SHALL
  transition the job to `state='pending_agent'` and broadcast an SSE event on
  `/api/events/enriched` carrying the job's `structured_data`.
- `[MUST]` WHILE a job is `state='pending_agent'` THE system SHALL NOT advance it on any
  timer or timeout — only an external `applyr add --intake-id <id>` call SHALL transition
  it, via a best-effort POST to a new internal endpoint.
- `[MUST]` WHEN `applyr add --intake-id <id>` succeeds THE system SHALL transition the
  paired job to `state='ready'` and broadcast the change over SSE.
- `[SHOULD]` WHEN `applyr add --intake-id <id>` fails (duplicate at CLI level, validation
  error) THE system SHALL transition the paired job to `state='failed'`,
  `failed_step='pending_agent'`, with the error message — best-effort, and SHALL NOT
  affect the CLI command's own exit code or output (ADR-013's non-blocking-instrumentation
  rule, carried forward).
- `[MUST]` WHEN a job is `state='failed'` (at `structuring` or `deduping`) THE user SHALL
  be able to call `POST /api/intake/{intake_id}/retry`, which resets it to
  `state='queued'`, clears `failed_step`/`error_message`, increments `retry_count`, and
  the worker SHALL reprocess it.
- `[MUST]` The system shall never automatically retry a failed job.
- `[MUST]` The system shall never invoke an LLM API from `applyr/ui/*` or the worker —
  reaffirms ADR-003 (verifiable: `grep -rn "openai\|anthropic" applyr/ui/` → no matches).
- `[MUST]` WHEN `applyr ui` starts THE system SHALL start the in-process worker
  automatically. THE `autopilot` subcommand SHALL NOT exist (removed from `cli.py` and
  its help text); `applyr/ui/autopilot.py` is deleted.
- `[MUST]` WHILE the worker restarts WHEN jobs were left in `queued`/`structuring` THE
  worker SHALL re-claim and reprocess them (crash-recoverable, idempotent re-run — both
  steps are pure functions of `raw_text`). Jobs left in `pending_agent` SHALL be left
  untouched (still correctly waiting for the agent, never silently lost or re-run).
- `[SHOULD]` Given the Visual UI's intake page is open, When a job's state changes, Then
  the UI reflects it via the SSE event, with no page reload and no polling for this data.
- `[WONT]` Automatic/headless completion of the `pending_agent` step without an attended
  agent session — explicitly out of scope (ADR-014, reaffirms ADR-003).
- `[WONT]` A swappable multi-provider `Agent` interface (Claude/OpenCode selectable at
  runtime) — explicitly out of scope (ADR-014 Decision 5; also on
  `docs/visual-ui/AGENTS.md`'s "Explicitly rejected" list).
- `[WONT]` Redis, Celery, or any process external to `applyr ui` — explicitly out of
  scope (ADR-014 Decision 4; `docs/visual-ui/AGENTS.md` invariant #4).

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/db.py` | MODIFY | v13→v14 migration: `ui_jobs` table + indexes, `SCHEMA_VERSION` bump |
| `applyr/ui/jobs.py` | CREATE | CRUD for `ui_jobs` (mirrors `intake.py`'s split): create paired with an intake row, get-by-intake-id, update-state, list-retryable |
| `applyr/intake.py` | MODIFY | `create_intake` gains the 10s idempotency guard |
| `applyr/ui/pipeline_worker.py` | CREATE | In-process asyncio worker: structuring extraction (labeled + heuristic patterns), dedupe-by-company query, state-machine driver, poll loop + wake signal |
| `applyr/ui/autopilot.py` | DELETE | Fully replaced by `pipeline_worker.py` |
| `applyr/ui/server.py` | MODIFY | Start/stop the worker as a background asyncio task on FastAPI startup/shutdown |
| `applyr/ui/api.py` | MODIFY | `POST /api/intake` creates the paired job + wakes the worker; `GET /api/intake` joins job state into the response; new `POST /api/intake/{id}/retry`; new internal `POST /api/internal/job-state`; extract shared `_broadcast_enriched()` helper (currently duplicated 3x); register `job.*` event types |
| `applyr/ui_events.py` | MODIFY | Add `notify_job_state()` best-effort CLI-side notifier (mirrors `notify_stage`); register `job.*` in `VALID_EVENT_TYPES` |
| `applyr/commands/core.py` | MODIFY | `applyr add --intake-id` calls `notify_job_state(..., state="ready")` on success / `"failed"` on the intake-linkage failure path — best-effort, non-blocking |
| `applyr/cli.py` | MODIFY | Remove the `autopilot` subcommand (dispatch branch + help text) |
| `applyr/ui/frontend/src/api/intake.ts` | MODIFY | Type for the joined job state; `retryJob()` call |
| `applyr/ui/frontend/src/features/intake/PendingIntakeList.tsx` | MODIFY | Render `job.state` per row (queued/structuring/pending_agent/duplicate/failed/ready); Retry button on `failed` |
| `applyr/ui/frontend/src/hooks/useApplyrEvents.ts` | MODIFY | Subscribe to `job.*` SSE events, update the intake list live |
| `tests/test_ui_jobs.py` | CREATE | Migration, idempotency guard, worker extraction/dedupe/state transitions, retry endpoint, SSE broadcast |
| `tests/test_ui_cli.py` | MODIFY | Remove any `autopilot` help-text/dispatch expectations |
| `docs/visual-ui/AGENTS.md` | MODIFY | Update invariant #3 ("Data flow for a new offer"), add a Status-log entry for this slice |

### Dependencies

- APIs/endpoints used or added: `POST /api/intake` (existing, extended), `GET /api/intake`
  (existing, extended), `POST /api/intake/{id}/retry` (new), `POST
  /api/internal/job-state` (new, internal-only, no compatibility guarantee — same
  treatment as `/api/internal/pipeline-stage`).
- DB tables: new `ui_jobs` (references `ui_intake.id`, `offers.id`); reads/writes
  `ui_intake`, `offers` (dedupe query only, read-only).
- Auth: none — matches every other endpoint in this codebase (local, single-user, no auth
  layer, per `docs/visual-ui/AGENTS.md` invariant #4).
- Reused: SSE transport (`_enriched_event_subscribers`, `/api/events/enriched`) from
  ADR-013; the CLI best-effort-notify pattern (`applyr/ui_events.py`) from ADR-013; the
  `applyr doctor` pull-mechanism (`_check_agent_responses`) stays as-is, unrelated to this
  push path.

### Explicit assumptions

- We assume the 10-second idempotency window is enough to catch a genuine double-click
  without blocking a deliberate re-paste of similar text minutes later → if too
  aggressive/lax in practice, the window is a named constant, trivial to retune later.
- We assume exact case-insensitive company+title match is a strict-enough duplicate
  definition for `structuring`'s dedupe step (mirrors `--company`'s existing definition
  used elsewhere in the CLI) → if it's too strict and misses near-duplicates, that's the
  same accepted limitation `applyr search --company` already has project-wide, not a new
  gap.
- We assume the worker's poll tick (2s) plus an immediate in-process wake signal on
  submit is enough to feel instant for a single local user → no load-testing planned,
  single-user local tool.

### Non-functional requirements

- Performance: worker claims a newly queued job within its next tick (≤2s worst case,
  near-instant via the wake signal on the common path — no measurable target beyond "same
  process, no network hop").
- Security: no new auth surface; `/api/internal/*` stays unauthenticated like its
  siblings — accepted, loopback-only threat model already established for this codebase.
- Data integrity: `ui_jobs.state` enforced via a SQLite `CHECK` constraint (same pattern
  as `_PIPELINE_STAGE_CHECK_SQL` in `db.py`), not just application-level validation.

### Edge cases / risks

- Worker process killed mid-`structuring` → job stuck in `structuring` until restart →
  mitigated by AC "crash-recoverable": the worker re-claims `queued`/`structuring` jobs on
  startup, safe because both steps are pure functions of `raw_text` (idempotent re-run).
- Label-pattern false positive (pasted text casually contains "Company:" mid-paragraph) →
  accepted risk; `extraction_method` stays visible so the agent knows to double-check, and
  `PENDING_AGENT` still requires the agent's real judgment regardless — `structured_data`
  is a hint, never authoritative (unchanged from AGENTS.md core principle #1).
- Two intake rows racing to claim the same job row → not a real risk: single asyncio task,
  single process, no concurrent workers by construction.
- `applyr add --intake-id`'s best-effort notification silently fails (UI backend down) →
  by design (ADR-013's non-blocking rule) — the CLI command still succeeds and
  `ui_intake`/`offers` are still correctly updated; only the `ui_jobs` row and the SSE
  push are stale until the next `GET /api/intake` poll on page load/reconnect.

### Task breakdown (execution order)

1. [x] `applyr/db.py`: v14 migration (`ui_jobs` table + indexes) + `applyr/ui/jobs.py` CRUD [M]
2. [x] `applyr/intake.py`: idempotency guard in `create_intake` [S]
3. [x] `applyr/ui/pipeline_worker.py`: structuring extraction + dedupe query + state-machine
   driver + poll loop + wake signal [L]
4. [x] `applyr/ui/api.py`: wire `POST /api/intake` to create the paired job + wake the worker;
   extend `GET /api/intake`; new retry endpoint; new internal job-state endpoint; extract
   `_broadcast_enriched()`; register `job.*` event types [L]
5. [x] `applyr/ui/server.py`: start/stop the worker task on the FastAPI lifecycle [S]
6. [x] `applyr/ui_events.py` + `applyr/commands/core.py`: `notify_job_state()`, wired into
   `applyr add --intake-id` [M]
7. [x] `applyr/cli.py` + delete `applyr/ui/autopilot.py`: remove the `autopilot` subcommand [S]
8. [ ] Frontend: `api/intake.ts` types + retry call, `PendingIntakeList.tsx` state rendering +
   Retry button, SSE subscription for `job.*` events [M]
9. [x] `tests/test_ui_jobs.py` (new) + `tests/test_ui_intake.py` idempotency tests
   (`tests/test_ui_cli.py` needed no changes — it never referenced `autopilot`) [L]
10. [ ] `docs/visual-ui/AGENTS.md`: update invariant #3, add Status-log entry [S]

**Progress (2026-08-31):** Tasks 1-7 + 9 (backend + backend tests) implemented and verified —
935/935 tests green, `/simplify-lean` run after every task (one real finding: a
`simplify-lean` pass on `server.py` introduced a bare-except-equivalent
`except (asyncio.CancelledError, Exception)`, caught and reverted to the narrow
`except asyncio.CancelledError` during review). Backend diff alone is ~780 lines,
already over the 500-line PR budget as predicted — this is "PR A" per the chained-PR
note above. Tasks 8 and 10 remain, to ship as separate chained PRs.

**PR budget note:** 15 files, likely 700-1000+ net lines — will exceed the 500-line
budget. Split at execution time via `/chained-pr` (e.g., PR A = tasks 1-7 + 9's backend
tests, PR B = task 8 + its frontend tests, PR C = task 10 docs) — the exact split is an
execution-time decision, not fixed here.

### Out of scope

- `[WONT]` Reversing ADR-003 (server-side LLM calls) — see ADR-014.
- `[WONT]` A swappable `Agent` provider interface — see ADR-014 Decision 5.
- `[WONT]` Redis/Celery/any external process — see ADR-014 Decision 4.
- `[WONT]` Improving `structuring`'s extraction beyond labeled-fields + heuristic fallback
  (e.g. NLP-based extraction) — labeled patterns are "this iteration's" improvement per
  the project owner's answer; anything beyond that is a future slice.
- `[WONT]` Editing/canceling a job once it reaches `pending_agent` from the UI — the only
  supported action there is the existing `applyr add --intake-id` path.
