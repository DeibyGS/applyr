## Spec: Office flow diagram (replaces the spatial PixiJS scene)

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context
- Classified as **architectural** (high cost of reversal): deletes an entire subsystem
  spanning 26 files across 7 PRs (#96-#100) and changes the primary visual identity of
  the product. Per `~/.claude/rules/pre-spec-questions.md`, a RADAR summary follows.
- `specs/visual-ui-slice-3/spec.md` introduced `AgentCard`/`deriveAgentStatuses` — this
  spec keeps that data layer as-is, only changes how agents are laid out and animated.
- `specs/agent-queue-modal/spec.md` (this session, IMPLEMENTED) — the thought-bubble +
  read-only modal system built minutes ago. Carries over unchanged in logic; gets visual
  polish (bigger trigger) and moves to live on this new merged page.
- Docs ADR-013 (`docs/adr/013-applyr-world-movement-and-push-transport.md`) — defined the
  SSE transport (`/api/events`, `/api/events/enriched`) this spec reuses as-is. Nothing
  about the transport changes; only the consumer (a spatial scene → a flow diagram).
- No Engram decision found for "flow diagram" / "abandon spatial office" before this
  session's own discussion (saved at the end of this spec, topic
  `decision/office-flow-diagram-replaces-spatial-scene`).

#### RADAR
- **Requirements**: the Office view needs to communicate "5 agents, each doing a real
  step of the pipeline, handing work to the next" in a way that reads as intentional and
  polished, without demanding the ongoing animation/art investment a 2D spatial scene
  needs to look right.
- **Alternatives considered**: (1) keep investing in the PixiJS spatial scene (sprites
  walking between desks); (2) a static list/table of agent states (loses the "handoff"
  narrative entirely); (3) the chosen option — a fixed 5-node diagram with connecting
  lines and an animated pulse on real handoff events.
- **Differences**: (1) requires continued animation/art polish with no clear ceiling —
  23 tests already broken, user's own assessment is "not landing" after 7 PRs of work.
  (2) is trivial to build but throws away the pipeline narrative the user explicitly
  wants to keep. (3) is a well-trodden UI pattern (CI/CD pipeline views, Zapier/n8n flow
  diagrams) — cheap to make look polished, keeps the narrative, and the real handoff SSE
  events (`handoff.started`/`handoff.completed`, already emitted by the CLI, already
  streamed, currently unused by anything after this change) plug directly into it.
- **Analysis**: option 3 fits — lowest ongoing cost, keeps the pipeline narrative, reuses
  the illustrations the user already likes, and composes with the queue-modal work just
  shipped (same card, same badge, same bubble).
- **Risks**: deleting 26 files is a large diff to review carefully; real-art assets tied
  to sprites (desks, walk-cycle frames) become unused (not deleted by this spec — see Out
  of scope); the SVG line/pulse layer needs to reflow correctly on window resize (a
  concrete AC below, not left implicit).

### What does it do? (observable behavior, not implementation)
- The spatial PixiJS Office scene is gone. `/office` and `/agents` merge into a single
  page: a fixed 5-node diagram (Recruiter + Matching on top, CV + ATS on bottom,
  Application on the right) using the same illustrations already in `AGENT_CONFIG`,
  connected by lines that trace the real pipeline order
  (Recruiter→Matching→CV→ATS→Application). The existing "Paste a job offer" intake form
  and pending-intake list stay, unchanged, alongside the diagram.
- Each node is the existing `AgentCard`, enhanced: an animated glow traces its border in
  a loop while `state === "working"` (stops when idle); the "thought bubble" trigger
  (from `specs/agent-queue-modal/`) is bigger and has a subtle invite-to-click motion;
  the state badge drops the literal words "Idle"/"Working" for short, playful,
  sim-game-flavored copy per agent (see table below — confirm/edit before implementation).
- When a real `handoff.started` or `handoff.completed` SSE event arrives for a pair of
  adjacent agents in the chain, a small light travels along that connecting line once,
  in the real direction of the handoff. Purely a "something just moved" signal — no
  numeric progress (confirmed: decorative, not tied to a real completion percentage).
- `/agents` becomes a redirect to `/office`. The sidebar's "Agents" entry is removed.

### Proposed badge copy (confirm before implementation)

| Agent | Idle | Working |
|-------|------|---------|
| Recruiter | "Grabbing a coffee ☕" | "Reading a new offer" |
| Matching | "Waiting for offers" | "Crunching the numbers" |
| CV | "Sharpening pencils ✏️" | "Tailoring your CV" |
| ATS | "On standby" | "Running the checks" |
| Application | "Ready when you are" | "Sealing the envelope ✉️" |

The existing detail line beneath the badge (`taskText()` — e.g. "Acme Corp — 91% match",
"2 offers in CV stage") is untouched; only the short badge pill changes.

### Acceptance criteria

- `[MUST]` The system shall render exactly 5 `AgentCard` nodes in a fixed layout: top row
  (Recruiter, Matching), bottom row (CV, ATS), Application positioned to the right of
  both rows.
- `[MUST]` The system shall draw 4 connecting lines matching the real pipeline order
  (Recruiter→Matching, Matching→CV, CV→ATS, ATS→Application) — no line for any other
  pair.
- `[MUST]` WHILE an agent's `state === "working"` THE system SHALL show a looping
  animated glow along that card's border; it SHALL stop when `state` returns to `"idle"`.
- `[MUST]` WHEN a `handoff.started` or `handoff.completed` event arrives (via the
  existing `useHandoffEvents()` hook) for a `from_agent`/`to_agent` pair that has a
  drawn connecting line THEN the system SHALL animate a light traveling along that line
  once, in the `from → to` direction.
- `[MUST]` IF the event's `from_agent`/`to_agent` pair has no drawn line (shouldn't occur
  given the real pipeline only emits adjacent-pair handoffs, but defensive) THEN the
  system SHALL silently ignore it — never throw.
- `[MUST]` The connecting lines SHALL reposition correctly on window resize (recalculate
  anchor points from each card's real DOM position, not hardcoded pixel coordinates).
- `[MUST]` WHEN the badge state changes (idle↔working) THE system SHALL show the copy
  from the table above for that agent — no agent shall ever show the literal words
  "Idle" or "Working".
- `[MUST]` `/agents` SHALL redirect to `/office`. The sidebar SHALL NOT list a separate
  "Agents" entry.
- `[MUST]` The "Paste a job offer" form and pending-intake list SHALL render on the
  merged page exactly as they do today (`IntakeForm`/`PendingIntakeList` are reused
  unchanged).
- `[SHOULD]` The thought-bubble trigger SHALL be visibly larger than its current size and
  SHALL carry a subtle animation (e.g. gentle scale pulse) to read as clickable, not just
  decorative.
- `[SHOULD]` `useHandoffEvents()`'s SSE connection SHALL be established once per page
  (not once per card) — a single subscription drives all 4 line-pulse animations.
- `[COULD]` A small on-hover tooltip on each connecting line naming the two agents it
  joins (helps at a glance, cheap to add, not required for v1).
- `[WONT]` Numeric/percentage progress on the traveling light — `notify_handoff_walking`
  exists server-side but is never called anywhere in the codebase (confirmed via grep);
  wiring it up is a separate, future decision, not this spec's scope.
- `[WONT]` Porting `TerminalPanel.tsx` (existing DOM-based event-log view, not
  PixiJS-dependent) or `AgentInspector.tsx` (DOM-based tabbed detail panel) to the new
  page — both are cut for scope, not because they're bad; `AgentInspector`'s job
  (click an agent, see detail) is already superseded by the queue modal. If real usage
  later wants a raw event log back, `TerminalPanel` + the relocated `EventBus` (see
  Affected files) are a cheap add — nothing about this spec makes that harder.
- `[WONT]` Deleting the real-art sprite/desk image assets themselves
  (`specs/visual-ui-applyr-world-real-art/`) — only the PixiJS code that rendered them.
  Confirm separately if those asset files should also go; not assumed here.

### Affected files

**New / relocated (generic, reusable — not PixiJS-dependent):**
| File | Action | Reason |
|------|--------|--------|
| `applyr/ui/frontend/src/lib/event-bus.ts` | CREATE (moved from `features/office-scene/event-bus.ts`) | Framework-agnostic pub/sub, zero Pixi/React dependency (confirmed by reading it) — `useApplyrEvents.ts` needs it and survives this change. |
| `applyr/ui/frontend/src/lib/applyr-events.ts` | CREATE (extracted from `features/office-scene/types.ts`) | `BaseApplyrEvent`, `Agent*Event`/`Handoff*Event` variants, `ApplyrEvent` union, `isHandoffEvent`/`isAgentEvent`/`isPipelineEvent` guards — the real event shapes `useHandoffEvents()` needs. Leaves the PixiJS-only types (`AgentVisualState`, `VisualProps`, `WorkArtifact*`) behind to be deleted with the rest. |
| `applyr/ui/frontend/src/hooks/useApplyrEvents.ts` | MODIFY | Two import lines repointed to the new `lib/` locations. No behavior change. |

**New (this feature):**
| File | Action | Reason |
|------|--------|--------|
| `applyr/ui/frontend/src/features/agents/AgentFlowDiagram.tsx` | CREATE | Lays out the 5 `AgentCard`s in the fixed grid, renders the SVG connecting-line layer, subscribes to `useHandoffEvents()` to trigger line-pulse animations. |
| `applyr/ui/frontend/src/features/agents/badge-copy.ts` | CREATE | The idle/working copy table above, keyed by `AgentId` — single source of truth so `AgentCard` doesn't hardcode strings inline. |

**Modified:**
| File | Action | Reason |
|------|--------|--------|
| `applyr/ui/frontend/src/features/agents/AgentCard.tsx` | MODIFY | Border-glow-while-working effect (CSS/SVG, no Pixi), bigger+animated bubble trigger, badge text sourced from `badge-copy.ts` instead of "Idle"/"Awaiting decision". |
| `applyr/ui/frontend/src/pages/OfficePage.tsx` | MODIFY (rewrite) | Drops `<OfficeScene>`, renders `<AgentFlowDiagram>` instead; `IntakeForm`/`PendingIntakeList` untouched. |
| `applyr/ui/frontend/src/App.tsx` | MODIFY | `agents` route becomes `<Navigate to="/office" replace />`. |
| `applyr/ui/frontend/src/layout/Sidebar.tsx` | MODIFY | Remove the "Agents" `NAV_ITEMS` entry. |

**Deleted (spatial PixiJS scene, superseded):**
| File | Reason |
|------|--------|
| `applyr/ui/frontend/src/pages/AgentsPage.tsx` | Folded into the merged `/office` page. |
| `applyr/ui/frontend/src/features/office-scene/OfficeScene.tsx` | Top-level Pixi orchestrator. |
| `applyr/ui/frontend/src/features/office-scene/PixiStage.tsx` | Pixi canvas mount. |
| `applyr/ui/frontend/src/features/office-scene/agent-sprite.ts` (+`.test.ts`) | Pixi sprite rendering + its 9 pre-existing-failing tests. |
| `applyr/ui/frontend/src/features/office-scene/agent-bubble.tsx` | Pixi speech bubble — superseded by the queue modal. |
| `applyr/ui/frontend/src/features/office-scene/agent-state-machine.ts` (+`.test.ts`) | Spatial-scene-only state machine (idle/working/receiving/blocked/…) — the diagram only needs the existing binary `AgentStatus.state`. |
| `applyr/ui/frontend/src/features/office-scene/animation-tokens.ts` | Pixi animation constants. |
| `applyr/ui/frontend/src/features/office-scene/movement-controller.ts` | Sprite walk/movement logic. |
| `applyr/ui/frontend/src/features/office-scene/movement-utils.ts` | Sprite tweening helpers. |
| `applyr/ui/frontend/src/features/office-scene/pipeline-sprites.ts` (+`.test.ts`, `.adversarial.test.ts`) | Sprite slotting/zone logic + its 7 pre-existing-failing tests. |
| `applyr/ui/frontend/src/features/office-scene/pixi-lifecycle.ts` (+`.test.ts`) | Pixi app lifecycle management. |
| `applyr/ui/frontend/src/features/office-scene/scene-layout.ts` (+`.test.ts`) | Spatial zone-position math + its 2 pre-existing-failing tests. |
| `applyr/ui/frontend/src/features/office-scene/scene-scenery.ts` (+`.test.ts`) | Desk/scenery rendering + its 1 pre-existing-failing test. |
| `applyr/ui/frontend/src/features/office-scene/textures.ts` (+`.test.ts`) | Sprite texture loading + its 3 pre-existing-failing tests. |
| `applyr/ui/frontend/src/features/office-scene/work-artifact-sprite.ts` | Pixi artifact icon sprites. |
| `applyr/ui/frontend/src/features/office-scene/pipeline-definition.ts` | Spatial zone/pipeline layout definition, superseded by the fixed grid + real `AgentId` order. |
| `applyr/ui/frontend/src/features/office-scene/TerminalPanel.tsx` | DOM-based, not Pixi — cut for scope per `[WONT]` above, not because it's broken. |
| `applyr/ui/frontend/src/features/office-scene/AgentInspector.tsx` | DOM-based — superseded by the queue modal per `[WONT]` above. |
| `applyr/ui/frontend/src/features/office-scene/types.ts` | Split: event-shape types move to `lib/applyr-events.ts`; everything else (Pixi-only) deleted with the directory. |
| `applyr/ui/frontend/src/features/office-scene/` (directory itself) | Removed once empty. |

### Dependencies
- APIs/endpoints used: `GET /api/events/enriched` (existing, via `useHandoffEvents()` —
  no backend change). `GET /api/jobs` + `GET /api/intake` (existing, via
  `useIntakeAndJobs()` — unchanged).
- UI primitives: plain SVG (`<svg>`, `<path>`, `<circle>` with `<animateMotion>` or CSS
  `offset-path`) for the connector lines + traveling light — no new dependency. The
  border-glow can be pure CSS (`@property`/conic-gradient mask or an animated SVG
  `stroke-dashoffset` on a rounded-rect outline) — no new dependency either.
- `pixi.js` and `gsap` become unused by the frontend once this ships (only office-scene
  imported them) — NOT removed from `package.json` by this spec (see Out of scope);
  flagging so it isn't a surprise when `npm run build`'s bundle shrinks.

### Explicit assumptions
- We assume the merged page keeps the `/office` URL (not `/agents`) — "Office"/"Applyr
  Office" is the existing on-page branding and the more narrative name.
- We assume the badge copy table above is a starting proposal, not final — the approval
  gate (spec confirmation) is where it gets edited, not a separate round-trip after
  implementation.
- We assume "bigger" bubble trigger means a concrete, noticeably larger hit target and
  icon (current: `size-4`, ~16px, in a `p-1` button) — will size it closer to `size-6`+
  in a `p-2` button with a hover/idle micro-animation, not a vague nudge.

### Non-functional requirements
- Performance: SVG line recalculation on resize uses a single `ResizeObserver` on the
  diagram container (not a `window.resize` listener firing on every layout pass
  elsewhere in the app).
- Accessibility: the connecting lines and traveling light are decorative (`aria-hidden`)
  — the real state (idle/working, handoff just happened) is still conveyed through the
  existing text badge/detail line for screen readers, not only visually.

### Edge cases / risks
- Multiple handoff events arriving in quick succession for the same line (e.g. a very
  fast `cv generate` immediately followed by `cv review`) — each triggers its own pulse;
  overlapping pulses on the same line are acceptable for v1, not deduplicated/queued.
- Browser tab backgrounded during a pulse animation — CSS animations pause naturally
  when `requestAnimationFrame` throttles in a background tab; no special handling needed.
- Deleting `office-scene/` removes its 23 pre-existing-failing tests as a side effect —
  documented so it doesn't read as "tests silently disappeared" in a future diff review.

### Task breakdown (execution order)
1. [x] Relocate `event-bus.ts` → `lib/event-bus.ts` and extract event types →
   `lib/applyr-events.ts`; repoint `useApplyrEvents.ts`'s two imports. [M]
2. [x] Create `badge-copy.ts` with the confirmed copy table (used as proposed, no edits
   requested at the approval gate). [S]
3. [x] Update `AgentCard.tsx` — badge copy, bigger/animated bubble trigger (`size-4`→
   `size-6`, `p-1`→`p-2`, `animate-pulse` + hover scale), border-glow while working
   (depends on 2). [M]
4. [x] Create `AgentFlowDiagram.tsx` — fixed grid layout of 5 `AgentCard`s + SVG connector
   lines with `ResizeObserver` repositioning (depends on 3). [L]
5. [x] Wire `useHandoffEvents()` into `AgentFlowDiagram.tsx` for the line-pulse animation
   (depends on 1, 4). [M]
6. [x] Rewrite `OfficePage.tsx` to use `AgentFlowDiagram` instead of `OfficeScene` (depends
   on 4). [S]
7. [x] Update `App.tsx` (redirect) + `Sidebar.tsx` (remove Agents entry) + delete
   `AgentsPage.tsx`. [S]
8. [x] Delete the rest of `features/office-scene/` (the full list in Affected files). [S]
9. [x] Manual verification — Playwright against the real dev server: diagram renders
   with real data (5 nodes, correct grid position), badge copy shows for idle/working,
   border-glow confirmed via computed-style inspection (real `conic-gradient` +
   animating `--glow-angle`, not just class presence) and visually after increasing
   its intensity (first pass was too subtle), a REAL handoff fired via
   `applyr cv generate <id>` on a disposable temp offer (added, tested, deleted —
   never touched real data) produced a pulse circle confirmed via DOM polling, window
   resize confirmed to reposition the SVG lines (`ResizeObserver` verified via
   before/after `boundingBox()`), `/agents` redirects to `/office`, zero console
   errors/warnings. [M]
10. [x] Ran `vitest` + `tsc --noEmit` — 42/42 tests pass (7 files, down from 15); the 23
    previously-failing tests are gone because their files were deleted, not "fixed". [S]

## Traceability Matrix

| AC ID | Priority | AC Description | Test File | Implementation File | Status |
|-------|----------|-----------------|-----------|----------------------|--------|
| AC-01 | [MUST] | 5 nodes in fixed layout (2 top, 2 bottom, Application right) | manual (Playwright screenshot) | `AgentFlowDiagram.tsx` | PASS |
| AC-02 | [MUST] | 4 lines matching real pipeline order only | manual (Playwright — read the 4 `<line>` DOM elements' actual x1/y1/x2/y2) | `AgentFlowDiagram.tsx` | PASS |
| AC-03 | [MUST] | Border glow loops while working, stops when idle | manual (computed-style check: real `conic-gradient`, animating `--glow-angle`; visually confirmed after intensity fix) | `AgentCard.tsx`, `index.css` | PASS |
| AC-04 | [MUST] | Real `handoff.started`/`handoff.completed` triggers a line pulse in the right direction | manual (real `applyr cv generate` on a disposable offer → DOM-polled a `<circle>` appearing) — pulse's `anchors[from]`/`anchors[to]` provably reuse the same anchor lookup as the static line for that pair | `AgentFlowDiagram.tsx` | PASS |
| AC-05 | [MUST] | Unknown from/to pair is silently ignored | code inspection (`SEGMENTS.some(...)` guard before pushing a pulse) — not exercised live, the real pipeline never emits a non-adjacent pair | `AgentFlowDiagram.tsx` | PASS (untested live) |
| AC-06 | [MUST] | Lines reposition correctly on resize | manual (Playwright — `boundingBox()` before/after `set_viewport_size`, coordinates changed correctly) | `AgentFlowDiagram.tsx` | PASS |
| AC-07 | [MUST] | No agent ever shows literal "Idle"/"Working" | manual (Playwright body text across all 5 cards) | `badge-copy.ts`, `AgentCard.tsx` | PASS |
| AC-08 | [MUST] | `/agents` redirects to `/office`, no sidebar entry | manual (Playwright — navigated to `/agents`, landed on `/office`) | `App.tsx`, `Sidebar.tsx` | PASS |
| AC-09 | [MUST] | Intake form + pending list unchanged | manual (Playwright screenshot shows both, unchanged from before) | `OfficePage.tsx` | PASS |
| AC-10 | [SHOULD] | Bigger, animated bubble trigger | manual (visual — `size-6`/`p-2`/`animate-pulse`, screenshot) | `AgentCard.tsx` | PASS |
| AC-11 | [SHOULD] | Single SSE subscription for all 4 pulses | code inspection (`useHandoffEvents()` called once in `AgentFlowDiagram`, not per-card) | `AgentFlowDiagram.tsx` | PASS |

## Drift check
- No functions/endpoints exist outside the spec's scope.
- No deviations from the plan — the one open question (exact glow intensity) was a
  visual-tuning pass within the same AC, not a scope change.
- Confirmed side effect (documented, not a surprise): 23 previously-failing `vitest`
  tests are gone because `features/office-scene/` (their home) was deleted per the
  spec's own plan — not silently lost.

## Out of scope
- `[WONT]` Removing `pixi.js`/`gsap` from `package.json` — flagged as now-unused, not
  removed here (a follow-up cleanup once this ships and nothing else needs them).
- `[WONT]` Deleting the real-art sprite/desk image asset files themselves.
- `[WONT]` Porting `TerminalPanel`/`AgentInspector` to the new page.
- `[WONT]` Real numeric progress on the handoff pulse (`notify_handoff_walking` is
  unused server-side; wiring it up is a separate future decision).
- `[WONT]` A hover tooltip on connector lines (nice-to-have, `[COULD]` above).
