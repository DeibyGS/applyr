## Spec: Visual UI — Offers page (Slice 4)

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context
- Project constitution (`docs/visual-ui/AGENTS.md`): engine never changes (read-only
  against `applyr/db.py` via the existing `GET /api/jobs`), no WebSocket/global store,
  feature-based frontend structure, `api/` is the only fetch boundary, pure logic lives
  separate from components for Vitest testability, PR base = `feat/cc-visual-ui`.
- Relevant ADRs: ADR-011 (Visual UI as optional additive interface) — no new
  constraints for this slice beyond what's already true of the frontend package.
- Engram decisions: `mem_search` for "offers page kanban filter sort visual ui" →
  no prior decisions found. Nothing to reconcile.
- Corrected assumptions from Step 2: all 9 assumptions presented to the user were
  confirmed as-is (user replied "sigue" — proceed). Two of them fix concrete
  implementation choices not otherwise specified and are treated as binding for this
  spec: status filter is single-select (`All` or one status, mirrors CLI
  `applyr list --status S`), score filter is a single minimum threshold (mirrors CLI
  `applyr pipeline --min-score N`).

### What does it do? (observable behavior, not implementation)
Replaces the `ComingSoon` stub at `/offers` with a real, read-only page showing every
offer from the existing `GET /api/jobs` data (already polled by `useIntakeAndJobs`).
Users can toggle between a **List** view (filterable by status/work_mode, filterable by
minimum score, sortable by date or score) and a **Kanban** view (columns per real
status, same filtered set as List). Clicking any offer in either view opens the
existing `JobDetail` panel. No data is ever mutated from this page.

### Acceptance criteria

- `[MUST]` Given a user navigates to `/offers`, When the page loads, Then it shows
  real offer data (not `ComingSoon`), defaulting to List view, sorted by date
  descending (matches existing backend order).
- `[MUST]` Given List view, When the user picks a status filter value, Then only jobs
  with that exact `status` are shown; default is "All" (no status filter applied).
- `[MUST]` Given List view, When the user picks a work_mode filter value, Then only
  jobs with that exact `work_mode` are shown; default is "All".
- `[MUST]` Given List view, When the user enters a minimum score, Then only jobs with
  `compatibility_pct >= entered value` are shown; empty/0 means no score filter.
- `[MUST]` The system shall combine all active filters with AND logic (status AND
  work_mode AND score-minimum apply simultaneously, never OR).
- `[MUST]` Given List view, When the user picks Date or Score as the sort field, Then
  jobs are ordered accordingly, descending by default; clicking the already-active
  sort field again reverses direction.
- `[MUST]` Given the user switches to Kanban view, Then jobs are grouped into columns
  by the 7 real `OFFER_STATUSES` values (reusing `groupByStatus`, not a new status
  list), using the SAME filtered set the List view currently shows (filters carry
  over across the view toggle; the toggle changes presentation only).
- `[MUST]` Given Kanban view, Then columns are strictly read-only: no drag-and-drop,
  no status mutation, no write call of any kind.
- `[MUST]` Given either view, When the user clicks a job card, Then the existing
  `JobDetail` panel opens via the existing `useSelectedJob` hook; the panel's "back"
  action returns to the same view/filter/sort state the user had before opening it
  (state lives in the parent page component and outlives `selectedJobId` changes).
- `[MUST]` Given no jobs match the active filters, Then the view shows an empty-state
  message distinct from the "no jobs exist at all" case (e.g. "No offers match these
  filters." vs. the existing `JobList` "No jobs yet.").
- `[SHOULD]` Given the user navigates away from `/offers` and back, Then view/filter/
  sort state resets to defaults — intentionally not persisted (no global store, no
  URL query params in this slice).
- `[MUST]` The system shall NOT introduce any new backend endpoint or modify
  `GET /api/jobs` in any way.
- `[MUST]` The system shall NOT add any new npm dependency — all controls (view
  toggle, filter pills, sort buttons, score input) are built from the existing
  `Button`/`Input` primitives in `components/ui/`.
- `[MUST]` Filter/sort/grouping keyboard and screen-reader behavior shall match the
  existing accessible patterns already in `JobCard`/`Button` (native `<button>`
  semantics, visible focus ring) — no new accessibility regressions on a page that
  previously passed the project's WCAG AA contrast pass.
- `[SHOULD]` Pure filter/sort logic (`filterJobs`, `sortJobs`) shall be unit-tested in
  Vitest, colocated next to the implementation per the locked frontend structure.
- `[WONT]` No drag-and-drop between Kanban columns (page is read-only by design).
- `[WONT]` No URL query-param persistence of filters/view (`[SHOULD]` above already
  says state does not survive navigation — a follow-up slice can add this later if a
  real need shows up).
- `[WONT]` No new backend `/api/stats`-style aggregation endpoint — all filtering/
  sorting is client-side over the existing unpaginated `GET /api/jobs` payload.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/ui/frontend/src/features/jobs/offer-filters.ts` | CREATE | Pure `filterJobs`/`sortJobs` functions + `OfferFilters`/`SortField`/`SortDirection` types |
| `applyr/ui/frontend/src/features/jobs/offer-filters.test.ts` | CREATE | Vitest coverage for filter/sort pure logic |
| `applyr/ui/frontend/src/features/jobs/OffersToolbar.tsx` | CREATE | View toggle (List/Kanban) + status/work_mode/score filters + sort controls |
| `applyr/ui/frontend/src/features/jobs/KanbanBoard.tsx` | CREATE | Read-only column layout over `groupByStatus`, reuses `JobCard` |
| `applyr/ui/frontend/src/pages/OffersPage.tsx` | MODIFY | Replace `ComingSoon` stub with real page wiring toolbar + List/Kanban + `JobDetail` |
| `specs/visual-ui-slice-4-offers/spec.md` | MODIFY | Traceability matrix + status update once implemented |
| `docs/visual-ui/AGENTS.md` | MODIFY | Append Slice 4 entry to the Status section, same pattern as slices 1-3 |

### Dependencies
- APIs / endpoints used: `GET /api/jobs` (existing, unmodified), `GET /api/jobs/{id}`
  (existing, via `useSelectedJob`), `GET /api/config` (existing, via `useThresholds`).
- DB tables: none touched directly — read-only through the existing endpoints.
- Reused components/hooks: `useIntakeAndJobs`, `useThresholds`, `useSelectedJob`,
  `JobList`, `JobCard`, `JobDetail`, `groupByStatus`/`OFFER_STATUSES`, `Button`,
  `Input`, `Card`, `Badge`.
- No new dependencies (confirmed as a `[MUST]` AC above).

### Explicit assumptions
- We assume status filter is single-select (`All` or exactly one status) → if the
  user later wants multi-status selection (e.g. "pending + applied" simultaneously),
  that's a follow-up change to `OfferFilters.status` from `string | null` to
  `string[]`, done as its own small PR, not retrofitted silently here.
- We assume score filter is a single minimum threshold, not a range → mirrors the
  existing CLI mental model (`applyr pipeline --min-score N`); a max-score ceiling can
  be added later if a real need appears.
- We assume `compatibility_pct` is always a number (per `JobSummary` type, never
  null) → no null-guard needed in `filterJobs`.

### Non-functional requirements
- Performance: filtering/sorting ~245 real offers client-side must stay imperceptible
  (<16ms per keystroke/click) — trivial at this scale for `Array.filter`/`.sort`, no
  memoization required, but avoid re-fetching on every filter change (filters operate
  on the already-polled `jobs` array from `useIntakeAndJobs`, not a new network call).
- Accessibility: WCAG AA already verified for the palette (Slice 2); new controls must
  use native `<button>`/`<input>` elements (already true of `components/ui/*`) with
  visible focus states — no new custom widgets that bypass keyboard navigation.

### Edge cases / risks
- Zero jobs match filters → distinct empty-state message (AC above), not a blank
  screen that reads as broken.
- User applies a filter, then opens a job detail, then hits back → filter state must
  survive (covered by the "state lives in parent" AC) — the main risk this spec
  guards against, since `useSelectedJob`'s existing pattern in Office/Archive doesn't
  need to preserve sibling state today (those pages have no filters to lose).
- Kanban view with a status that has zero jobs → column still renders with a "0"
  count and no cards, consistent with how `ArchivePage` already renders empty
  sections (`grouped[status].length` can be 0 there today).

### Task breakdown (execution order)
1. `offer-filters.ts` + `offer-filters.test.ts` — pure types + `filterJobs`/`sortJobs`, independently verifiable via Vitest before any UI exists [S]
2. `OffersToolbar.tsx` — view toggle + filter/sort controls, wired to local state only (no page integration yet) [M]
3. `KanbanBoard.tsx` — column layout via `groupByStatus`, reuses `JobCard`/`JobList` empty-state pattern [S]
4. `OffersPage.tsx` rewrite — wires toolbar + `filterJobs`/`sortJobs` + List/Kanban toggle + `JobDetail` via `useSelectedJob`, empty states [M]
5. Manual verification against real data (245 offers) + traceability matrix + `docs/visual-ui/AGENTS.md` Status update [S]

Task sizes: S (<1h) | M (1-3h)

### Out of scope
- `[WONT]` Drag-and-drop status changes from Kanban.
- `[WONT]` URL query-param persistence of filter/view state.
- `[WONT]` Multi-select status filter.
- `[WONT]` Any backend change.

### Scope amendment (discovered during Task 5 visual verification)

User feedback while reviewing the live page: `OfficePage.tsx` still rendered the full,
unfiltered `Jobs (N)` / `JobList` at the bottom — a duplication now that Offers owns
job browsing. Fixed in the same PR as a small, low-risk, directly-caused cleanup (not
a separate slice): removed the `JobList`/`JobDetail`/`useSelectedJob` section from
`OfficePage.tsx`; Office now shows only the header, `AgentRow`, and the
`IntakeForm`/`PendingIntakeList` column (agent status + intake queue — no offer
browsing). `useIntakeAndJobs`'s `jobs` array is still consumed by
`deriveAgentStatuses` for agent-status derivation, just no longer rendered as a list.
Pure deletion, no new logic → `/simplify-lean` skipped per project convention. Added
to "Affected files" retroactively below.

| File | Action | Reason |
|------|--------|--------|
| `applyr/ui/frontend/src/pages/OfficePage.tsx` | MODIFY | Remove duplicated full job list now that `/offers` owns job browsing (user feedback) |

## Traceability Matrix

| AC | Priority | Description | Verification | Status |
|----|----------|--------------|---------------|--------|
| AC-01 | MUST | `/offers` loads real data, defaults List, sorted date desc | `OffersPage.tsx` useState defaults; curl `/offers` → 200; manual visual confirm by user | PASS |
| AC-02 | MUST | Status filter, exact match, default All | `offer-filters.test.ts` "filters by exact status" | PASS |
| AC-03 | MUST | Work_mode filter, exact match, default All | `offer-filters.test.ts` "filters by exact work_mode" | PASS |
| AC-04 | MUST | Min-score filter, inclusive | `offer-filters.test.ts` "filters by minimum score, inclusive" | PASS |
| AC-05 | MUST | Filters combine with AND | `offer-filters.test.ts` "combines active filters with AND logic" | PASS |
| AC-06 | MUST | Sort by date/score, direction toggle on re-click | `offer-filters.test.ts` 4 sort tests + `OffersPage.handleSortChange` code review + manual visual confirm | PASS |
| AC-07 | MUST | Kanban uses same filtered set as List, reuses `groupByStatus` | Code review: `KanbanBoard` receives `visibleJobs` (already filtered/sorted) from `OffersPage` | PASS |
| AC-08 | MUST | Kanban strictly read-only | Code review: `KanbanBoard.tsx` has no drag handlers, no write calls | PASS |
| AC-09 | MUST | Detail panel preserves view/filter/sort state on back | Code review: state lives in `OffersPage`, outlives `selectedJobId`; manual visual confirm by user | PASS |
| AC-10 | MUST | Distinct empty-state message for "no matches" vs "no jobs" | Code review: `hasActiveFilters` conditional message in `OffersPage.tsx` | PASS |
| AC-11 | SHOULD | No persistence across navigation | Code review: local `useState` only, no storage/URL params | PASS |
| AC-12 | MUST | No new backend endpoint | `git diff feat/cc-visual-ui --stat` → zero backend files touched | PASS |
| AC-13 | MUST | No new npm dependency | `git diff feat/cc-visual-ui --stat` → zero `package.json` changes | PASS |
| AC-14 | MUST | Accessible native controls, no regressions | Code review: `Button`/`Input` primitives only in `OffersToolbar`/`KanbanBoard` | PASS |
| AC-15 | SHOULD | Vitest coverage for pure filter/sort logic | `offer-filters.test.ts`, 10/10 passing | PASS |

Full suite: 23/23 Vitest tests passing (10 new in `offer-filters.test.ts`, 13 pre-existing
unchanged), `tsc --noEmit` clean. Manually verified against real data (246 real offers,
5 of 7 statuses populated) via local backend+frontend dev servers; user confirmed
"funcionalmente está bien" after reviewing `/offers` live, and separately flagged the
Office duplication now fixed above. `/simplify-lean` ran twice (offer-filters.ts/test.ts;
OffersToolbar.tsx/KanbanBoard.tsx/OffersPage.tsx) — both passes returned "no changes
needed".
