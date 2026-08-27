## Spec: Agent queue modal ("thought bubble")

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context
- Project constitution (`constitution.md`): backend rules only (Python/SQLite/CLI) — no
  frontend section exists yet. Nothing there constrains this feature.
- `docs/visual-ui/AGENTS.md`: backend binds loopback-only, CORS locked to the Vite dev
  origin — unaffected, this feature adds no new backend surface.
- Relevant spec: `specs/visual-ui-slice-3/spec.md` — introduced `AgentCard` /
  `deriveAgentStatuses` (Office + Agents page share one derivation, `variant` prop is
  presentation-only). This feature extends that same function, doesn't replace it.
- Relevant ADR: ADR-013 gave `cv`/`ats`/`application` real backing data via
  `offers.pipeline_stage` (see `types.ts` comment) — this feature reads that same column,
  adds no new one.
- No Engram decisions found for "agent queue modal" / "thought bubble".
- Session origin: user found the Agents page misleading (`agent-status.ts` only ever
  showed a single item labeled "Working" while a real backlog of 11 pending offers sat
  invisible) and asked for a way to see the full backlog per agent, with an eye toward a
  future iteration surfacing live per-agent activity (e.g. what the ATS agent is doing to
  a CV in real time) in the same surface.

### What does it do? (observable behavior, not implementation)
- Every `AgentCard` that has queued work (`state === "working"`) gets a clickable
  "thought bubble" affordance. Clicking it opens a modal listing every item currently
  backing that agent's status — not just the single one shown on the collapsed card.
- Recruiter's modal lists pending intake rows (raw pasted text, truncated, + received
  date). Matching's modal lists every pending offer (company, title, compatibility %,
  date). CV/ATS/Application's modals list every offer whose `pipeline_stage` matches
  that zone (same fields as Matching, minus the score being the reason it's there).
- Clicking a job row navigates to `/offers?jobId=<id>` and closes the modal. Intake rows are
  not clickable (no offer exists yet to navigate to).
- Read-only: no apply/discard/promote actions live in the modal. Existing flows
  (`/offers?jobId=<id>`, `applyr update`) remain the only way to act on an item.

### Acceptance criteria

- `[MUST]` WHEN an agent's `state` is `"working"` THE system SHALL render a
  thought-bubble trigger on its `AgentCard`.
- `[MUST]` WHEN an agent's `state` is `"idle"` THE system SHALL NOT render a
  thought-bubble trigger.
- `[MUST]` WHEN the thought-bubble trigger is clicked THE system SHALL open a modal
  listing every queue item for that agent, sourced from the same polled `jobs` /
  `pendingIntake` data already held by `useIntakeAndJobs` — no new API call.
- `[MUST]` The system shall sort Matching's and Recruiter's queue items by `created_at`
  descending (most recent first), matching the existing single-item selection logic so
  the first row always matches what the collapsed card already showed.
- `[MUST]` The system shall list CV/ATS/Application queue items filtered by
  `job.pipeline_stage === <zone>`, the same filter `pipelineZoneStatus` already uses for
  its count.
- `[MUST]` Given a job queue item, When clicked, Then the modal closes AND the app
  navigates to `/offers?jobId=<id>`.
- `[MUST]` Given an intake queue item, Then it renders as non-interactive text (no
  link) — no offer exists yet.
- `[SHOULD]` IF the queue becomes empty while the modal is open (item resolved/discarded
  from elsewhere during the 3s poll) THEN the system SHALL show an empty-state message
  inside the still-open modal rather than force-closing it.
- `[SHOULD]` The system shall truncate intake `raw_text` previews to 120 characters with
  an ellipsis, so one long paste can't blow out the modal's layout.
- `[COULD]` The system shall reuse one generic `AgentQueueModal` component (not 5
  bespoke ones) so the same surface is the natural extension point for a future
  live-activity feed (explicitly out of scope for this iteration — see below).
- `[WONT]` Live/streaming agent activity content (e.g. real-time ATS analysis of a CV as
  it happens) inside the modal — noted as the deliberate next step, not built now. The
  existing `/api/events` SSE stream (already powering Office's spatial bubbles) is the
  natural future data source; this iteration only shapes the modal so that swap doesn't
  require restructuring it.
- `[WONT]` Inline actions (apply/discard/promote) from within the modal.
- `[WONT]` Pagination — v1 renders the full list in a scrollable container; revisit only
  if real usage produces backlogs large enough to matter.

### Affected files
| File | Action | Reason |
|------|--------|--------|
| `applyr/ui/frontend/src/features/agents/types.ts` | MODIFY | Add `items` to every `"working"` `AgentStatus` variant; add `JobQueueItem`/`IntakeQueueItem` types |
| `applyr/ui/frontend/src/features/agents/agent-status.ts` | MODIFY | `deriveAgentStatuses` populates `items` (full sorted/filtered list) alongside the existing single-item summary fields |
| `applyr/ui/frontend/src/features/agents/agent-status.test.ts` | MODIFY | Existing `toEqual` assertions need the new `items` field; add coverage for list content/order/count |
| `applyr/ui/frontend/src/components/ui/dialog.tsx` | CREATE | shadcn/radix `Dialog` primitive (Root/Trigger/Content/Header/Title/Close) — none exists yet, `radix-ui` package is already a dependency |
| `applyr/ui/frontend/src/features/agents/AgentQueueModal.tsx` | CREATE | Reusable modal: renders the right row shape per `agentId`, empty state, close-on-navigate |
| `applyr/ui/frontend/src/features/agents/AgentCard.tsx` | MODIFY | Add thought-bubble trigger button (rendered only when `state === "working"`), wires up `AgentQueueModal` |
| `applyr/ui/frontend/src/pages/OffersPage.tsx` | MODIFY | Read `?jobId=` on mount to preselect `selectedJobId` — `OffersPage` has no `:id` route today (`App.tsx` only registers `offers`), it manages detail-vs-list via local state (`useState<number\|null>`), so a query param is the minimal way to deep-link into it from another page. No existing behavior changes when the param is absent. |
| `applyr/ui/frontend/src/features/office-scene/agent-sprite.test.ts` | MODIFY | Discovered during implementation: builds `AgentStatus` literals directly for sprite-behavior mocks, unrelated to this feature — needed `items: []` added to compile once `items` became required. Mechanical, no behavior change. |

### Dependencies
- APIs/endpoints used: none new. Reuses `GET /api/jobs` + `GET /api/intake?status=pending`
  already fetched by `useIntakeAndJobs` (3s poll).
- DB tables: `offers` (`pipeline_stage`, `compatibility_pct`, `status`, `created_at`),
  `intake` (`raw_text`, `created_at`) — read-only, no schema change.
- UI primitives: `radix-ui` (already a dependency, unified package — `import { Dialog }
  from "radix-ui"`, same pattern `badge.tsx` uses for `Slot`), `lucide-react` for the
  bubble icon (already a dependency), `react-router`'s `Link` for navigation.
- Reused components: `Card`, `Badge` (existing `AgentCard` styling stays as-is).

### Explicit assumptions
- We assume the thought-bubble trigger's visibility is fully derived from `state ===
  "working"` (no separate empty check needed) → true today because every `"working"`
  variant is only ever constructed when its backing collection is non-empty
  (`pendingIntake.length > 0`, `mostRecentPendingJob` exists, `count > 0`). If that
  invariant ever breaks, the modal component still defends with its own empty state
  (the `[SHOULD]` AC above), so the UI never shows a bubble with literally nothing behind it.
- We assume Recruiter's intake rows are genuinely not clickable in v1 (no `/intake/:id`
  page exists) → if that's wrong, tell me now rather than after implementation.

### Non-functional requirements
- Performance: no new network calls; modal renders from data already in memory. List
  container caps at a fixed max-height with internal scroll so a 50+ item backlog
  doesn't blow out the page layout.
- Accessibility: inherited for free from Radix `Dialog` — focus trap, `Escape` to close,
  `aria-modal`, labelled by `Dialog.Title`. Nothing custom to build.

### Edge cases / risks
- Long intake paste text → truncated to 120 chars (`[SHOULD]` AC above).
- Item disappears mid-view (discarded/applied elsewhere while modal open) → empty-state
  inside the modal, not an auto-close (`[SHOULD]` AC above) — avoids a jarring UX during
  the 3s poll window.
- Existing tests use `toEqual` with exact object shapes on every `AgentStatus` variant —
  adding `items` breaks them all until updated; task 3 below covers this explicitly so it
  isn't discovered as a surprise CI failure.

### Task breakdown (execution order)
1. [x] Extend `types.ts` — new `JobQueueItem`/`IntakeQueueItem` types, add `items` to every
   `"working"` `AgentStatus` variant. [S]
2. [x] Update `agent-status.ts` — populate `items` in `deriveAgentStatuses` (depends on 1). [S]
3. [x] Update `agent-status.test.ts` — fix broken `toEqual` assertions, add list-content/order
   coverage (depends on 2). [M]
4. [x] Create `components/ui/dialog.tsx` — Radix Dialog primitive, shadcn conventions,
   independent of 1-3. Required `React.forwardRef` on `DialogOverlay`/`DialogContent`
   (discovered via a real console warning during manual verification — Radix's
   `Presence` attaches a ref for exit-animation lifecycle; a plain function component
   can't receive one). [M]
5. [x] Create `AgentQueueModal.tsx` — consumes `items` from step 1's types + `dialog.tsx`
   from step 4. [M]
6. [x] Wire the thought-bubble trigger into `AgentCard.tsx` (depends on 5). [S]
7. [x] Manual verification — Playwright against the real dev server: bubble renders only
   on the one real "working" agent (Application/Join Aurora, since the pending queue was
   emptied earlier this session), modal opens with correct data, clicking the job item
   navigates to `/offers?jobId=166`, closes the modal, and renders the real offer detail.
   Zero console errors/warnings after the forwardRef fix. Screenshot saved. [S]

## Traceability Matrix

| AC ID | Priority | AC Description | Test File | Implementation File | Status |
|-------|----------|-----------------|-----------|----------------------|--------|
| AC-01 | [MUST] | Bubble trigger renders only when `state === "working"` | manual (Playwright, real data) | `AgentCard.tsx` | PASS |
| AC-02 | [MUST] | No trigger when `state === "idle"` | manual (Playwright — Recruiter/Matching/CV/ATS all Idle, no button) | `AgentCard.tsx` | PASS |
| AC-03 | [MUST] | Click opens modal listing every queue item, no new API call | manual (Playwright) + `agent-status.test.ts` (data shape) | `AgentQueueModal.tsx`, `agent-status.ts` | PASS |
| AC-04 | [MUST] | Matching/Recruiter items sorted `created_at` desc | `agent-status.test.ts` — "queue lists every pending offer, most recent first" / "...intake row, most recent first" | `agent-status.ts` | PASS |
| AC-05 | [MUST] | CV/ATS/Application items filtered by `pipeline_stage` | `agent-status.test.ts` — "report working with the real count of offers in that stage" | `agent-status.ts` | PASS |
| AC-06 | [MUST] | Click job item closes modal + navigates to `/offers?jobId=<id>` | manual (Playwright — verified URL + rendered detail) | `AgentQueueModal.tsx`, `OffersPage.tsx` | PASS |
| AC-07 | [MUST] | Intake items render non-interactive | code inspection (`AgentQueueModal.tsx` renders `<li>`, not `<Link>`, for intake rows) — not exercised live (no pending intake existed at verification time) | `AgentQueueModal.tsx` | PASS (untested live) |
| AC-08 | [SHOULD] | Empty queue mid-view shows empty state, doesn't force-close | code inspection (`items.length === 0` branch in `AgentQueueModal.tsx`) | `AgentQueueModal.tsx` | PASS (untested live) |
| AC-09 | [SHOULD] | Intake preview truncated to 120 chars | `agent-status.test.ts` — "truncates long previews" | `agent-status.ts` | PASS |

AC-07/AC-08 aren't exercised against live data (no pending intake, and reproducing the
mid-view-empty race requires timing a manual edit against the 3s poll) — logic is
straightforward and covered by code inspection; flag if real usage surfaces a gap.

## Drift check
- No functions/endpoints exist outside the spec's scope.
- One deviation from the original spec, corrected in-flight and documented above: the
  spec assumed a `/offers/:id` route existed; it doesn't. Fixed by adding `?jobId=`
  query-param support to `OffersPage.tsx` instead (see Affected files table).
- One file touched that wasn't in the original spec: `agent-sprite.test.ts` (mechanical
  fixture fix, unrelated to this feature's behavior — documented in Affected files).
- Pre-existing, unrelated: 23 vitest failures in `office-scene/*` (agent-sprite,
  pipeline-sprites, scene-layout, scene-scenery, textures) — confirmed via `git stash`
  to already fail identically on the branch tip (`7eabc69`) before this feature touched
  anything. Out of scope for this spec; not fixed here.

## Out of scope
- `[WONT]` Live/streaming per-agent activity content (documented above as the deliberate
  next step once there's real data to show).
- `[WONT]` Inline actions from the modal.
- `[WONT]` Pagination.
- `[WONT]` A dedicated intake detail page/route (`/intake/:id`) — would be required to
  make intake rows clickable; not requested.
