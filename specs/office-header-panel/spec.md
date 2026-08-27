## Spec: Office header + collapsible intake panel

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context
- `docs/visual-ui/AGENTS.md` (constitution): integration branch `feat/cc-visual-ui`,
  sub-PR base must be `feat/cc-visual-ui` (never `main`); no new npm dependencies
  without a real trigger; Framer Motion allowed everywhere except Office (that
  carve-out existed to reserve Office's animation budget for a future PixiJS scene);
  feature-based frontend structure (`features/<domain>/`, `layout/` is app chrome only,
  `pages/` stays thin); "never simulate/fake agent state" principle; polling-only
  real-time (no WebSocket).
- Engram #1990 (decision, 2026-08-28): user's explicit next-session priority — Office
  redesign flagged as "no se nos puede escapar." Own idea: descriptive header/nav +
  paste-offer box as a slide-out/collapsible panel instead of the current floating card.
- `docs/visual-ui/AGENTS.md` status log: the PixiJS "Applyr World" plan (ADR-012) that
  motivated the Framer-Motion-except-Office carve-out was superseded — Office now uses a
  static flow diagram (`specs/office-flow-diagram/spec.md`, IMPLEMENTED) instead of a
  PixiJS scene. The carve-out's original rationale no longer strictly applies, but the
  user confirmed (this session) to keep respecting it anyway — CSS/Tailwind transitions
  only, no Framer Motion added to Office.
- Corrected assumptions from Step 2 (all confirmed by user, no changes):
  1. "Active agents" = count of `state === "working"` in `deriveAgentStatuses` output.
  2. "Pending intake count" = `pendingIntake.length`.
  3. Panel animation: CSS/Tailwind `transition`, not Framer Motion.
  4. Panel open/closed state: local `useState`, resets to closed every page load.
  5. New components live in a new `features/office/` folder.
  6. Zero new npm dependencies.
  7. Toggle button has `aria-expanded`/`aria-controls`; panel content stays keyboard-reachable.
  8. Frontend-only change — no backend/Python changes.

### What does it do? (observable behavior, not implementation)
- Office page shows a header at the top with the page title and two live stats:
  pending intake count and active-agent count.
- The "paste a job offer" form + pending-intake list, currently a floating card
  overlapping the flow diagram, become a collapsible side panel that starts **closed**
  on every page load. A toggle button opens/closes it. When closed, the flow diagram is
  the only thing visible below the header.
- Both live stats and the panel's list content stay in sync with the existing polling
  (`useIntakeAndJobs`) — no new fetch behavior, no simulated/faked data.

### Acceptance criteria

- `[MUST]` Given a user opens `/office`, When the page loads, Then a header renders
  above the flow diagram showing the page title, the pending intake count, and the
  active-agent count.
- `[MUST]` WHEN `pendingIntake` or `jobs` change (via the existing polling interval)
  THE header stats SHALL update to reflect the new values (no stale counts).
- `[MUST]` Given a user opens `/office`, When the page first renders, Then the
  intake panel (form + pending list) SHALL be closed/hidden, and the flow diagram
  SHALL be the primary visible content.
- `[MUST]` Given the panel is closed, When the user clicks the toggle button, Then the
  panel SHALL open, showing `IntakeForm` and `PendingIntakeList` together in one panel.
- `[MUST]` Given the panel is open, When the user clicks the toggle button again, Then
  the panel SHALL close.
- `[MUST]` The toggle button SHALL expose `aria-expanded` matching the panel's current
  state and `aria-controls` referencing the panel's element id.
- `[SHOULD]` WHILE the panel is open THE panel SHALL be reachable and operable via
  keyboard (tab order, focus visible) — no keyboard trap.
- `[SHOULD]` The panel open/close transition SHALL use a CSS/Tailwind transition, not a
  new animation library dependency.
- `[SHOULD]` Given `pendingIntake.length === 0`, When the panel is open, Then the
  existing empty-state copy in `PendingIntakeList` ("Nothing pending — paste an offer
  above.") SHALL still render unchanged.
- `[COULD]` The header's active-agent count SHOULD use a subtle visual treatment
  (e.g. muted badge) consistent with the existing warm dark theme / teal primary —
  no new color tokens introduced without checking `index.css`.
- `[WONT]` This spec does NOT add a new backend endpoint, DB column, or persisted
  panel-state preference (e.g. localStorage) — panel always starts closed.
- `[WONT]` This spec does NOT change `IntakeForm`'s or `PendingIntakeList`'s internal
  submit/fetch logic — only how they're composed/wrapped on the page.

### Affected files
| File | Action | Reason |
|------|--------|--------|
| `applyr/ui/frontend/src/pages/OfficePage.tsx` | MODIFY | Compose new header + panel instead of the current floating card |
| `applyr/ui/frontend/src/features/office/OfficeHeader.tsx` | CREATE | Title + live stats (pending count, active-agent count) |
| `applyr/ui/frontend/src/features/office/office-stats.ts` | CREATE | Pure function deriving `{ pendingCount, activeAgentCount }` from existing hook data — unit-testable, no DOM |
| `applyr/ui/frontend/src/features/office/office-stats.test.ts` | CREATE | Vitest coverage for the pure stats function |
| `applyr/ui/frontend/src/features/office/IntakePanel.tsx` | CREATE | Collapsible wrapper composing `IntakeForm` + `PendingIntakeList`, owns open/closed state + toggle button |
| `applyr/ui/frontend/src/features/intake/IntakeForm.tsx` | READ | Reused unchanged inside `IntakePanel` |
| `applyr/ui/frontend/src/features/intake/PendingIntakeList.tsx` | READ | Reused unchanged inside `IntakePanel` |
| `applyr/ui/frontend/src/features/agents/agent-status.ts` | READ | `deriveAgentStatuses` output consumed by `office-stats.ts` |

### Dependencies
- APIs / endpoints used: none new — reuses `useIntakeAndJobs` (already polls existing
  `GET /api/intake` / `GET /api/jobs`).
- DB tables: none touched.
- Auth pattern: none (single-user local app).
- Reused components: `Button`, `Card` (`components/ui/`), Lucide icon for the toggle
  (e.g. `ChevronRight`/`ChevronLeft` or `PanelRightOpen`/`PanelRightClose`).

### Explicit assumptions
- We assume `deriveAgentStatuses(pendingIntake, jobs)` already returns per-agent
  `state` values including `"working"` → if the actual union type differs, adjust
  `office-stats.ts`'s filter predicate accordingly, but the derivation stays a pure
  function over already-computed data (no new state source).

### Non-functional requirements
- Accessibility: toggle button `aria-expanded`/`aria-controls`; panel content keyboard
  reachable when open; no color-only state indication (icon + `aria-expanded` together).
- Performance: no new network requests; stats are derived client-side from data already
  in memory on every existing poll tick.

### Edge cases / risks
- Zero pending intake + zero active agents → header still renders with `0`/`0`, not
  hidden (never a fake/misleading count).
- Panel open state does not persist across navigation away and back to `/office` — by
  design (`[WONT]` above); if this proves annoying in practice, a follow-up spec can
  add persistence.

### Task breakdown (execution order)
1. [x] `office-stats.ts` + unit tests (pure function, `pendingCount`/`activeAgentCount`) [S]
2. [x] `OfficeHeader.tsx` (title + stats, consumes `office-stats.ts`) [S]
3. [x] `IntakePanel.tsx` (toggle button + collapsible wrapper around existing `IntakeForm`/`PendingIntakeList`, CSS transition, starts closed) [M] — `inert` set imperatively via a ref/`useEffect` instead of the JSX attribute, since `@types/react` 18 doesn't type it
4. [x] Rewire `OfficePage.tsx` to compose `OfficeHeader` + `AgentFlowDiagram` + `IntakePanel` (remove the old floating-card `<section>`) [S]
5. [x] Manual verification against live dev servers (backend `applyr ui` :8000, frontend `npm run dev` :5173) via a headless-Chromium screenshot pass — closed state (header shows real `0 pending`/`1 agents active`) and open state (panel slides in with form + list, toggle label switches to "Close") both confirmed visually, zero console errors [S]

### Out of scope
- `[WONT]` Persisting panel state (localStorage) — always starts closed.
- `[WONT]` New backend endpoint or schema change.
- `[WONT]` Redesigning `AgentFlowDiagram` itself.
- `[WONT]` Framer Motion or any new animation dependency.

## Traceability Matrix

| AC | Priority | Description | Verification | Status |
|----|----------|--------------|---------------|--------|
| AC-01 | MUST | Header renders title + pending/agent stats | Manual: screenshot, `office-closed.png` shows "0 pending" / "1 agents active" | PASS |
| AC-02 | MUST | Stats stay in sync with polling | `office-stats.ts` is a pure function of `pendingIntake`/`agentStatuses`, re-derived every `OfficePage` render (each poll tick) — `office-stats.test.ts` (3 cases) | PASS |
| AC-03 | MUST | Panel closed on first render | `useState(false)` default; screenshot `office-closed.png` shows no panel, button reads "Paste offer" | PASS |
| AC-04 | MUST | Toggle opens panel with form+list | Manual: clicked toggle, `office-open.png` shows `IntakeForm` + `PendingIntakeList` together | PASS |
| AC-05 | MUST | Toggle closes panel again | Same handler (`setOpen(v => !v)`) drives both directions — code inspection, symmetric with AC-04 | PASS |
| AC-06 | MUST | `aria-expanded`/`aria-controls` on toggle | `IntakePanel.tsx` — `aria-expanded={open}`, `aria-controls={PANEL_ID}` | PASS |
| AC-07 | SHOULD | Keyboard reachable, no trap | `panelRef.current.inert = !open` (native DOM `inert`, removes closed panel from tab order and AT tree) — code inspection, not manually tab-tested | PASS (unverified by hand) |
| AC-08 | SHOULD | CSS transition, no new animation dep | Tailwind `transition-transform duration-200 ease-out` + `translate-x-*`; `package.json` unchanged (no new dependency) | PASS |
| AC-09 | SHOULD | Empty-state copy unchanged | `PendingIntakeList` untouched; `office-open.png` shows "Waiting for your agent (0)" / "Nothing pending..." | PASS |

Coverage gap: AC-07 (keyboard trap) was verified by code inspection (the `inert` DOM API is
the standard mechanism for this and is well-supported), not by an actual Tab-key walk —
no keyboard-driving step was scripted this session. Low risk given `inert` is a native
platform primitive, not custom focus-trap logic, but flagged here rather than silently
assumed.

Drift check: no scope creep — all touched files match the "Affected files" table above.
`/adversarial-test` not run — UI-only change, not on the auth/money/migration/state-machine
trigger list.
