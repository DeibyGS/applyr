## Spec: Analytics page — filter row, funnel chart fix, salary normalization

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context
- Project constitution (`constitution.md`): parameterized SQL only, no DB access
  outside `db.py`/`get_conn()`, constants in `constants.py` (no magic numbers in
  business logic), `--json` output keys are never renamed/removed, tests+code same
  commit, PR budget 500 lines, coverage gate 75%.
- `AGENTS.md`: analytics/reporting lives in `commands/analytics.py`; applyr is a
  storage layer, no LLM calls (irrelevant here but confirmed not violated).
- ADR-009 (`docs/adr/009-weight-versioning-and-rebalance.md`): `avg_compatibility_pct`
  excludes offers with `weights_used IS NULL` — this exclusion is a fixed baseline,
  not a user-facing filter, and must stay AND-combined with any new filters, never
  overridden.
- Engram: no prior decisions found for analytics filters, salary normalization, or
  the funnel chart form.
- Corrected assumptions from Step 2: none — all 9 assumptions confirmed as-is by the
  user (2026-08-30).

### What does it do? (observable behavior, not implementation)
- The Analytics page gains one filter row (date-range preset, work mode, canal,
  seniority level, role category) above all charts. Changing any filter re-renders
  every chart on the page (StatCards, Conversion Funnel, Applications Over Time,
  Channel/Work Mode Breakdown) against the same filtered slice.
- The Conversion Funnel changes from a proportional-area funnel shape to a
  horizontal bar chart, one bar per stage, so stages with a count of 0 render
  correctly instead of breaking the funnel silhouette.
- The "Salary" stat card's min/max/avg (and the CLI's `applyr salary` min/max/avg/
  median) now reflect annual-equivalent values: monthly and hourly salaries are
  converted to their annual equivalent before aggregating, instead of being mixed
  in raw with annual values.

### Acceptance criteria

#### Backend — filters
- `[MUST]` WHEN `/api/stats` is called with no query params THE system SHALL return
  the same payload shape as today, unfiltered (no regression).
- `[MUST]` WHEN `/api/stats` is called with any combination of `from`, `to`,
  `work_mode`, `canal`, `seniority_level`, `role_category` THE system SHALL apply
  all provided filters as AND-combined SQL WHERE conditions, using parameterized
  queries only.
- `[MUST]` WHEN `avg_compatibility_pct` is computed under any filter combination THE
  system SHALL still exclude `weights_used IS NULL` offers (ADR-009), AND-combined
  with the user filters, never replaced by them.
- `[MUST]` WHEN `/api/trends` is called THE system SHALL accept the same filter
  query params as `/api/stats`, in addition to its existing `period` param, and
  apply them identically.
- `[MUST]` The system shall reject an invalid `work_mode`/`canal`/`seniority_level`/
  `role_category` value (not in the existing `VALID_*` tuples in `db.py`) with a 400
  and a structured JSON error (existing error pattern), not a silent no-op filter.
- `[SHOULD]` IF the filtered result set is empty THEN `/api/stats` SHALL return a
  distinguishable payload (e.g. `{"total": 0, "filtered": true}` alongside the
  existing empty-payload shape) so the frontend can tell "no offers in DB" apart
  from "no offers match this filter."

#### Backend — salary normalization
- `[MUST]` The system shall provide a single pure function
  `_normalize_to_annual(value: int, period: str) -> int` in `commands/analytics.py`,
  used by both `_stats_payload()`'s salary block and `_salary_stats()`.
- `[MUST]` WHEN `salary_period == "monthly"` THE system SHALL multiply the value by
  12 before aggregating.
- `[MUST]` WHEN `salary_period == "hourly"` THE system SHALL multiply the value by
  `HOURS_PER_WORK_YEAR` (new constant in `constants.py`, value 2080).
- `[MUST]` WHEN `salary_period == "annual"` (or unset, defaulting per existing
  `db.py` column default) THE system SHALL use the value unchanged.
- `[MUST]` `_stats_payload()`'s salary block SHALL fetch raw `(salary_min,
  salary_max, salary_period)` rows and normalize+aggregate in Python (replacing the
  current raw `SELECT MIN/MAX/AVG(salary_min)` SQL aggregate), mirroring
  `_salary_stats()`'s existing per-row approach.
- `[MUST]` `cmd_salary`'s median calculation SHALL use normalized values, not raw
  ones.
- `[MUST]` The `--json` output key names for salary (`salary.min`, `salary.max`,
  `salary.avg`, and the CLI's min/max/avg/median) SHALL NOT change — only the
  values change semantics (constitution: never rename/remove `--json` keys).

#### Frontend — filter row
- `[MUST]` Given the Analytics page, When no filter is active, Then the page
  behaves exactly as it does today (unfiltered).
- `[MUST]` Given the Analytics page, When the user picks a date-range preset (7d /
  30d / 90d / All), Then the frontend computes `from`/`to` client-side (ISO dates)
  and passes them to `getStats`/`getTrends`; "All" omits both params entirely.
- `[MUST]` Given the Analytics page, When the user sets work mode, canal, seniority,
  or role category, Then all charts on the page re-fetch and re-render against that
  slice — no per-chart filters.
- `[MUST]` The filter row SHALL reuse the existing `components/ui/filter-bar.tsx`
  primitives (FilterGroup/FilterPill/SegmentedControl/ActiveFilterChips) — no new
  filter UI component.
- `[MUST]` TrendChart's existing Week/Month granularity toggle SHALL remain
  independent of and composable with the new filters (both apply simultaneously).
- `[SHOULD]` Given a filter combination that matches zero offers, When the page
  re-renders, Then it shows a distinct empty state ("No offers match these
  filters") rather than the existing "No offers in the database yet" `ComingSoon`
  message.

#### Frontend — funnel chart
- `[MUST]` The Conversion Funnel SHALL render as a horizontal bar chart (Recharts
  `BarChart`), one bar per stage (Applied/Responded/Interview/Offer), ordinal
  single-hue ramp (reuse the existing validated `STAGE_FILLS` colors).
- `[MUST]` A stage with count 0 SHALL render as an empty/zero-length bar, not break
  the chart layout.
- `[MUST]` Each bar SHALL show count and percent-of-previous-stage (reuse the
  server-computed `funnel_pct`), matching the current funnel's label content.
- `[MUST]` The chart SHALL keep the existing `role="img"` + `aria-label` pattern
  listing all stage values for accessibility.

### Affected files
| File | Action | Reason |
|------|--------|--------|
| `applyr/commands/analytics.py` | MODIFY | Add filter params to `_stats_payload`/`_trends_payload`; add `_normalize_to_annual`; rewrite salary block and `_salary_stats` to use it |
| `applyr/constants.py` | MODIFY | Add `HOURS_PER_WORK_YEAR = 2080` |
| `applyr/ui/api.py` | MODIFY | Add `Query` params to `/api/stats` and `/api/trends`; validate against `VALID_*` tuples, 400 on invalid |
| `applyr/ui/frontend/src/api/analytics.ts` | MODIFY | Thread new filter params through `getStats`/`getTrends` signatures |
| `applyr/ui/frontend/src/features/analytics/analytics-filters.ts` | CREATE | Filter state type + `hasActiveFilters`/`describeActiveFilters`, mirroring `features/jobs/offer-filters.ts` |
| `applyr/ui/frontend/src/features/analytics/AnalyticsFilterBar.tsx` | CREATE | Filter row component using `components/ui/filter-bar.tsx` primitives |
| `applyr/ui/frontend/src/pages/AnalyticsPage.tsx` | MODIFY | Wire filter state, pass to `getStats`/`getTrends`, render `AnalyticsFilterBar`, distinct filtered-empty state |
| `applyr/ui/frontend/src/features/analytics/FunnelChart.tsx` | MODIFY | Replace `Funnel`/`RechartsFunnelChart` with horizontal `BarChart` |
| `tests/test_analytics.py` | MODIFY | Tests for `_normalize_to_annual`, filtered `_stats_payload`/`_trends_payload`, ADR-009 AND-composition, invalid filter value → 400 |

### Dependencies
- APIs/endpoints: `/api/stats`, `/api/trends` (both existing, gaining query params)
- DB tables: `offers` (existing columns: `salary_min`, `salary_max`, `salary_period`,
  `work_mode`, `canal`, `seniority_level`, `role_category`, `created_at TEXT
  DEFAULT CURRENT_TIMESTAMP` — confirmed in `db.py:121`, used for the date-range
  filter)
- Reused components: `components/ui/filter-bar.tsx`, `components/ui/card.tsx`,
  existing `VALID_WORK_MODES`/`VALID_SENIORITY`/`VALID_ROLE_CATEGORIES` from `db.py`
- No new dependencies (stays on Recharts, no new charting or date-picker library)

### Explicit assumptions
- We assume filters AND-combine, never OR → if false, revisit query builder shape.
- We assume "All" means omit date params entirely (not a wide literal range) → if
  false, adjust client-side preset logic.
- Confirmed: `offers.created_at` (`db.py:121`) is the date-range filter column.

### Non-functional requirements
- Security: all filter values validated against existing `VALID_*` enums before
  use in SQL; all queries parameterized (constitution requirement, not optional).
- Performance: no explicit target — this is a local SQLite DB, existing query
  patterns (unindexed WHERE on a few hundred rows) are the precedent and are
  sufficient.

### Edge cases / risks
- Mixing `salary_period` normalization changes historical salary numbers users may
  have already seen → acceptable, this is a bug fix, not a new feature; no
  migration needed since it's computed at read-time, not stored.
- Invalid filter combination (e.g. a `role_category` that legitimately has zero
  offers) is not an error — it's the `[SHOULD]` empty-filtered-state case, not a 400.
  A 400 is only for a value outside the `VALID_*` enum entirely (a real bad request).
### Task breakdown (execution order)
1. [x] Add `_normalize_to_annual` + `HOURS_PER_WORK_YEAR` constant; rewrite
   `_salary_stats` and `_stats_payload`'s salary block to use it; tests for all 3
   periods + no-regression on pure-annual data. [M]
2. [x] Add filter params (`from`, `to`, `work_mode`, `canal`, `seniority_level`,
   `role_category`) to `_stats_payload`/`_trends_payload`, parameterized SQL,
   ADR-009 exclusion stays AND-fixed; tests for each dimension + combined filters +
   empty-filtered-result payload shape. [M]
3. [x] Add `Query` params + `VALID_*` validation (400 on invalid) to `/api/stats` and
   `/api/trends` in `ui/api.py`; tests for valid/invalid param values. [S]
4. [x] `analytics-filters.ts` (filter state + chip helpers, mirrors `offer-filters.ts`)
   + `AnalyticsFilterBar.tsx` using existing `filter-bar.tsx` primitives. [M]
5. [x] Wire filter state into `AnalyticsPage.tsx`, thread through `getStats`/
   `getTrends` in `api/analytics.ts`, add filtered-empty state. [M]
6. [x] Replace `FunnelChart.tsx`'s `Funnel` with a horizontal `BarChart`; verify zero-
   value stages render correctly; keep `role="img"`/`aria-label`. [S]
7. [x] Manual browser verification (both filtered and unfiltered, zero-result filter,
   dark-mode contrast) + `npm run build` + full backend test suite. [S]

### Out of scope
- `[WONT]` Custom date-range picker (presets only, per user decision).
- `[WONT]` New charting library — stays on Recharts.
- `[WONT]` Changes to Offers or Interviews pages.
- `[WONT]` An ADR for the salary normalization — classified as Design (low cost of
  reversal, read-time computation, no schema change), not Architecture.
