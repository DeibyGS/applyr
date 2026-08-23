## Spec: Visual UI — Interviews page (Slice 7)

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context
- Project constitution (`docs/visual-ui/AGENTS.md`): engine never changes — reuse
  existing `GET /api/jobs` data (already polled by `useIntakeAndJobs`), never
  reimplement it. No WebSocket, no new backend infra. `api/` is the only fetch
  boundary. Feature-based structure, pure logic separate from components for Vitest
  testability. PR base = `feat/cc-visual-ui`.
- Relevant ADRs: ADR-011 (Visual UI as optional additive interface) — no new
  constraints.
- Prior deferred decision (Slice 3, `docs/visual-ui/AGENTS.md`): "Interviews shows
  specific copy (applyr has no interview-scheduling date/time field, only
  `status == 'in_process'` as a proxy — never fabricate a schedule)." This slice
  resolves that deferral.
- Engram: no prior decisions found for "interviews page in_process visual ui".
- Pre-spec question answers (binding for this spec):
  1. **Scope decision (the blocker from Slice 3): proxy-only.** No schema change, no
     new DB columns for scheduling. The page shows offers where
     `status == 'in_process'`, nothing more — same honest "no scheduling data yet"
     framing the current `ComingSoon` stub already uses, now as a real filtered list
     instead of a stub message.
  2. Sort = same order `GET /api/jobs` already returns (`created_at DESC`) — no new
     sort logic, filtering preserves the existing order.
  3. Layout = flat list (no grouping by company or anything else) — same pattern
     `ArchivePage` uses per-status, applied to a single status here.

### What does it do? (observable behavior, not implementation)
Replaces the `ComingSoon` stub at `/interviews` with a real, read-only page showing
every offer where `status == 'in_process'`, using the already-polled `GET /api/jobs`
data (via `useIntakeAndJobs`, same as Offers/Archive) — no new backend endpoint.
Clicking an offer opens the existing `JobDetail` panel. No data is ever mutated from
this page. Given applyr has no interview-scheduling date/time field, the page shows
only what's real (title, company, score, status) — never a fabricated schedule.

### Acceptance criteria

- `[MUST]` Given a user navigates to `/interviews`, When the page loads, Then it
  shows only offers with `status == 'in_process'`, in the same order `GET /api/jobs`
  already returns them (`created_at DESC`) — no client-side re-sort.
- `[MUST]` The system shall NOT introduce any new backend endpoint or modify
  `GET /api/jobs` in any way — filtering happens entirely client-side over the
  already-polled `jobs` array from `useIntakeAndJobs`.
- `[MUST]` Given zero offers have `status == 'in_process'`, Then the page shows an
  empty-state message distinct from a broken/blank page (e.g. "No offers currently
  in interview stage.").
- `[MUST]` Given the user clicks an offer card, Then the existing `JobDetail` panel
  opens via the existing `useSelectedJob` hook, same pattern `Offers`/`Archive`
  already use.
- `[MUST]` The pure filtering logic (`filterInProcess`) shall live in its own file
  separate from the page component, unit-tested in Vitest — same discipline
  `offer-filters.ts`/`group-by-status.ts` already established in prior slices.
- `[MUST]` The system shall NOT add any new npm dependency — built entirely from
  existing `JobList`/`JobCard`/`JobDetail` components.
- `[MUST]` The system shall NOT display or imply any interview date, time, or
  scheduling detail that doesn't exist in the data — the honest "no scheduling data
  yet" framing from the current stub carries forward as page copy (e.g. a subtitle),
  not silently dropped now that there's a real list to show.
- `[WONT]` No interview date/time/scheduling fields — this is the explicit scope
  decision from the pre-spec question; a schema change for real scheduling data is a
  separate, future decision with its own spec (higher cost of reversal — DB
  migration).
- `[WONT]` No grouping (e.g. by company) — flat list only, per the pre-spec answer.
- `[WONT]` No new sort control — inherits `GET /api/jobs`' existing order as-is.
- `[WONT]` Any write/mutation capability.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/ui/frontend/src/features/jobs/filter-in-process.ts` | CREATE | Pure `filterInProcess(jobs)` function |
| `applyr/ui/frontend/src/features/jobs/filter-in-process.test.ts` | CREATE | Vitest coverage for the pure filter |
| `applyr/ui/frontend/src/pages/InterviewsPage.tsx` | MODIFY | Replace `ComingSoon` stub with real filtered list + `JobDetail` |
| `specs/visual-ui-slice-7-interviews/spec.md` | MODIFY | Traceability matrix + status update once implemented |
| `docs/visual-ui/AGENTS.md` | MODIFY | Append Slice 7 entry to the Status section |

### Dependencies
- APIs / endpoints used: `GET /api/jobs` (existing, unmodified, via
  `useIntakeAndJobs`), `GET /api/jobs/{id}` (existing, via `useSelectedJob`).
- DB tables: none touched directly.
- Reused components/hooks: `useIntakeAndJobs`, `useSelectedJob`, `useThresholds`,
  `JobList`, `JobCard`, `JobDetail`.
- No new dependencies.

### Explicit assumptions
- We assume "in interview stage" means exactly `status == 'in_process'`, the same
  single value `applyr`'s CLI funnel (`cmd_stats`) already counts as `interview` —
  no broader interpretation (e.g. also including `waiting`) is introduced here.
- We assume the empty state and "no scheduling data" copy can reuse language close
  to the current `ComingSoon` stub's existing text, rather than inventing new
  copy — keeps the honest framing consistent across the transition from stub to
  real page.

### Non-functional requirements
- Performance: filtering an already-fetched, already-small (in-process offers are a
  small subset of the full set) array client-side is trivially fast, no
  memoization needed.
- Accessibility: reuses `JobList`/`JobCard`/`JobDetail`, which already passed the
  project's WCAG AA contrast pass — no new custom widgets introduced.

### Edge cases / risks
- Zero in-process offers → distinct empty-state message (AC above), not a blank
  screen that reads as broken — same risk `OffersPage`'s spec already flagged and
  solved for its own empty-filter case.
- User has offers with `status == 'in_process'` but incomplete data (missing
  `work_mode`, `location`, etc.) — already handled by the existing `JobCard`/
  `JobDetail` components (no new null-handling needed here).

### Task breakdown (execution order)
1. [x] `filter-in-process.ts` + `filter-in-process.test.ts` — pure function,
   independently verifiable via Vitest before any UI exists [S]
2. [x] `InterviewsPage.tsx` rewrite — wires `useIntakeAndJobs` + `filterInProcess` +
   `JobList`/`JobDetail` via `useSelectedJob`, empty state, honest subtitle copy [S]
3. [x] Manual verification against real data + traceability matrix + `docs/visual-ui/
   AGENTS.md` Status update [S]

Task sizes: S (<1h)

### Out of scope
- `[WONT]` Interview date/time/scheduling data or schema changes.
- `[WONT]` Grouping by company or anything else.
- `[WONT]` New sort control.
- `[WONT]` Any backend change.

## Traceability Matrix

| AC | Priority | Description | Verification | Status |
|----|----------|--------------|---------------|--------|
| AC-01 | MUST | Shows only status=='in_process', existing GET /api/jobs order | `filter-in-process.test.ts` "keeps only..." + "preserves the input order" | PASS |
| AC-02 | MUST | No new backend endpoint, no GET /api/jobs modification | `git diff --stat` — zero backend files touched | PASS |
| AC-03 | MUST | Distinct empty-state message when zero in-process offers | `InterviewsPage.tsx` conditional; manually confirmed live (user's real DB has 0 in-process offers right now) | PASS |
| AC-04 | MUST | Clicking a card opens JobDetail via useSelectedJob | Code review: identical pattern to `ArchivePage.tsx`, unchanged `useSelectedJob` | PASS |
| AC-05 | MUST | Pure filter logic isolated + unit-tested | `filter-in-process.ts` + `filter-in-process.test.ts`, 4/4 passing | PASS |
| AC-06 | MUST | No new npm dependency | `git diff --stat` — no `package.json` change | PASS |
| AC-07 | MUST | No fabricated interview date/time, honest subtitle copy | `InterviewsPage.tsx` header text: "applyr doesn't track interview dates or times..." | PASS |

Full suite: 35/35 Vitest passing (4 new in `filter-in-process.test.ts`), `tsc --noEmit`
clean. No backend changes, so no new Python tests. Manually verified against the
user's real 246-offer database via curl (`GET /api/jobs`): 0 offers currently have
`status == 'in_process'`, so the live page renders its empty state, which is the
correct and honest behavior for this data — not a bug. `/interviews` route confirmed
reachable (200) via local dev server. Could NOT visually verify rendering in a
browser — no browser-driving/screenshot tool available in this session, disclosed
explicitly rather than assumed. `/simplify-lean` ran once, returned "no changes
needed".
