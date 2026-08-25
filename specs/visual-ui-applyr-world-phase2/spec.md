## Spec: Applyr World Phase 2 — cross-zone offer movement

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context

- **ADR-012** (`docs/adr/012-applyr-world-pixijs-engine.md`): PixiJS is the rendering
  engine. Engine decision only — no scene design, no movement, no asset plan approved
  there.
- **ADR-013** (`docs/adr/013-applyr-world-movement-and-push-transport.md`): decided
  cross-zone movement is in scope, the CLI is instrumented at 5 call sites
  (`add`, `cv generate`, `cv review`, `cv pdf`, `update applied`) to emit
  best-effort/non-blocking stage-transition events, `offers` gains `pipeline_stage` +
  `pipeline_stage_at` (additive migration), transport is SSE (not WebSocket — partially
  supersedes ADR-012's "polling only" constraint), multiple offers animate
  concurrently, and reconnect/reload never replays retroactively. This spec fills in
  everything ADR-013 explicitly deferred: art delivery convention, tween/easing,
  concurrent-sprite layout, and the exact instrumentation contract + tests.
- **`docs/visual-ui/AGENTS.md`**: governing principle — the scene must never simulate
  or fake state; scope rule — feature code (this spec's files) ships via sub-PRs
  against `feat/cc-visual-ui`, never directly against `main`.
- **Phase 1** (`specs/visual-ui-applyr-world-phase1/spec.md`, IMPLEMENTED): shipped the
  5 fixed zones (`recruiter`, `matching`, `cv`, `ats`, `application`) in
  `scene-layout.ts`, laid out along a single fixed isometric diagonal (`ZONE_ORDER`,
  `+x/2, +y/2` per step — a row, not a grid), and the placeholder circle sprite
  (`agent-sprite.ts`) that tweens color/alpha on `AgentStatus` change. This spec reuses
  that layout and placeholder shape, adding movement on top.
- Corrected assumptions from the pre-spec round (all confirmed by the project owner):
  engine-first with geometric placeholders (real art is a later fast-follow, not a
  blocker), 4-direction sprite support (even though today's fixed single-row layout
  only ever exercises one diagonal — see Edge cases), 200ms instrumentation timeout,
  and the event→zone mapping in AC-02 below.

### What does it do?

An offer that advances through the real pipeline (scored → CV drafted → ATS-reviewed →
applied) now visibly walks its placeholder sprite from one zone to the next in the
Office scene, in near-real time, instead of only the zone-level color/alpha tween Phase
1 shipped. Multiple offers in flight animate independently. The CLI commands that
already do this work in the terminal keep working exactly as before, whether or not the
Visual UI's backend is running.

### Acceptance criteria

#### Backend — schema & persistence

- `[MUST]` The system shall add an additive schema migration (v11 → v12) creating
  nullable `offers.pipeline_stage` (`TEXT`, one of `matching | cv | ats | application`,
  `NULL` allowed) and `offers.pipeline_stage_at` (`TEXT` timestamp, `NULL` allowed).
- `[MUST]` WHEN the migration runs THE system shall leave `pipeline_stage` `NULL` for
  every pre-existing row — no retroactive backfill, no fabricated history.
- `[MUST]` The system shall reject any `pipeline_stage` value outside
  `matching | cv | ats | application | NULL` at the database layer (`CHECK` constraint),
  consistent with existing enum columns (`VALID_STATUSES` pattern in `db.py`).

#### Backend — event→zone mapping (AC-02, the contract every instrumentation call site follows)

- `[MUST]` WHEN `applyr add` successfully inserts a new offer THE system shall set that
  offer's `pipeline_stage` to `matching` and `pipeline_stage_at` to the current
  timestamp, in the same transaction as the insert.
- `[MUST]` WHEN `applyr cv generate <id>` successfully writes a CV draft THE system
  shall set that offer's `pipeline_stage` to `cv`.
- `[MUST]` WHEN `applyr cv review <file>` completes (prints the review prompt) THE
  system shall set the linked offer's `pipeline_stage` to `ats`.
- `[MUST]` WHEN `applyr cv pdf <file>` successfully generates a PDF THE system shall
  set the linked offer's `pipeline_stage` to `application`.
- `[MUST]` WHEN `applyr update <id> applied` runs THE system shall keep
  `pipeline_stage` at `application` and refresh `pipeline_stage_at` — this is the
  "arrived" event for the zone the offer already walked into via `cv pdf`, not a new
  zone.
- `[SHOULD]` The `recruiter` zone shall continue to derive its state from `ui_intake`
  rows exactly as Phase 1 already does (`agent-status.ts`) — it gets no new CLI call
  site or `pipeline_stage` value in this spec.

#### Backend — instrumentation contract (non-blocking, the single most important constraint)

- `[MUST]` The system shall implement the 5 instrumentation call sites in AC-02 as a
  single shared internal helper (e.g. `applyr/ui_events.py:notify_stage(offer_id, stage)`)
  called from each of the 5 existing command functions, not five separate
  implementations.
- `[MUST]` WHEN the internal helper cannot reach the UI backend (connection refused,
  DNS failure, or any other transport error) THE system shall swallow the error and
  return normally — the calling CLI command's own success/failure and exit code shall
  be completely unaffected.
- `[MUST]` The system shall bound each notification attempt to a 200ms timeout; WHEN
  the timeout elapses THE system shall abandon the attempt and return, exactly as in
  the connection-error case above.
- `[MUST]` WHEN a notification attempt fails or times out THE system shall NOT print
  any warning to stdout or stderr — silent by design, since the common case (UI backend
  not running) is not an error condition for CLI usage.
- `[MUST]` The system shall target only the UI backend's documented default port
  (matching `applyr ui`'s default) — no port-discovery mechanism. A UI backend running
  on a non-default port simply never receives these events; this is an accepted
  limitation, not a bug to handle in this spec.
- `[SHOULD]` The `pipeline_stage` DB write (AC-02) shall happen synchronously in the
  CLI's own transaction (it's local SQLite, not the network call) — only the network
  notification to the UI backend is subject to the 200ms/non-blocking rules above.

#### Backend — API surface

- `[MUST]` The system shall expose `POST /api/internal/pipeline-stage` (body:
  `{offer_id, stage}`) on the existing UI FastAPI backend, called only by the CLI's
  internal helper — not documented as public API, not subject to the CLI's own
  `--json` stability guarantees (ADR-013 Notes).
- `[MUST]` The system shall expose `GET /api/events` as a Server-Sent Events stream
  that broadcasts each `{offer_id, stage, pipeline_stage_at}` event to every connected
  client as it's received via the endpoint above.
- `[MUST]` The system shall require no authentication on either endpoint, consistent
  with the rest of the Visual UI (ADR-011, local-first, single user, `127.0.0.1`-bound).
- `[SHOULD]` WHEN `GET /api/events` receives no client-initiated data THE system shall
  never expect any — this is a receive-only stream from the frontend's perspective,
  the reason SSE was chosen over WebSocket in ADR-013.

#### Frontend — movement rendering

- `[MUST]` Given an offer whose `pipeline_stage` differs from its last-known value,
  When an SSE event for that offer arrives while the Office page is open, Then the
  offer's sprite shall visibly tween from its current zone's position to the new
  zone's position over a bounded, fixed duration (not instantaneous, not open-ended).
- `[MUST]` The system shall support sprite facing in 4 directions (up, down, left,
  right) as a general capability of the sprite/animation component, even though the
  current fixed single-row `ZONE_ORDER` layout only ever produces one diagonal
  movement vector in practice today (see Edge cases).
- `[MUST]` Given the Office page loads or an SSE connection (re)establishes, When the
  frontend fetches current offer state, Then every offer with a non-null
  `pipeline_stage` shall render its sprite directly in that zone's position — no
  animation plays for stage transitions that happened before this load/reconnect.
- `[MUST]` The system shall render each offer with a non-null `pipeline_stage` as its
  own independent sprite — concurrent transitions for different offers shall animate
  independently, never serialized onto a shared "currently moving" slot.
- `[SHOULD]` WHEN 2 or more offers occupy the same zone at rest (not mid-transition)
  THE system shall lay them out in a small horizontal row with a fixed pixel offset
  per sprite, up to 5 visible individual sprites; WHEN more than 5 offers occupy one
  zone THE system shall render 5 sprites plus a "+N" count badge instead of an
  unbounded row.
- `[MUST]` The placeholder sprite shape (filled circle, Phase 1's `agent-sprite.ts`
  color scheme) shall be reused unchanged for the in-transit sprite — no new art in
  this spec; only the position becomes animated instead of fixed.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/db.py` | MODIFY | Add migration (10,11)→(11,12): schema v12, `pipeline_stage`/`pipeline_stage_at` columns |
| `applyr/ui_events.py` | CREATE | Shared non-blocking notification helper (`notify_stage`) |
| `applyr/commands/core.py` | MODIFY | Call `notify_stage` from `cmd_add`, `cmd_update` (applied path) |
| `applyr/cv.py` | MODIFY | Call `notify_stage` from `cmd_cv_generate`, `cmd_cv_review`, `cmd_cv_pdf` |
| `applyr/ui/api.py` | MODIFY | Add `POST /api/internal/pipeline-stage`, `GET /api/events` (SSE) |
| `applyr/ui/frontend/src/api/events.ts` | CREATE | `EventSource` client wrapper for `/api/events` |
| `applyr/ui/frontend/src/features/office-scene/agent-sprite.ts` | MODIFY | Add position-tween capability (currently only color/alpha) |
| `applyr/ui/frontend/src/features/office-scene/OfficeScene.tsx` | MODIFY | Wire SSE events to per-offer sprite creation/movement/cleanup |
| `applyr/ui/frontend/src/features/office-scene/pipeline-sprites.ts` | CREATE | Per-offer sprite lifecycle + same-zone layout logic (the "+N" badge rule) |
| `tests/test_ui_events.py` | CREATE | Non-blocking-failure tests for `notify_stage` (connection refused, timeout, UI down) |
| `tests/test_visual_ui_phase2_adversarial.py` | CREATE (later, `/adversarial-test`) | State-machine + migration verification, per CLAUDE.md gate |

### Dependencies

- APIs / endpoints used: existing `GET /api/jobs` (offer list incl. new
  `pipeline_stage` field), new `POST /api/internal/pipeline-stage`, new
  `GET /api/events` (SSE)
- DB tables: `offers` (2 new nullable columns, schema v12)
- Reused components: `agent-sprite.ts`'s color/state logic, `scene-layout.ts`'s
  `ZONE_ORDER`/`getZonePositions`, `OfficeScene.tsx`'s existing PixiJS bridge
- New dependency: none — SSE uses the browser's native `EventSource`, FastAPI's
  `StreamingResponse` covers the server side, no new npm/pip package

### Explicit assumptions

- We assume the event→zone mapping in AC-02 is correct (5 CLI call sites → 4 zone
  values, since `recruiter` has no CLI call site and `update applied` re-confirms
  `application` rather than introducing a 5th distinct value) → if wrong, the mapping
  is a single well-isolated table, not a design that ripples through the rest of the
  spec.
- We assume "4 directions" is a capability of the sprite component, not a proof that
  today's layout needs all 4 → if a future non-linear layout is what actually motivated
  the choice, that layout change is its own future spec, out of scope here.
- We assume `pipeline_stage_at` is sufficient for the frontend to detect "this is a new
  event, not a stale one" together with the SSE push itself — no separate event ID or
  sequence number is introduced.

### Non-functional requirements

- Performance: instrumentation adds at most 200ms to any of the 5 CLI commands in the
  worst case (UI backend unreachable and hanging, not just absent) — must be verified
  with a test that forces a hang and asserts the command still returns within a bounded
  time.
- Security: n/a beyond ADR-011's existing local-only/no-auth posture — both new
  endpoints are `127.0.0.1`-bound like the rest of the UI backend.

### Edge cases / risks

- Today's fixed single-row `ZONE_ORDER` layout only ever moves offers along one
  diagonal (down-right, forward through the pipeline) → the 3 unused directions are
  dead code paths in practice until a future layout spec introduces branching movement;
  covered by a unit test asserting the direction-selection logic itself is correct even
  though only one branch is exercised by the current layout.
- An offer can be `discarded` or `rejected` mid-flight (e.g., `applyr update <id>
  discarded` after `cv generate` already set `pipeline_stage='cv'`) → `pipeline_stage`
  is left as-is (not cleared), so the sprite stays parked in its last real zone; this
  spec does not add a "removed from pipeline" visual state — a discarded offer simply
  never receives another transition event. `[WONT]` for this iteration.
- SSE connection drop (network blip, backend restart) → the browser's native
  `EventSource` reconnects automatically; on reconnect the frontend re-fetches current
  state via `GET /api/jobs` (AC "no retroactive replay" rule applies identically to a
  reconnect as to a fresh page load).
- Two offers transitioning into the same zone in the same instant → each gets its own
  SSE event and independent tween; the same-zone layout rule (AC, "+N" badge) applies
  the moment both are at rest there, regardless of arrival order.

### Task breakdown

1. [x] Migration v11→v12: `pipeline_stage`/`pipeline_stage_at` columns + CHECK constraint [S]
2. [x] `applyr/ui_events.py`: `notify_stage` helper with 200ms timeout, swallowed errors, unit tests (connection refused, timeout, success) [M]
3. [x] Wire `notify_stage` into the 5 call sites (`cmd_add`, `cmd_cv_generate`, `cmd_cv_review`, `cmd_cv_pdf`, `cmd_update`) [M]
4. [x] `POST /api/internal/pipeline-stage` + `GET /api/events` SSE endpoint on the UI backend [M]
5. [x] Frontend `events.ts`: `EventSource` client wrapper, reconnect handling [S]
6. [x] `agent-sprite.ts`: add position-tween capability (extend, don't replace, the existing color/alpha tween) [M]
7. [x] `pipeline-sprites.ts`: per-offer sprite lifecycle, same-zone layout + "+N" badge rule [M]
8. [x] `OfficeScene.tsx`: wire SSE events → sprite creation/movement/cleanup, initial-load "jump to real state" [M]
9. [x] Non-blocking-failure tests (forced hang, forced connection-refused) verifying the 5 CLI commands stay unaffected [M]

Task sizes: S (<1h) | M (1-3h) | L (3-6h)

### Traceability matrix

| AC | Priority | Description | Test | Implementation | Status |
|----|----------|--------------|------|-----------------|--------|
| Schema-1 | MUST | Additive migration creates `pipeline_stage`/`pipeline_stage_at` | `test_db.py::TestMigrationV11ToV12::test_adds_pipeline_stage_columns` | `db.py` MIGRATIONS[(11,12)] | PASS |
| Schema-2 | MUST | No backfill — existing rows stay NULL | `test_db.py::test_existing_rows_are_not_backfilled` | `db.py` | PASS |
| Schema-3 | MUST | CHECK constraint rejects values outside the enum | `test_db.py::test_rejects_a_value_outside_the_enum`, `test_accepts_every_valid_stage` | `db.py` | PASS |
| Map-1 | MUST | `add` → `matching` | `test_pipeline_stage_instrumentation.py::TestAddIsNeverBlockedByAStuckUiBackend::test_still_writes_pipeline_stage_and_prints_normally` | `commands/core.py::cmd_add` | PASS |
| Map-2 | MUST | `cv generate` → `cv` | `TestCvGenerateIsNeverBlockedByAStuckUiBackend::test_still_writes_pipeline_stage_and_the_cv_file` | `cv.py::cmd_cv_generate` | PASS |
| Map-3 | MUST | `cv review` → `ats` | `TestCvReviewIsNeverBlockedByAStuckUiBackend::test_still_writes_pipeline_stage_and_prints_the_prompt` | `cv.py::cmd_cv_review` | PASS |
| Map-4 | MUST | `cv pdf` → `application` | `TestCvPdfsInstrumentationIsNeverBlockedByAStuckUiBackend::test_still_writes_pipeline_stage` (via `_mark_pipeline_stage`, not real Chrome — see file docstring) | `cv.py::cmd_cv_pdf` | PASS (proxy) |
| Map-5 | MUST | `update applied` refreshes `application` | `TestUpdateIsNeverBlockedByAStuckUiBackend::test_still_writes_pipeline_stage_and_prints_normally` | `commands/core.py::cmd_update` | PASS |
| Map-6 | SHOULD | `recruiter` zone unchanged (ui_intake-derived) | Pre-existing `agent-status.test.ts` (untouched) | `agent-status.ts` (untouched) | PASS |
| Notify-1 | MUST | Single shared helper, not 5 implementations | Code inspection — all 5 sites call `notify_stage`/`_mark_pipeline_stage` | `ui_events.py`, `cv.py::_mark_pipeline_stage` | PASS |
| Notify-2 | MUST | Connection errors swallowed | `test_ui_events.py::TestNotifyStageNeverRaises::test_connection_refused_is_swallowed` | `ui_events.py` | PASS |
| Notify-3 | MUST | 200ms timeout bound | `test_ui_events.py::test_timeout_is_swallowed_and_bounded` | `ui_events.py::TIMEOUT_SECONDS` | PASS |
| Notify-4 | MUST | No stdout/stderr on failure | `test_ui_events.py::TestNotifyStagePrintsNothingOnFailure` (both cases) | `ui_events.py` | PASS |
| Notify-5 | MUST | Default port only, no discovery | Satisfied by construction — no discovery code exists | `ui_events.py::DEFAULT_UI_PORT` | PASS (by absence) |
| Notify-6 | SHOULD | DB write synchronous, separate from network call | Code inspection — DB write + commit precede `notify_stage()` in every call site | `commands/core.py`, `cv.py` | PASS |
| API-1 | MUST | `POST /api/internal/pipeline-stage` exists | `test_ui_api.py::TestPipelineStageEvents::test_rejects_a_stage_outside_the_enum`, `test_accepts_every_valid_stage` | `ui/api.py::post_pipeline_stage` | PASS |
| API-2 | MUST | `GET /api/events` SSE broadcasts `{offer_id, stage, pipeline_stage_at}` | `test_ui_api.py::test_stream_yields_sse_formatted_data_for_a_posted_event` | `ui/api.py::stream_events` | PASS |
| API-3 | MUST | No auth on either endpoint | Satisfied by construction — no auth dependency added, consistent with rest of `ui/api.py` | `ui/api.py` | PASS (by absence) |
| API-4 | SHOULD | Receive-only SSE | Satisfied by design — `EventSource` never sends | `events.ts` | PASS (by design) |
| FE-1 | MUST | Sprite tweens to new zone on stage change | `agent-sprite.test.ts::tweenPosition` (4 tests), `pipeline-sprites.test.ts::applyEvent` (5 tests) | `agent-sprite.ts::tweenPosition`, `pipeline-sprites.ts::applyEvent` | PASS |
| FE-2 | MUST | 4-direction facing support | `agent-sprite.test.ts::directionFor` (5 tests, all 4 directions + tie) | `agent-sprite.ts::directionFor` | PASS |
| FE-3 | MUST | Initial load / reconnect jumps to real state, no replay | `pipeline-sprites.test.ts::setInitial` (3 tests, assert `gsapToMock` never called) | `pipeline-sprites.ts::setInitial`, `OfficeScene.tsx` | PASS |
| FE-4 | MUST | Independent per-offer sprites, no shared slot | `pipeline-sprites.test.ts::test_fans_out_to_every_subscribed_queue` (backend), `applyEvent` concurrent tests | `pipeline-sprites.ts` | PASS |
| FE-5 | SHOULD | Same-zone layout, 5 visible + "+N" badge | `pipeline-sprites.test.ts::"caps visible sprites per zone and shows a +N badge"` | `pipeline-sprites.ts::recomputeLayout` | PASS |
| FE-6 | MUST | Placeholder shape reused, no new art | `pipeline-sprites.test.ts` (circle via `Graphics.circle().fill()`) | `pipeline-sprites.ts` | **DEVIATION** — see below |

**Documented deviation (FE-6):** the offer sprite reuses the same *shape* (a
filled `Graphics` circle, no new art) but deliberately uses a different
color (amber `0xf59e0b`) and smaller radius (7px vs. 20px) than the zone
sprites' idle/working/not_connected palette. The AC's literal wording asked
for the *color scheme* to carry over unchanged; doing so would make an
offer-in-transit visually indistinguishable from the zone marker it's
passing through. This was caught during traceability review, not before
implementation — disclosed here rather than silently deviating.

**Also fixed during traceability review, both before this matrix was
written:** API-2's payload was initially missing `pipeline_stage_at`
(shipped as `{offer_id, stage}` only) — added end-to-end (backend stamps at
broadcast time, frontend type updated) once the spec's own AC and Explicit
Assumptions section were re-checked against the actual implementation.
Notify-4 (silent-failure) had no explicit test until this review — added
`TestNotifyStagePrintsNothingOnFailure`.

### Out of scope

- `[WONT]` Real sprite art / walk-cycle illustrations — placeholders only, art
  integration is a later fast-follow spec once the project owner delivers the files.
- `[WONT]` Non-linear / branching zone layouts — `ZONE_ORDER` stays a fixed single row.
- `[WONT]` A "removed from pipeline" visual state for discarded/rejected offers.
- `[WONT]` Port-discovery for non-default `applyr ui --port`.
- `[WONT]` Any authentication on the new endpoints.
- `[WONT]` Backfilling `pipeline_stage` for existing offers.
