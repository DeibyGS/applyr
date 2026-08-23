# applyr Visual UI — Feature Guide

> Read this file first whenever the user says "applyr UI", "la interfaz", "la visual",
> or "dashboard" — it means work happens in this worktree/branch, not in the main
> `applyr` repo. If the user says plain "applyr" or "la tool", this file does not apply.

## What this is

A local, single-user visual dashboard for `applyr`. NOT a rewrite, NOT a SaaS. Full
context/rationale for every decision below lives in the chat session dated 2026-08-22/23
that scoped this down from a much larger multi-tenant proposal
(`APPLYR_VISUAL_AGENTS_PROPOSAL.md`, kept as historical reference only — most of its
infra choices were rejected, see "Explicitly rejected" below).

## Non-negotiable invariants

1. **The engine does not change.** `applyr/db.py`, `scoring.py`, `cv.py`,
   `commands/*.py` are reused, never duplicated. The UI is a new, separate, optional
   package that reads/writes the same SQLite DB.
2. **Claude Code / OpenCode / Cursor remains the brain.** The dashboard never calls an
   LLM API directly and never re-implements Matcher/Recruiter scoring logic. It is a
   viewer + intake form.
3. **Data flow for a new offer:**
   ```
   Dashboard: user pastes/uploads offer text
        -> saved as a "pending" row in the existing jobs DB
        -> user tells their AI agent (in a terminal) to process pending offers
        -> agent runs the existing pipeline (applyr add / update, same as today)
        -> Dashboard polls the same DB (TanStack Query, no WebSocket in v1)
        -> UI reflects real state changes only — never simulate/fake agent progress
   ```
4. **No infrastructure beyond a single process.** No Postgres, no Redis, no Celery, no
   Docker Compose, no auth, no multi-tenancy. Single user, local machine, `applyr ui`
   starts one process and that's it.

## Stack (decided — don't re-litigate without a new decision)

| Layer | Choice |
|---|---|
| Backend | FastAPI, single process, embeds/serves the built frontend |
| DB | Existing SQLite via `applyr/db.py` — no new engine, minimal schema additions only if truly needed |
| Real-time | Plain `fetch` + `setInterval` polling (2-3s), wrapped in shared hooks (`useIntakeAndJobs`, `useThresholds`). No WebSocket in v1. |
| Frontend | React + TypeScript + Vite |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite`) + shadcn/ui + Radix UI + Lucide icons |
| Animation | Framer Motion, 2D/CSS only — no Three.js / 3D |
| Charts | Recharts (added Slice 5) — first chart library; the funnel/trend/breakdown charts on the Analytics page need real geometry (funnel segments, trend lines) that plain CSS bars can't do well. Frontend-only dependency, zero impact on the Python `applyr[ui]` extra. Chart colors are never picked by eye — validated per-app with the dataviz skill's CVD-safety script against the real `--background` surface before use (see `index.css`'s `--chart-1..6` tokens and their validation note). |
| Client state | Plain `useState`/`useEffect` — no global store adopted (no Zustand). Revisit only if prop-drilling actually becomes painful; it hasn't across 3 slices. |
| Routing | `react-router` v8 (Slice 3+) — real URLs per page, `<BrowserRouter>`/`<Routes>` |
| Packaging | `pip install applyr[ui]` — optional extra. Core `applyr` CLI stays dependency-light (stdlib + colorama), do not add FastAPI/React deps to the base install. |

Corrected 2026-08-23 after 3 slices of real implementation: this table originally named
TanStack Query and Zustand, neither of which was ever actually installed — plain
`fetch`/`useState`/`setInterval` covered every real need so far. Table above now
reflects what's actually in the codebase, not the original upfront guess. Revisit
TanStack Query specifically if request deduplication/caching across pages becomes a
real problem (3 pages now poll independently via the shared hooks — acceptable at this
scale, not necessarily forever).

## Frontend structure (locked in 2026-08-23 — read before adding any file)

Feature-based/domain organization, not the old "everything in `components/`" pattern —
this is current React/Vite best practice (Robin Wieruch's 2026 folder-structure guide
is the most-cited reference on this specific question) and is what keeps a growing
multi-slice dashboard debuggable instead of turning into a junk drawer.

```
applyr/ui/frontend/src/
├── main.tsx / App.tsx / index.css   # entry point + route definitions (Slice 3+)
├── assets/                          # images (agent illustrations, etc.)
├── api/                             # the ONLY place that calls fetch()
│   ├── client.ts                    # base wrapper (error shape, base URL)
│   ├── intake.ts, jobs.ts, config.ts  # one file per backend resource, typed
├── layout/                          # app chrome: Sidebar, AppShell, ComingSoon —
│                                     # navigation/shell, not a business domain
├── pages/                           # one file per route (Slice 3+), thin — composes
│                                     # features/* and layout/*, no logic of its own
├── features/<domain>/               # agents/, jobs/, intake/, kanban/ (later), ...
│   ├── SomeComponent.tsx            # PascalCase, feature-specific UI
│   ├── some-logic.ts                # kebab-case, PURE function, no React/DOM
│   ├── some-logic.test.ts           # colocated, not a separate __tests__ tree
│   └── types.ts
├── components/ui/                   # shadcn-generated primitives ONLY — never
│                                     # hand-write a component directly in here
├── hooks/                           # cross-feature hooks only (rare) — e.g.
│                                     # useIntakeAndJobs, useThresholds,
│                                     # useSelectedJob: 2-3 pages each needed the
│                                     # same fetch/polling, shared here instead of
│                                     # duplicated per page
└── lib/                             # small: cn() helper + app-wide constants only
```

Rules (don't relitigate these per-slice — they're decided):

1. **A feature folder owns everything specific to it** — components, pure logic,
   types, tests, colocated. When `jobs` grows (Kanban, detail panel, timeline), it
   grows inside `features/jobs/`, not spread across generic folders.
2. **`components/ui/` is shadcn-only.** App-specific UI always lives in the relevant
   `features/` folder, never here.
3. **`api/` is the only HTTP boundary.** Features import typed functions from `api/`;
   they never call `fetch` directly. Keeps the backend contract centralized and mockable.
4. **Pure logic lives in its own file, separate from the component that uses it** —
   e.g. `agent-status.ts` vs `AgentCard.tsx`. This is what makes it unit-testable with
   Vitest with zero DOM/jsdom setup, and it's why a "styling-only" slice can still ship
   real, fast unit tests instead of skipping tests entirely.
5. **`lib/` stays small on purpose.** If something feels like it belongs in `lib/` but
   is really about jobs or agents specifically, it goes in that feature folder instead.
6. **Naming:** kebab-case for `.ts` files, PascalCase for `.tsx` components, camelCase
   for exported functions/variables.
7. **Tests are colocated**, never a top-level `__tests__/` tree — a feature folder
   should be fully self-contained and movable/deletable as a unit.
8. **`layout/` is app chrome, `pages/` is route composition — neither is a feature.**
   A page file should mostly just import from `features/*`/`layout/*` and lay them
   out; if a page starts accumulating its own business logic, that logic belongs in
   a `features/` folder instead.

## Explicitly rejected (do not add later without a real trigger)

PostgreSQL, Redis, Celery + queues, WebSockets (v1), auth/multi-tenancy, 3D/Three.js,
Docker Compose, OpenTelemetry/Prometheus, an `LLMProvider` abstraction layer (there is
no direct LLM call from the backend — the AI coding agent is the LLM caller, via CLI).
These solve scale/multi-tenant problems that don't exist for a single local user. If a
concrete trigger appears later (e.g. this becomes multi-user), revisit as a new decision,
not a default.

## Git workflow

- **Integration branch:** `feat/cc-visual-ui` — this is the "developer" branch. Never
  merges into `main` until the user explicitly says the feature is ready.
- **Worktree:** `.worktrees/cc-visual-ui` (gitignored, not tracked). Run the dev server
  here (`applyr ui` / `npm run dev`) and leave it running across sessions — the repo root
  worktree stays free for normal `applyr` CLI work/bug fixes on `main`.
- **Sub-PRs (per phase/feature):**
  - Branch off `feat/cc-visual-ui`, name it `feat/cc-visual-ui-<short-name>`
    (e.g. `feat/cc-visual-ui-backend-skeleton`, `feat/cc-visual-ui-kanban`).
  - Open the PR with **base = `feat/cc-visual-ui`**, never `main`. Double-check the base
    branch before creating every PR — this is the #1 way main gets dirtied by accident.
  - Same discipline as always: work-unit commits (code+tests together), PR budget ≤500
    changed lines per sub-PR (split into chained sub-PRs if a phase is bigger), PR body
    follows the usual template.
- **Keeping in sync with main:** periodically (start of a new phase, or before the final
  PR) run, from inside `feat/cc-visual-ui`:
  ```bash
  git fetch origin main
  git merge origin/main
  ```
  Conflict risk should stay low — this feature lives in new files/a new package and only
  *reads* `db.py`, it doesn't modify existing core modules.
- **Final PR:** only when the user explicitly says the feature is ready to present —
  `feat/cc-visual-ui` -> `main`, reviewed like any other PR.
- **Never:** commit directly to `main` from this work, merge `feat/cc-visual-ui` into
  `main` without explicit approval, or open a sub-PR with base `main`.

## Where the technical spec lives

`specs/visual-ui/` (populated via `/sdd`, one spec per phase/slice as we go — not one
giant upfront spec for the whole feature).

## Status

**Slice 1 implemented (2026-08-23)** — `specs/visual-ui/spec.md`, status IMPLEMENTED.
Backend (`applyr/ui/server.py` + `api.py`), `ui_intake` table + migration
(`applyr/db.py`, `applyr/intake.py`), `applyr add --intake-id` linkage
(`applyr/commands/core.py`), `applyr ui` CLI command, `applyr[ui]` optional extra
(`pyproject.toml`), frontend scaffold (`applyr/ui/frontend/`, unstyled), ADR-011. 35
new backend tests (`tests/test_ui_intake.py`, `tests/test_ui_api.py`,
`tests/test_ui_cli.py`), full suite green (756 tests), manual end-to-end pass verified
against a live server: paste offer -> `add --intake-id` -> promoted -> real score
visible via `/api/jobs`, full topic breakdown via `/api/jobs/{id}`.

Known follow-ups (not blockers for this slice, tracked here so they aren't lost):
- Frontend scaffold's `npm audit` flags a moderate esbuild/vite dev-server advisory
  (GHSA-67mh-4wv8-2f99) — fixing needs a vite major bump (5.x -> 8.x), deferred rather
  than absorbed into this slice; low real risk given the loopback-only threat model, but
  should be revisited before this frontend gets built out further.
- Unrelated applyr core bug found while testing (NOT part of this feature, not fixed
  here): running `applyr init`/`setup-agent` with cwd inside the applyr repo itself
  duplicates content into the repo's own root `AGENTS.md` instead of detecting it's
  already current. Saved to Engram (`bug-agents-md-duplication-on-repo-self-init`) for a
  separate fix.

**Slice 2 implemented (2026-08-23)** — `specs/visual-ui-slice-2/spec.md`, status
IMPLEMENTED. Real design system (Tailwind v4 + shadcn/ui CLI, warm graphite palette,
teal accent, Fraunces/Inter self-hosted, `lucide-react` icons only). New
`GET /api/config` endpoint (read-only thresholds). Agent row with the user's 5
real character illustrations (normalized, compressed to WebP, ~2.3MB -> ~274KB);
Recruiter/Matching show real derived status, CV/ATS/Application honestly show "not
connected yet." Job list restyled as cards with real-threshold color coding; job
detail restyled with the same information as Slice 1. Intake form/list restyled.
Frontend restructured into the locked feature-based layout (`api/`, `features/*`,
`components/ui/` shadcn-only). WCAG AA contrast verified via script — 3 initial
palette values (`highlight`, `danger`, `ring`) were adjusted after failing the check.
10 new Vitest unit tests for the pure logic (`agent-status.ts`, `score-color.ts`),
full Python suite green (771 tests). Confirmed visually by the user against their
real data (245 real offers) before merging.

**Slice 3 implemented (2026-08-23)** — `specs/visual-ui-slice-3/spec.md`, status
IMPLEMENTED. Sidebar navigation shell via `react-router` v8: 7 real routes (`/office`,
`/offers`, `/agents`, `/interviews`, `/archive`, `/analytics`, `/settings`), `/`
redirects to `/office`. New structure: `src/layout/` (Sidebar, AppShell, ComingSoon)
and `src/pages/` (one per route), added to the locked convention above. Real content
in Office (relocated Slice 2 dashboard, unchanged behavior), Agents (`AgentCard`
gained a `variant="compact"|"detailed"` prop, same real/not-connected data, no new
source), Archive (offers grouped by the real 7-value `status` enum via
`group-by-status.ts`, unit-tested as a drift tripwire against Python's
`VALID_STATUSES`). Offers/Analytics/Settings show a shared honest `ComingSoon`;
Interviews shows specific copy (applyr has no interview-scheduling date/time field,
only `status == 'in_process'` as a proxy — never fabricate a schedule). No backend
changes. 3 shared hooks extracted (`useIntakeAndJobs`, `useThresholds`,
`useSelectedJob`) once 2-3 pages needed the same fetch/polling — avoids the
duplication a straight per-page implementation would have produced. 13/13 Vitest,
771 Python tests still green (untouched backend). All 7 routes verified reachable via
direct URL/reload, not just sidebar clicks.

Also corrected in this pass: the Stack table above previously named TanStack Query and
Zustand as decided — neither was ever installed across 3 slices; corrected to reflect
what's actually in the codebase (plain `fetch`/`useState`/shared hooks).

**Slice 4 implemented (2026-08-23)** — `specs/visual-ui-slice-4-offers/spec.md`, status
IMPLEMENTED. Real `/offers` page replacing the `ComingSoon` stub: toggle between List
(filterable by status/work_mode, single-select each; min-score threshold; sortable by
date/score with a re-click-to-reverse direction) and Kanban (columns via the existing
`groupByStatus`, same filtered set as List, strictly read-only — no drag-and-drop). New
`features/jobs/offer-filters.ts` (pure `filterJobs`/`sortJobs`, 10 Vitest tests),
`OffersToolbar.tsx`, `KanbanBoard.tsx` — all built from existing `Button`/`Input`
primitives, zero new npm dependencies, zero backend changes. Detail panel reuses the
existing `useSelectedJob`/`JobDetail`; view/filter/sort state lives in `OffersPage` so
it survives opening/closing that panel. Manually verified against 246 real offers via
local dev servers (backend resolved from worktree cwd, frontend on Vite + CORS).
**Scope amendment during verification:** user flagged that `OfficePage.tsx` still
rendered the full unfiltered job list at the bottom — a duplication now that Offers
owns job browsing. Removed in the same PR: Office now shows only header + `AgentRow` +
`IntakeForm`/`PendingIntakeList` (agent status + intake queue, no offer browsing).
23/23 Vitest tests green, `tsc --noEmit` clean, both `/simplify-lean` passes returned
"no changes needed".

**"Applyr World" concept — proposed, deferred (2026-08-23):** user pitched a much
larger pivot for Office — an isometric/2.5D animated pipeline (PixiJS/Phaser), agents
physically walking offers through Scout → Analyst → Decision → CV/ATS/Writer stages,
driven by a real-time event bus (`offer.created`, `scoring.completed`, etc.). This
conflicts with 3 already-locked decisions above (polling-only/no WebSocket in v1,
Framer Motion 2D/CSS-only animation, no scale-oriented infra for a single local user)
and was classified as an **architectural** decision (high cost of reversal, new
render engine, new event contract) per the project's decision-classification rule —
not something to fold into a slice. **Agreed next step: a dedicated RADAR + ADR
session (would become ADR-012) before any implementation**, not bundled into current
work. Until then, Office keeps its simple ambient background image (see below).

**Slice 5 implemented (2026-08-23)** — `specs/visual-ui-slice-5-analytics/spec.md`,
status IMPLEMENTED. Real `/analytics` page replacing the `ComingSoon` stub. New
`GET /api/stats` + `GET /api/trends?period=week|month`, both thin wrappers around
`_stats_payload`/`_trends_payload` — extracted out of `cmd_stats`/`cmd_trends` in
`applyr/commands/analytics.py` as pure functions so the CLI and the API share one
aggregation implementation (behavior-preserving refactor, all 41 pre-existing
stats/trends tests still green). `funnel_pct` added to the JSON payload (both CLI
`--json` and the API) so the frontend never re-derives conversion percentages
client-side. Frontend: `features/analytics/` (FunnelChart, TrendChart with a
week/month toggle that is the one interaction in this slice allowed a second fetch,
BreakdownChart reused for channels/work-modes, StatCards for salary/score-calibration,
pure `analytics-data.ts` data-shaping unit-tested with 6 Vitest cases). First Recharts
usage in the project (see Stack table amendment above) — its categorical chart colors
(`--chart-1..6` in `index.css`) were previously unvalidated aliases of other tokens;
replaced with a teal-led reordering of the dataviz skill's default dark categorical
palette, re-validated with the CVD-safety script against the real `--background`
surface (all 6 checks PASS). 6 new backend tests (`tests/test_ui_api.py`
`TestStatsEndpoint`/`TestTrendsEndpoint`), full Python suite green (777 tests),
31/31 Vitest green, `tsc --noEmit` clean. Manually verified via curl against the
user's real 246-offer database (both endpoints return correctly shaped data); could
not visually confirm chart rendering in a browser — no browser-driving tool available
in this session, disclosed rather than assumed working. Dev servers left running
(backend :8000, frontend :5173) for the user to check `/analytics` directly.

**Slice 6 implemented (2026-08-23)** — `specs/visual-ui-slice-6-settings/spec.md`,
status IMPLEMENTED. Real `/settings` page replacing the `ComingSoon` stub, read-only.
New `GET /api/settings` returns `threshold_apply`/`threshold_maybe`, the raw integer
per-topic weights from `applyr.toml` (`config["weights_raw"]`, not the normalized
decimals `calculate_score` uses internally), and a CV Master `ok`/`warning` status
badge reusing `doctor`'s existing `_check_cv_master()` check — the API strips the
local filesystem path out of the message before it leaves the machine, extending the
same privacy boundary `GET /api/config` already established for `chrome_path`.
Frontend: `features/settings/` (`ThresholdsCard`, `WeightsCard`,
`CvMasterStatusBadge` with icon+text so status is never color-alone), no new npm
dependency (`Card`/`Badge` primitives only, no charts — this is config display, not
analytics). No editing/POST in this slice by design; editable settings deferred to a
future spec needing its own concurrency/validation analysis. 5 new backend tests
(happy path, missing CV master, too-thin CV master, 2 path-privacy assertions), full
Python suite green (776 tests), 25/25 Vitest, `tsc --noEmit` clean. Manually verified
`GET /api/settings` via curl against the user's real config (custom thresholds 65/55,
default weights, `cv_master_status: "ok"` with no path in the response); could not
visually confirm chart-free page rendering in a browser — no browser-driving tool
available this session, disclosed rather than assumed.

Next: office background image (user will generate a simple ambient illustration as a
placeholder — no characters, no baked-in text/data — to slot into the `.office-bg`
CSS hook already prepared in `index.css`; swappable later if "Applyr World" is
approved); then Interviews as it comes up (blocked on deciding whether
`status == 'in_process'` alone is enough or real interview-scheduling data should be
added to the schema first). Analytics and Settings are both done. Each slice still
gets its own `/sdd` spec.
