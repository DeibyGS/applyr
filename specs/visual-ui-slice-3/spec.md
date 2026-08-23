# Spec: Visual UI — Slice 3 (sidebar navigation shell)

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context

- **Project constitution:**
  - `docs/visual-ui/AGENTS.md` — invariants: engine unchanged, AI agent remains the
    sole reasoner, no Postgres/Redis/Celery/auth/Docker, no WebSocket, no 3D/Canvas,
    stack = FastAPI + SQLite + React/TS/Vite + Tailwind + shadcn/ui + Framer Motion.
    "Frontend structure" section: feature-based domain folders (`features/<domain>/`),
    `api/` as the sole HTTP boundary, `components/ui/` shadcn-only, tests colocated.
  - `specs/visual-ui-slice-2/spec.md` (Slice 2, IMPLEMENTED, merged) — design system
    (warm graphite/teal/copper, Fraunces/Inter, WCAG AA verified), `AgentRow`/
    `AgentCard`, `JobList`/`JobCard`/`JobDetail`, `IntakeForm`/`PendingIntakeList`,
    `api/{client,intake,jobs,config}.ts`, `GET /api/config`.
  - ADR-011 — Visual UI is optional/additive; base CLI unaffected. Still true — this
    slice only touches `applyr/ui/frontend/`, no backend changes.
- **Relevant ADRs:** 003, 005, 011. No conflicts.
- **Engram:** Slice 1/2 decisions recovered; nothing prior for a nav shell.
- **Corrected assumptions from Step 2 (user-confirmed 2026-08-23):**
  1. `react-router` v8 (the current unified package, not legacy `react-router-dom`),
     plain declarative `<BrowserRouter>`/`<Routes>` — no loaders/actions needed.
  2. `/` redirects to `/office`.
  3. Routes and sidebar labels in English, matching Slice 2's existing UI copy
     ("Paste a job offer", "Waiting for your agent", etc.).
  4. New top-level `src/pages/` folder (alongside the confirmed `src/layout/`) — one
     file per route, each composing existing `features/*` building blocks. Logical
     extension of needing route-level compositions that don't belong to one domain.
  5. Archivador (`/archive`) groups strictly by the real `offers.status` enum (7
     values: pending/applied/waiting/in_process/rejected/discarded/offer) — not the
     reference mockup's invented buckets ("Nuevas"/"Analizando"/"Pendiente decisión"),
     which don't map to a single real status value.
  6. Sidebar stays fixed/always-visible this slice; a mobile collapse/hamburger
     pattern is deferred, not a blocker.
  7. One shared `ComingSoon` component for Offers/Analytics/Settings; Interviews gets
     a more specific placeholder explaining applyr has no real interview-scheduling
     data yet (only `status == 'in_process'` as a proxy).
  8. `AgentCard` gains an optional `variant?: "compact" | "detailed"` prop (default
     `"compact"`) rather than a duplicate component — `/agents` uses `"detailed"`.
  9. Office background: build `/office` now with a solid fallback (today's page
     background color — i.e., no visible change until an image exists), structured
     so adding the user's background image later is a one-line CSS change, not a
     layout rework.

### What does it do? (observable behavior, not implementation)

- The dashboard now has a persistent left sidebar with 7 real destinations, each its
  own URL: Office, Offers, Agents, Interviews, Archive, Analytics, Settings.
- Office (`/office`) is today's dashboard content (agent row + intake + job list/detail)
  relocated under the shell, ready to take a background illustration later without
  layout changes.
- Agents (`/agents`) shows the same 5 agents as the compact row, in a larger, more
  detailed layout — same real/idle/not-connected states, no new data.
- Archive (`/archive`) shows every real offer grouped into 7 sections by its actual
  status.
- Offers, Interviews, Analytics, Settings are visible and navigable but honestly show
  "coming soon" — never fabricated content.
- Reloading the page on any tab keeps you on that tab (real URLs, not just client state).

### Acceptance criteria

#### Routing & shell
- `[MUST]` The system shall render a persistent sidebar with exactly 7 links: Office,
  Offers, Agents, Interviews, Archive, Analytics, Settings.
- `[MUST]` WHEN the user navigates to `/` THE system SHALL redirect to `/office`.
- `[MUST]` WHEN the user navigates directly to any of the 7 routes (e.g. via reload or
  a typed URL) THE system SHALL render that page — no route requires client-side
  state carried from another page.
- `[MUST]` WHILE a route is active THE system SHALL visually mark its sidebar link as
  current (e.g. active state), determined from the real URL, not a separate manually
  synced state variable.
- `[SHOULD]` The sidebar link order shall match: Office, Offers, Agents, Interviews,
  Archive, Analytics, Settings.

#### Office page
- `[MUST]` The `/office` page shall render the same agent row, intake form, pending
  list, and job list/detail behavior Slice 2 shipped — no information removed.
- `[MUST]` The page's background shall use a single, centrally defined style (e.g. one
  CSS class) so that adding a background image later requires changing that one
  definition, not the page's layout markup.

#### Agents page
- `[MUST]` The `/agents` page shall render all 5 agents using `AgentCard` with
  `variant="detailed"` — larger illustration, role description always visible
  (never truncated), same real Recruiter/Matching data and honest
  CV/ATS/Application "not connected" state as the compact row.
- `[MUST]` The system shall never introduce a data source for this page beyond what
  `deriveAgentStatuses` already provides from Slice 2.

#### Archive page
- `[MUST]` WHEN `/archive` renders THE system SHALL group all offers from `GET
  /api/jobs` into exactly 7 sections, one per `VALID_STATUSES` value, using each
  offer's real `status` field.
- `[MUST]` IF a status section has zero offers THEN the system SHALL still show the
  section with a real "0" count, not hide it.
- `[SHOULD]` Each section should show its count in the section header (e.g. "Applied
  (14)").

#### Coming-soon pages
- `[MUST]` The `/offers`, `/analytics`, and `/settings` routes shall render a shared
  `ComingSoon` component — no fabricated data, no preview content.
- `[MUST]` The `/interviews` route shall render a placeholder explaining specifically
  that applyr has no interview-scheduling data yet (distinct copy from the generic
  `ComingSoon` message) — never a fabricated date/time list.

#### Structure
- `[MUST]` Sidebar/shell chrome shall live in `src/layout/` (`Sidebar.tsx`,
  `AppShell.tsx`), never inside `features/` or `components/ui/`.
- `[MUST]` Route-level page compositions shall live in `src/pages/`, one file per
  route, composing existing `features/*` components — no business logic duplicated
  from `features/`.

### Affected files

| File | Action | Reason |
|---|---|---|
| `applyr/ui/frontend/package.json` | MODIFY | Add `react-router` |
| `applyr/ui/frontend/src/main.tsx` | MODIFY | Wrap root in `<BrowserRouter>` |
| `applyr/ui/frontend/src/App.tsx` | MODIFY | Becomes route definitions (`<Routes>`), not page content |
| `applyr/ui/frontend/src/layout/AppShell.tsx` | CREATE | Sidebar + `<Outlet />` content area |
| `applyr/ui/frontend/src/layout/Sidebar.tsx` | CREATE | 7 nav links, active-state from real URL (`NavLink`) |
| `applyr/ui/frontend/src/layout/ComingSoon.tsx` | CREATE | Shared honest placeholder |
| `applyr/ui/frontend/src/pages/OfficePage.tsx` | CREATE | Today's dashboard content, moved from `App.tsx` |
| `applyr/ui/frontend/src/pages/AgentsPage.tsx` | CREATE | Detailed agent grid |
| `applyr/ui/frontend/src/pages/ArchivePage.tsx` | CREATE | Offers grouped by real status |
| `applyr/ui/frontend/src/pages/OffersPage.tsx` | CREATE | `ComingSoon` |
| `applyr/ui/frontend/src/pages/InterviewsPage.tsx` | CREATE | Specific "no scheduling data" placeholder |
| `applyr/ui/frontend/src/pages/AnalyticsPage.tsx` | CREATE | `ComingSoon` |
| `applyr/ui/frontend/src/pages/SettingsPage.tsx` | CREATE | `ComingSoon` |
| `applyr/ui/frontend/src/features/agents/AgentCard.tsx` | MODIFY | Add `variant?: "compact" \| "detailed"` prop |
| `applyr/ui/frontend/src/features/jobs/group-by-status.ts` | CREATE | Pure function: `JobSummary[]` -> grouped by `VALID_STATUSES`, unit-tested |
| `applyr/ui/frontend/src/features/jobs/group-by-status.test.ts` | CREATE | Unit tests incl. empty-section case |
| `applyr/ui/frontend/src/index.css` | MODIFY | Add the single office-background style hook |
| `applyr/ui/frontend/src/hooks/useIntakeAndJobs.ts` | CREATE | Not in original plan — extracted once Office/Agents/Archive all needed the same polling |
| `applyr/ui/frontend/src/hooks/useThresholds.ts` | CREATE | Same reason — 3 pages needed real thresholds |
| `applyr/ui/frontend/src/hooks/useSelectedJob.ts` | CREATE | Same reason — Office/Archive both needed fetch-on-select |
| `docs/visual-ui/AGENTS.md` | MODIFY | Status update; document `pages/`/`layout/` addition to the structure section; corrected a stale Stack table entry (TanStack Query/Zustand never adopted) |

### Dependencies

- New frontend dep: `react-router` (v8, current major).
- No backend/DB changes — reads only `GET /api/jobs` and `GET /api/intake` (both
  already exist from Slice 1/2).

### Explicit assumptions

- We assume the 7 real `VALID_STATUSES` values are stable enough to hardcode as
  Archive's 7 sections → if applyr ever adds a new status value, `group-by-status.ts`
  needs updating; a unit test asserting the exact 7-value set will fail loudly if the
  Python and TS enums drift, which is the intended safety net rather than importing a
  shared source of truth across languages (out of scope for this slice).
- We assume no user is deep in a multi-step flow when this ships — moving `/office`'s
  content from `App.tsx` to `pages/OfficePage.tsx` is a pure relocation, not a
  behavior change; regression coverage is "identical Slice 2 behavior after the move,"
  not new functionality.

### Non-functional requirements

- **Performance:** route transitions are client-side (react-router), no full page
  reload between tabs.
- **Accessibility:** sidebar links are real `<a>`-rendering `NavLink`s (keyboard/tab
  navigable, screen-reader-visible current-page state via `aria-current`), not
  click-only `<div>`s. Same WCAG AA contrast tokens from Slice 2 apply throughout.

### Edge cases / risks

- **Risk:** silently duplicating business logic into `pages/` instead of composing
  `features/*` would violate the locked structure and create drift → mitigated by the
  explicit AC forbidding it and a code-review check during Step 6.
- **Risk:** hardcoding the 7 status values in two places (Python `VALID_STATUSES`,
  TS `group-by-status.ts`) can drift if one changes without the other → mitigated by
  a unit test asserting the exact set, acting as a tripwire, not by a shared source of
  truth (explicitly out of scope this slice — would require exposing an enum endpoint).
- **Risk:** moving Office's content out of `App.tsx` could silently drop behavior
  (polling, error handling) during the refactor → mitigated by treating this as a pure
  relocation task with an explicit manual pass confirming identical behavior.

### Task breakdown (execution order)

1. [x] Install `react-router` v8; `App.tsx` restructured into `<BrowserRouter>` +
   route definitions; `AppShell` + `Sidebar` (`layout/`) [M]
2. [x] `ComingSoon` component + `OffersPage`/`AnalyticsPage`/`SettingsPage` (all reuse
   it) + `InterviewsPage` (specific copy) [S]
3. [x] `OfficePage` — relocated Slice 2's `App.tsx` content, refactored onto shared
   `useIntakeAndJobs`/`useThresholds`/`useSelectedJob` hooks (extracted this slice
   once Agents/Archive needed the same data — not in the original file list, added
   during implementation to avoid the 3-way duplication a literal per-page port
   would have produced) [M]
4. [x] `AgentCard` `variant` prop + `AgentsPage` (detailed grid) [M]
5. [x] `group-by-status.ts` pure function + unit tests (incl. a Python-enum drift
   tripwire) + `ArchivePage` [M]
6. [x] Office background CSS hook (`.office-bg`, solid fallback) [S]
7. [x] Accessibility pass — satisfied by construction: `NavLink` provides
   `aria-current`/keyboard nav natively, no new color tokens introduced (reused
   Slice 2's WCAG-AA-verified set), no new Framer Motion to gate on
   `prefers-reduced-motion` [S]
8. [x] Manual visual verification: all 7 routes return 200 on direct URL/reload
   (curl-verified, not just sidebar-navigated), served content confirmed correct [S]
9. [x] Update `docs/visual-ui/AGENTS.md` Status + structure section — also corrected
   a stale Stack table entry (TanStack Query/Zustand were never actually adopted
   across 3 slices; fixed while already editing this file) [S]

## Traceability Matrix

| AC | Priority | Description | Verified by | Status |
|---|---|---|---|---|
| 7 sidebar links | [MUST] | Exactly Office/Offers/Agents/Interviews/Archive/Analytics/Settings | `Sidebar.tsx` `NAV_ITEMS`; visual confirmation | PASS |
| `/` redirects to `/office` | [MUST] | Default route | `App.tsx` `<Route index element={<Navigate .../>} />`; curl confirmed 200 on `/` reaching Office content | PASS |
| Direct navigation works | [MUST] | No route needs carried client state | All 7 routes curl-verified 200 on direct request, not just via sidebar click | PASS |
| Active link marked from real URL | [MUST] | No manually synced state | `NavLink`'s built-in `isActive` (URL-derived, not a separate variable) | PASS |
| Office unchanged behavior | [MUST] | Same fields/polling as Slice 2 | Manual diff: `OfficePage.tsx` is `App.tsx`'s content, refactored onto shared hooks with identical external behavior; `tsc`/`vitest`/`vite build` all clean | PASS |
| Office background single hook | [MUST] | One CSS class, not scattered | `.office-bg` in `index.css`, one usage site in `OfficePage.tsx` | PASS |
| Agents page — same data, detailed variant | [MUST] | No new data source | `AgentsPage.tsx` calls the same `deriveAgentStatuses` as Office; `AgentCard` `variant` prop is presentation-only | PASS |
| Archive groups by real status | [MUST] | Exactly 7 sections | `group-by-status.test.ts` (4 tests incl. drift tripwire + empty-section case) | PASS |
| Coming-soon pages, no fabricated data | [MUST] | Offers/Analytics/Settings/Interviews | `ComingSoon.tsx` + 4 thin page wrappers, no data fetching in any of them | PASS |
| Layout in `layout/`, pages in `pages/` | [MUST] | Structure convention | File tree matches; `AGENTS.md` updated | PASS |

Every `[MUST]` AC verified. `[SHOULD]` items (sidebar order, section counts in
headers) implemented and spot-checked, no dedicated automated test — consistent with
Slice 2's established split (pure logic gets unit tests, presentational/visual
behavior gets manual verification).

### Drift check

- **Scope drift (beneficial, documented):** 3 shared hooks (`useIntakeAndJobs`,
  `useThresholds`, `useSelectedJob`) were added beyond the original file list once
  implementation revealed 2-3 pages needed identical fetch/polling logic. Caught by
  a `/simplify-lean` review mid-implementation. Documented here and in
  `docs/visual-ui/AGENTS.md` rather than silently left out of the spec record.
- **Coverage gap:** none found for `[MUST]` ACs.
- **Behavior drift:** none — Office's behavior is unchanged from Slice 2 by
  construction (pure relocation + hook refactor, no new fields/logic).
- **Out-of-scope guardrails:** verified — no `GET /api/stats`, no config-write
  endpoint, no fabricated interview schedule, no Kanban drag-and-drop, no mobile
  sidebar collapse.
- **Unplanned fix:** `docs/visual-ui/AGENTS.md`'s Stack table incorrectly named
  TanStack Query and Zustand as decided technology; neither was ever installed across
  3 slices. Corrected while already editing the file for this slice's status update —
  a documentation-accuracy fix, not a scope or behavior change.

### Adversarial verification

Not run. Same reasoning as Slice 2 — this slice's risk category is
presentation/navigation, not auth/money/data-integrity/migration/state-machine/
idempotency. No backend changes at all this slice (verified: `applyr/` Python source
untouched, 771 tests unchanged).

### Out of scope

- `[WONT]` Real content for Offers, Interviews, Analytics, Settings — each gets its
  own future slice.
- `[WONT]` `GET /api/stats` endpoint (Analytics needs it, deferred with that slice).
- `[WONT]` Editable Settings / config-write endpoint (deferred, needs its own
  concurrency/validation-focused spec per Slice 2's scoping notes).
- `[WONT]` Mobile sidebar collapse/hamburger toggle.
- `[WONT]` The actual office background image (user generates it separately; this
  slice only prepares the hook to add it without a layout rework).
- `[WONT]` Kanban drag-and-drop on the Archive page — this slice is read-only grouped
  display, not the interactive board from earlier scoping (that remains a separate,
  larger future slice if still wanted).
