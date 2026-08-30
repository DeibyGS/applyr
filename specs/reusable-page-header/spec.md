## Spec: Reusable PageHeader with conditional KPI chips

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context
- Project constitution (`constitution.md`): parameterized SQL only, no DB access
  outside `db.py`/`get_conn()`, constants in `constants.py`, `--json` output keys
  never renamed/removed, tests+code same commit, PR budget 500 lines.
- `AGENTS.md`: UI lives under `applyr/ui/frontend/src`; the FastAPI layer
  (`applyr/ui/api.py`) is a thin wrapper that reuses `commands/` payload builders,
  never reimplements aggregation SQL there.
- `_trends_payload` (commands/analytics.py:717-767) establishes the existing,
  already-shipped convention for "when did this application happen":
  `COALESCE(date_applied, date_received)` — NOT `created_at`. The new Analytics
  header KPIs must follow this same convention so their numbers agree with the
  existing Trend chart, rather than introducing a second, disagreeing definition
  of "applied date."
- `cv_master.py`'s `inspect_cv_master(text) -> CvMasterReport` (`filled: bool`,
  `placeholder_sections: tuple[str,...]`, `content_words: int`, `.reason`
  property) and `cv.py`'s `get_cv_master_path()` already implement everything
  needed for the Settings KPI — this spec wires them into a new endpoint, it does
  not reimplement CV-master inspection.
- `OfficeHeader.tsx` (features/office/OfficeHeader.tsx) is the existing precedent
  this spec generalizes: title+subtitle on the left, a row of `StatBadge` chips
  (bordered pill, bold value + muted label) on the right. It currently uses
  `text-xl` for the title while Offers/Interviews/Analytics/Settings all use
  `text-2xl` — one of the inconsistencies this spec fixes.
- Engram: no prior decisions found for a shared page header component.
- Corrected assumptions from Step 2 (user confirmed 2026-08-30): Analytics KPIs
  use `date_applied`/`date_received` (not `created_at`) and need NO new backend
  endpoint (derivable from data already fetched via `getStats`/`getTrends`); only
  the CV Master KPI is clickable in this iteration; Interview KPIs are limited to
  "waiting" (in_process) and "success" (offer) — no "unsuccessful" KPI, since
  applyr has no status-history table and a `rejected` offer cannot be reliably
  attributed to having reached interview stage or not.

### What does it do? (observable behavior, not implementation)
- A single `PageHeader` component renders the title/subtitle + an optional row
  of KPI chips, used identically by Office, Offers, Interviews, Analytics, and
  Settings — replacing five different ad hoc header markups with one.
- Office keeps its existing 2 chips (Pending, Agents active), migrated into the
  shared component with no behavior change.
- Interviews gains 2 new chips: Waiting, Success — computed client-side from data
  the page already fetches.
- Analytics gains 3 new chips: Applied (total), This week, This month — computed
  from `stats.funnel.applied` (already fetched) and `getTrends` week/month rows
  (already available via existing endpoints), using the same date convention as
  the Trend chart.
- Settings gains 1 new chip: CV Master status (OK/warning/missing, with word
  count when OK). It is visibly clickable (hover state + pointer cursor + a
  small affordance icon) and opens a modal showing the full CV Master content,
  rendered as markdown.
- Offers keeps title+subtitle only, no chips (none requested) — still migrates
  to `PageHeader` for visual consistency.

### Acceptance criteria

#### Shared component
- `[MUST]` The system shall provide one `PageHeader` component accepting
  `title`, `description` (or subtitle content), and an optional list of chip
  definitions (`{ label, value, tone?, onClick? }`).
- `[MUST]` All 5 pages (Office, Offers, Interviews, Analytics, Settings) shall
  render their header via `PageHeader` — no page keeps a bespoke `<header>`
  block.
- `[MUST]` The title shall render at a single consistent size across all 5 pages
  (`text-2xl`, matching the current majority — Office's chip row is unaffected,
  only its title size changes).
- `[MUST]` A chip with no `onClick` shall render as a non-interactive badge
  (current `StatBadge` visual, unchanged) — Office/Interviews/Analytics chips
  are all non-interactive in this iteration.
- `[MUST]` A chip with an `onClick` shall visibly signal interactivity: pointer
  cursor, a hover state (border/background shift, consistent with existing
  hover conventions elsewhere in the app), and a small icon affordance (e.g. a
  chevron or expand icon) distinguishing it from the plain badges next to it.

#### Interviews chips
- `[MUST]` "Waiting" shall count offers with `status === "in_process"` (same
  definition `filterInProcess`/`InterviewsPage` already uses — reuse that
  function, do not reimplement the filter).
- `[MUST]` "Success" shall count offers with `status === "offer"`.
- `[MUST]` Both counts shall be computed from the `jobs` data `InterviewsPage`
  already fetches via `useIntakeAndJobs` — no new API call.

#### Analytics chips
- `[MUST]` "Applied" (total) shall use `stats.funnel.applied` — already present
  in the `/api/stats` payload, no new field.
- `[MUST]` "This week"/"This month" shall come from `getTrends("week")` and
  `getTrends("month")`'s most recent row (`count` of the latest period bucket)
  — both already use `COALESCE(date_applied, date_received)` server-side
  (`_trends_payload`). `AnalyticsPage` fetches month-period trends in addition
  to its existing week-period fetch (or reuses whichever grouping is not
  already the active toggle — see Task breakdown).
- `[MUST]` These 3 chips shall respect the page's active filters exactly like
  every other stat on the page (they use the same filtered `getStats`/
  `getTrends` calls already in place — no separate unfiltered fetch).

#### Settings / CV Master chip
- `[MUST]` A new endpoint `GET /api/cv-master` shall return
  `{ path: str, filled: bool, content_words: int, reason: str | null }`,
  built from `get_cv_master_path()` + `inspect_cv_master()` — reused, not
  reimplemented.
- `[MUST]` A new endpoint `GET /api/cv-master/content` shall return the raw
  markdown text of `cv-master.md` (`{ content: str }`), read via the same
  `get_cv_master_path()`.
- `[MUST]` WHEN the file does not exist THE system SHALL return 404 with a
  structured error (existing error pattern) — not a 200 with empty content.
- `[MUST]` The Settings chip shall render "CV Master: OK ({content_words}
  words)" in the success tone when `filled`, or the report's `.reason` text in
  a warning tone when not filled.
- `[MUST]` Clicking the chip shall open a `Dialog` (reuse `components/ui/
  dialog.tsx`, the same modal primitive already used elsewhere in the app —
  e.g. the Offers detail modal) showing the full `cv-master.md` content
  rendered as markdown.
- `[MUST]` The modal shall fetch `/api/cv-master/content` lazily (on open, not
  on every Settings page load) to avoid reading the file when the user never
  opens the modal.

### Affected files
| File | Action | Reason |
|------|--------|--------|
| `applyr/ui/frontend/src/components/ui/page-header.tsx` | CREATE | Shared `PageHeader` + chip primitive (generalizes `OfficeHeader`'s `StatBadge`) |
| `applyr/ui/frontend/src/features/office/OfficeHeader.tsx` | MODIFY | Rewritten as a thin wrapper around `PageHeader`, or removed if callers switch directly to `PageHeader` |
| `applyr/ui/frontend/src/pages/OfficePage.tsx` | MODIFY | Use `PageHeader` (if `OfficeHeader.tsx` is removed) |
| `applyr/ui/frontend/src/pages/OffersPage.tsx` | MODIFY | Replace bespoke header with `PageHeader`, no chips |
| `applyr/ui/frontend/src/pages/InterviewsPage.tsx` | MODIFY | Replace header, add Waiting/Success chips |
| `applyr/ui/frontend/src/pages/AnalyticsPage.tsx` | MODIFY | Replace header, add Applied/This week/This month chips, fetch month trends |
| `applyr/ui/frontend/src/pages/SettingsPage.tsx` | MODIFY | Replace header, add CV Master chip + modal |
| `applyr/ui/frontend/src/features/settings/CvMasterModal.tsx` | CREATE | Modal component rendering markdown CV content |
| `applyr/ui/frontend/src/api/cv-master.ts` | CREATE | `getCvMasterStatus()`, `getCvMasterContent()` fetch wrappers |
| `applyr/ui/frontend/package.json` | MODIFY | Add `markdown-to-jsx` dependency |
| `applyr/ui/api.py` | MODIFY | Add `GET /api/cv-master`, `GET /api/cv-master/content` |
| `tests/test_ui_api.py` | MODIFY | Tests for both new endpoints (found/missing/unfilled cases) |

### Dependencies
- APIs/endpoints: `/api/cv-master`, `/api/cv-master/content` (new); `/api/stats`,
  `/api/trends` (existing, reused, no contract change)
- Reused: `components/ui/dialog.tsx`, `cv_master.inspect_cv_master`,
  `cv.get_cv_master_path`, `features/jobs/filter-in-process.ts`
  (`filterInProcess`)
- New frontend dependency: `markdown-to-jsx` (single package, no remark/rehype
  ecosystem — user explicitly approved adding a dependency for this, overriding
  the no-new-deps default this session otherwise followed)

### Explicit assumptions
- Confirmed: Analytics KPIs need no new backend field — `funnel.applied` +
  week/month trend rows already cover it.
- Confirmed: only the CV Master chip is clickable in this iteration; Office/
  Interviews/Analytics chips stay informational.
- Confirmed: Offers gets no chips (none requested) but still adopts
  `PageHeader` for consistency.
- We assume `AnalyticsPage` can add a month-period `getTrends` fetch alongside
  its existing week-period one without a UX conflict with the page's own Week/
  Month toggle (that toggle controls the *Applications Over Time chart's*
  granularity, not the header chips — the header always shows both this-week
  and this-month regardless of the chart's toggle state) → if this reads as
  confusing in practice, revisit during implementation review.

### Non-functional requirements
- Security: `/api/cv-master/content` reads a local file the user owns
  (`~/.applyr/cv-master.md`) in a single-user, local-first app — no path
  traversal risk since the path is fixed via `get_cv_master_path()`, never
  user-supplied.
- Accessibility: the clickable CV Master chip needs a proper `role="button"` (or
  a real `<button>`) and keyboard focus/activation, not just a `div` with
  `onClick` — matches the project's existing accessibility patterns (e.g.
  `role="img"`/`aria-label` on charts).

### Edge cases / risks
- `cv-master.md` missing entirely → `/api/cv-master` still returns 200 with
  `filled: false` (file-not-found is itself a valid, displayable state, distinct
  from "exists but unfilled") — only `/api/cv-master/content` 404s, since there's
  nothing to show in the modal. Chip click when `filled` is false due to missing
  file should be handled gracefully (e.g. disable the click affordance, or open
  the modal showing the `reason` text instead of raw content) — decide during
  implementation, document the choice in the PR.
- Large `cv-master.md` (rare, but no enforced size cap) — `markdown-to-jsx`
  handles arbitrary text fine; no pagination needed for a CV-sized document.
- Interview "Success" (status=offer) and "Waiting" (status=in_process) can both
  be 0 — chips must handle zero gracefully (still show "0", not hide the chip).

### Task breakdown (execution order)
1. [x] Backend: `GET /api/cv-master` + `GET /api/cv-master/content` in `ui/api.py`,
   reusing `inspect_cv_master`/`get_cv_master_path`; tests for found/missing/
   unfilled. [S] — corrected during review to drop `path` from both responses,
   matching the existing `/api/settings`/`/api/config` "never a filesystem path
   over the API" convention (the initial implementation exposed it).
2. [x] Frontend: `PageHeader` shared component (title/description + optional chip
   list, chip supports `onClick` with visible affordance vs. plain badge). [M]
3. [x] Migrate `OfficeHeader` → `PageHeader` (Pending/Agents active chips,
   unchanged values, title size now `text-2xl`). [S]
4. [x] Migrate `OffersPage` header → `PageHeader`, no chips. [S]
5. [x] Migrate `InterviewsPage` header → `PageHeader` + Waiting/Success chips
   (client-side from existing `jobs` data). [S]
6. [x] Migrate `AnalyticsPage` header → `PageHeader` + Applied/This week/This month
   chips (fetch month-period trends alongside existing week-period fetch). [M]
   — corrected during review: initial implementation read `trends[trends.length-1]`
   (oldest period in the window) instead of `trends[0]` (most recent, since
   `_trends_payload` orders `DESC`).
7. [x] `api/cv-master.ts` fetch wrappers + `CvMasterModal.tsx` (markdown render via
   `markdown-to-jsx`) + Settings page chip wiring, lazy content fetch on open. [M]
8. [x] Manual browser verification across all 5 pages (chip values correct, CV
   modal opens/renders, keyboard-accessible click affordance) + `npm run build`
   + backend test suite. [S] — verified: 888/888 backend tests, clean build,
   screenshots of Offers/Interviews/Analytics/Settings headers + CV modal
   rendering real content correctly.

### Out of scope
- `[WONT]` "Interview unsuccessful" KPI — no reliable data source without a
  status-history schema change.
- `[WONT]` Making Office/Interviews/Analytics chips clickable — only CV Master
  is interactive in this iteration.
- `[WONT]` A custom date-range picker or new chart types — this spec is header-
  only, it does not touch existing chart/filter logic shipped in
  `specs/analytics-filters-and-fixes/spec.md`.
- `[WONT]` Editing `cv-master.md` from the modal — read-only display only.
