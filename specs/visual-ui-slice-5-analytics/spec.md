## Spec: Visual UI — Analytics page (Slice 5)

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context
- Project constitution (`docs/visual-ui/AGENTS.md`): engine never changes — reuse
  `applyr/commands/analytics.py` aggregation logic, never reimplement SQL in the API
  layer. No WebSocket, no new backend infra. `api/` is the only fetch boundary on the
  frontend. Feature-based structure (`features/<domain>/`, pure logic separate from
  components for Vitest testability). PR base = `feat/cc-visual-ui`, never `main`.
  Stack table locked in Slice 2/3 (plain `fetch`/`useState`, no TanStack Query, no
  Zustand, no chart library) — **this slice amends that table** (see below).
- Relevant ADRs: ADR-011 (Visual UI as optional additive interface) — no new
  constraints beyond what's already true of the frontend package. This slice adds a
  frontend-only npm dependency (Recharts); ADR-011's "zero new deps on base install"
  guarantee is about the Python `applyr` core, not the `ui/frontend` npm tree, so no
  conflict.
- Engram: no prior decisions found for "analytics page recharts trends visual ui".
- Corrected assumptions from Step 2: all 7 assumptions presented to the user were
  confirmed as-is (user replied "sigue" — proceed).
- Pre-spec question answers (binding for this spec):
  1. Scope = Stats + Trends (not Gaps — deferred, no `/api/gaps-stats` in this slice).
  2. Visualization = Recharts (new npm dependency — first one added since the stack
     was locked; the CSS-bars-only path was explicitly rejected by the user).
  3. No date-range filter — static full-history snapshot, matching `applyr stats`/
     `applyr trends` CLI behavior exactly.
  4. No polling — single fetch on page mount (aggregate stats don't change on a
     2-3s timescale; polling here would be pure waste, unlike Office/Offers where the
     underlying `jobs`/`intake` tables change from agent activity between polls).

### What does it do? (observable behavior, not implementation)
Replaces the `ComingSoon` stub at `/analytics` with a real, read-only dashboard
combining two existing CLI reports — `applyr stats` and `applyr trends` — rendered as
charts instead of terminal text. On mount, the page fetches `GET /api/stats` and
`GET /api/trends?period=week` once (no polling), then renders: a conversion funnel
(applied → responded → interview → offer), a trend bar chart (applications per week,
switchable to per month), channel and work-mode breakdown charts, and stat cards for
average compatibility and salary range. No data is ever mutated from this page.

### Acceptance criteria

- `[MUST]` Given a user navigates to `/analytics`, When the page loads, Then it fetches
  `GET /api/stats` and `GET /api/trends?period=week` exactly once (on mount), not on an
  interval — distinct from the polling pattern used by Office/Offers/Agents.
- `[MUST]` The system shall expose `GET /api/stats` in `applyr/ui/api.py`, returning the
  same aggregate shape as `applyr stats --json` (`total`, `pending`, `discarded`,
  `avg_compatibility_pct`, `avg_compatibility_pct_excluded_unknown_weights`, `funnel`,
  `channels`, `work_modes`, `score_calibration`, `excluded_unknown_weights`, and
  `salary` when present).
- `[MUST]` The system shall expose `GET /api/trends?period=week|month` (default
  `week`), returning the same shape as `applyr trends --period <p> --json` (list of
  `{period, count, growth_pct}`); invalid `period` values return HTTP 400, mirroring
  the CLI's `die()` on the same input.
- `[MUST]` Both endpoints shall call the existing aggregation logic in
  `applyr/commands/analytics.py` (extracted into shared helper functions consumed by
  both `cmd_stats`/`cmd_trends` and the new endpoints) — no SQL duplicated in
  `applyr/ui/api.py`.
- `[MUST]` Given `total == 0` (empty database), Then `GET /api/stats` returns valid
  JSON with `total: 0` (HTTP 200, not an error), and the frontend renders a friendly
  empty state ("No offers in the database yet.", mirroring the CLI message) instead of
  charts.
- `[MUST]` Given no dated offers exist, Then `GET /api/trends` returns `[]` (HTTP 200),
  and the frontend renders a friendly empty state ("No dated offers found.", mirroring
  the CLI message) instead of a trend chart.
- `[MUST]` Given the funnel data, Then the page renders a funnel visualization showing
  all four stages (`applied`, `responded`, `interview`, `offer`) with their real counts
  and the same percentage-of-previous-stage math already computed server-side by
  `cmd_stats` (no client-side re-derivation of percentages).
- `[MUST]` Given trend data, Then the page renders a bar chart of counts by period, with
  a toggle to switch between `week` and `month` (re-fetches `/api/trends` with the new
  `period` on toggle — this is the one interaction allowed to trigger a second fetch).
- `[MUST]` Given channel/work-mode breakdown data, Then the page renders one chart per
  breakdown (bar or donut), using real counts only — no channel/mode is fabricated if
  absent from the data.
- `[MUST]` Given salary and score-calibration data, Then the page renders them as stat
  cards (min/max/avg for salary; whatever `score_calibration` reports), not charts —
  matches the pre-spec decision that single-number aggregates don't need a chart.
- `[MUST]` The system shall add Recharts as a new frontend dependency in
  `applyr/ui/frontend/package.json`, and shall NOT add any dependency to the Python
  `applyr` core or the `applyr[ui]` extra.
- `[MUST]` All new chart colors shall pass the same WCAG AA contrast check already
  applied to the rest of the palette (Slice 2) — verified via the existing contrast
  script or equivalent manual check before merge, not assumed from Recharts defaults.
- `[MUST]` `docs/visual-ui/AGENTS.md`'s Stack table shall be amended to list Recharts
  (frontend-only) with a one-line rationale, consistent with how the table already
  documents the TanStack Query/Zustand correction.
- `[SHOULD]` Pure data-shaping logic (funnel percentage lookup, chart-ready data
  transforms) shall live in its own file separate from chart components, unit-tested in
  Vitest, per the locked frontend structure.
- `[WONT]` No `/api/gaps-stats` endpoint or gaps visualization in this slice (deferred;
  scope was explicitly narrowed to Stats + Trends in the pre-spec questions).
- `[WONT]` No date-range filter/picker — full-history snapshot only, matching CLI
  behavior exactly.
- `[WONT]` No polling/auto-refresh — single fetch per mount/toggle interaction only.
- `[WONT]` No write/mutation capability anywhere on this page.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/commands/analytics.py` | MODIFY | Extract `_stats_payload(conn)` / `_trends_payload(conn, period)` pure functions reused by both `cmd_stats`/`cmd_trends` and the new API endpoints |
| `applyr/ui/api.py` | MODIFY | Add `GET /api/stats`, `GET /api/trends` routes calling the extracted payload functions |
| `applyr/ui/frontend/package.json` | MODIFY | Add `recharts` dependency |
| `applyr/ui/frontend/src/api/analytics.ts` | CREATE | Typed fetch functions for `/api/stats`, `/api/trends` (the only HTTP boundary for this feature) |
| `applyr/ui/frontend/src/features/analytics/analytics-data.ts` | CREATE | Pure data-shaping helpers (funnel stage list, chart-ready transforms) |
| `applyr/ui/frontend/src/features/analytics/analytics-data.test.ts` | CREATE | Vitest coverage for pure data-shaping logic |
| `applyr/ui/frontend/src/features/analytics/FunnelChart.tsx` | CREATE | Conversion funnel visualization (Recharts) |
| `applyr/ui/frontend/src/features/analytics/TrendChart.tsx` | CREATE | Applications-over-time bar chart + week/month toggle (Recharts) |
| `applyr/ui/frontend/src/features/analytics/BreakdownChart.tsx` | CREATE | Reusable chart for channel/work-mode breakdowns (Recharts) |
| `applyr/ui/frontend/src/features/analytics/StatCards.tsx` | CREATE | Salary + score-calibration stat cards (no chart) |
| `applyr/ui/frontend/src/pages/AnalyticsPage.tsx` | MODIFY | Replace `ComingSoon` stub with real page composing the above |
| `tests/test_ui_api.py` | MODIFY | Backend tests for the two new endpoints (happy path, empty state, invalid period) |
| `tests/test_analytics.py` (or existing CLI analytics test file) | MODIFY | Confirm `cmd_stats`/`cmd_trends` still behave identically after extraction (regression guard) |
| `specs/visual-ui-slice-5-analytics/spec.md` | MODIFY | Traceability matrix + status update once implemented |
| `docs/visual-ui/AGENTS.md` | MODIFY | Stack table amendment (Recharts) + append Slice 5 entry to Status section |

### Dependencies
- APIs / endpoints used: new `GET /api/stats`, new `GET /api/trends?period=`. No
  existing endpoints modified.
- DB tables: none touched directly — read-only through the existing `offers` table via
  the extracted `applyr/commands/analytics.py` helpers (same queries `cmd_stats`/
  `cmd_trends` already run).
- Reused components: `Card`/`Badge` from `components/ui/` for stat cards and layout;
  no reuse from `features/jobs/` (this is a new, independent feature domain).
- New dependency: `recharts` (frontend only).

### Explicit assumptions
- We assume "Stats + Trends" excludes gaps entirely for this slice → if the user wants
  gaps visualized later, that's `GET /api/gaps-stats` as its own follow-up slice, not
  retrofitted here.
- We assume the funnel percentages shown are exactly what `cmd_stats` already computes
  server-side (`_pct(num, denom)` logic) → the frontend never recomputes or second-
  guesses those numbers, avoiding drift between CLI and UI on the same metric.
- We assume Recharts' default accessibility (SVG-based, screen-reader-unfriendly by
  default for chart internals) is acceptable for a single-user local tool → if this
  becomes a real accessibility complaint later, that's a follow-up, not a blocker here
  (noted under Non-functional requirements below rather than silently ignored).

### Non-functional requirements
- Performance: two fetches on mount (stats + trends), one additional fetch on
  week/month toggle — no perceptible latency concern at local-SQLite scale (existing
  `cmd_stats`/`cmd_trends` already run interactively from the CLI on the same data).
- Accessibility: WCAG AA contrast required on all new chart colors (see AC above).
  Chart SVG internals (bars, funnel segments) are not required to be screen-reader
  navigable in this slice — documented as an explicit assumption above, not silently
  dropped.
- Security: no new attack surface — both endpoints are read-only aggregates over
  already-local data, no new input except the `period` enum (validated, mirrors CLI).

### Edge cases / risks
- Empty database (`total == 0`) → friendly empty state, not broken charts or a 500
  (AC above).
- No dated offers for trends (`date_applied`/`date_received` both null on every row) →
  friendly empty state for the trend chart specifically, independent of whether stats
  itself has data (a user could have offers but none dated yet).
- `avg_compatibility_pct` excludes offers with `weights_used IS NULL` (per ADR-009,
  same as the CLI) — the frontend must surface the `excluded_unknown_weights` count
  somewhere near that stat, not hide the exclusion silently (same transparency the CLI
  already provides via `_excluded_note`).
- Recharts bundle size — first chart library added to a previously dependency-light
  frontend; acceptable since this is a local dev-served/embedded single-page app, not
  a bundle-size-sensitive public site, but worth a one-line note in the PR body.

### Task breakdown (execution order)
1. [x] Extract `_stats_payload(conn)` / `_trends_payload(conn, period)` in
   `applyr/commands/analytics.py`, re-point `cmd_stats`/`cmd_trends` at them, confirm
   existing CLI tests still pass unchanged (pure refactor, no behavior change) [S]
2. [x] Add `GET /api/stats`, `GET /api/trends` to `applyr/ui/api.py` + backend tests
   (happy path, empty state, invalid period → 400) [S]
3. [x] Install `recharts`, `src/api/analytics.ts` typed fetch functions [S]
4. [x] `analytics-data.ts` + `analytics-data.test.ts` — pure data-shaping, independently
   verifiable via Vitest before any chart exists [S]
5. [x] `FunnelChart.tsx`, `TrendChart.tsx` (+ week/month toggle), `BreakdownChart.tsx`,
   `StatCards.tsx` — one chart component at a time, each checked against the WCAG AA
   contrast script [M]
6. [x] `AnalyticsPage.tsx` — wire the fetch-on-mount + compose all chart components +
   empty states [M]
7. [x] Manual verification against real data + traceability matrix + `docs/visual-ui/
   AGENTS.md` Stack amendment and Status update [S]

Task sizes: S (<1h) | M (1-3h)

### Out of scope
- `[WONT]` Gaps visualization (`/api/gaps-stats`) — future slice.
- `[WONT]` Date-range filter/picker.
- `[WONT]` Polling/auto-refresh.
- `[WONT]` Any write/mutation capability.
- `[WONT]` Screen-reader-navigable chart internals (documented assumption, not a hard
  requirement for this single-user local tool in this iteration).

## Traceability Matrix

| AC | Priority | Description | Verification | Status |
|----|----------|--------------|---------------|--------|
| AC-01 | MUST | Fetch stats+trends once on mount, no polling | `AnalyticsPage.tsx` `useEffect(..., [])` — empty deps array | PASS |
| AC-02 | MUST | `GET /api/stats` matches `applyr stats --json` shape | `test_ui_api.py::TestStatsEndpoint::test_matches_cmd_stats_json_shape` | PASS |
| AC-03 | MUST | `GET /api/trends?period=` matches CLI shape, 400 on invalid period | `TestTrendsEndpoint` (4 tests incl. `test_invalid_period_is_400`) | PASS |
| AC-04 | MUST | Both endpoints reuse extracted payload functions, no SQL duplication | `applyr/ui/api.py` imports `_stats_payload`/`_trends_payload` from `applyr/commands/analytics.py`; code review confirms no inline SQL in `api.py` | PASS |
| AC-05 | MUST | Empty DB (`total==0`) → HTTP 200 `{"total": 0}`, friendly frontend empty state | `test_empty_database_returns_total_zero_not_error`; `AnalyticsPage.tsx` `isEmptyStats()` → `ComingSoon` | PASS |
| AC-06 | MUST | No dated offers → `[]` HTTP 200, friendly trend empty state | `test_no_dated_offers_returns_empty_list`; `TrendChart.tsx` "No dated offers found." branch | PASS |
| AC-07 | MUST | Funnel renders all 4 stages with backend-computed percentages | `FunnelChart.tsx` + `funnelStages()`; `analytics-data.test.ts` "orders stages..." + "passes through null percentages untouched" | PASS |
| AC-08 | MUST | Trend bar chart with week/month toggle, re-fetches on toggle | `TrendChart.tsx` `handlePeriodChange` calling `getTrends(next)` | PASS |
| AC-09 | MUST | Channel/work-mode breakdown charts, real counts only | `BreakdownChart.tsx` (2 instances in `AnalyticsPage.tsx`) + `breakdownEntries()` tests | PASS |
| AC-10 | MUST | Salary/score-calibration as stat cards, not charts | `StatCards.tsx` — no chart import, `Card` primitives only | PASS |
| AC-11 | MUST | Recharts added to frontend only, no Python core dependency | `git diff --stat` — `pyproject.toml` untouched, only `applyr/ui/frontend/package.json`/`package-lock.json` changed | PASS |
| AC-12 | MUST | Chart colors pass WCAG AA / CVD-safety validation | `node validate_palette.js` run against real `--background` (`#1a1917`) — teal-led reorder of default dark categorical set, ALL CHECKS PASS; documented in `index.css` | PASS |
| AC-13 | MUST | `docs/visual-ui/AGENTS.md` Stack table amended for Recharts | Stack table row added + Slice 5 Status entry appended | PASS |
| AC-14 | SHOULD | Pure data-shaping unit-tested, separate from components | `analytics-data.ts` (3 pure functions) + `analytics-data.test.ts` (6 tests) | PASS |

Full suite: 777/777 Python tests passing (6 new: `TestStatsEndpoint` x2, `TestTrendsEndpoint`
x4; 41 pre-existing stats/trends tests unchanged after the `_stats_payload`/
`_trends_payload` extraction), 31/31 Vitest passing (6 new in `analytics-data.test.ts`),
`tsc --noEmit` clean. Manually verified both new endpoints against the user's real
246-offer database via curl (correct shapes, real funnel/channel/salary numbers).
Could NOT visually verify chart rendering in a browser — no browser-driving/screenshot
tool available in this session; disclosed explicitly rather than assumed. Backend
(:8000) and frontend (:5173) dev servers left running for the user to check `/analytics`
directly. `/simplify-lean` ran 4 times across the slice (analytics.py extraction;
api.py + test_ui_api.py; api/analytics.ts + analytics-data.ts/.test.ts; the 5
chart/page components) — first 3 passes returned "no changes needed", the 4th
extracted a shared `TOOLTIP_CONTENT_STYLE` constant out of 3 near-identical Recharts
`Tooltip` style objects into `analytics-data.ts`, re-verified clean (`tsc`/Vitest
still green) after the extraction.
