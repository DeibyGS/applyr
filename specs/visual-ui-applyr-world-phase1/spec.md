## Spec: Applyr World — Phase 1 (PixiJS engine + isometric agent scene, placeholder sprites)

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context

- **Project constitution (`docs/visual-ui/AGENTS.md`)**: non-negotiable invariants —
  engine (`db.py`/`scoring.py`/`cv.py`) never touched by this feature; dashboard never
  fakes/simulates agent progress, state always comes from real polled data; no
  WebSocket in v1 (`POLL_INTERVAL_MS = 3000` in `useIntakeAndJobs.ts`); no
  infrastructure beyond the single existing process. Frontend structure is locked:
  feature folders under `features/<domain>/`, `api/` is the only fetch boundary,
  pure logic lives separate from components, tests colocated.
- **`docs/adr/012-applyr-world-pixijs-engine.md` (Accepted)**: decides the rendering
  engine only — PixiJS, single WebGL canvas mounted in `OfficePage.tsx`, hand-written
  isometric depth-sort (sort-by-Y), driven by existing polling hooks, no new backend
  endpoint to render. Explicitly does **not** authorize implementation scope — requires
  this dedicated spec with a hard-bounded MVP, plus first-class answers for: polling-tick
  interpolation (no teleporting sprites), sprite-asset production plan, and a
  well-tested React/Pixi lifecycle bridge component before it's reused across sprite
  types. Flags a state-machine-like agent transition behavior that should be evaluated
  for the `/adversarial-test` gate.
- **Engram / session history**: full RADAR + requirements-gathering that produced
  ADR-012 is recorded inline in `docs/visual-ui/AGENTS.md`'s "Applyr World" status
  entries (2026-08-23) — visual delight is the primary driver, pipeline visibility is
  secondary (already covered by the existing `/agents` page), one large dedicated build
  preferred over incremental slices, must never fake state, must integrate into Office
  rather than replace/silo it.
- **Corrected assumptions from Step 2** (confirmed by user 2026-08-24):
  1. The scene renders **5 zones**, one per real `AgentId` (`recruiter`, `matching`,
     `cv`, `ats`, `application` — from `features/agents/agent-config.ts`), not 6 —
     the ADR's narrative used 6 conceptual names (Scout/Analyst/Decision/CV/ATS/Writer)
     that don't map 1:1 onto the actual implemented agent taxonomy.
  2. Granularity is **per-agent, aggregate**, not per-offer. `deriveAgentStatuses`
     returns one `AgentStatus` per agent (e.g. "matching: working, company X"), not a
     list of individual offers in transit. The MVP animates one token per zone
     reflecting that zone's current aggregate `AgentStatus` — it does not render N
     separate sprites for N pending offers.
  3. Tweening library: **GSAP** (core, tree-shaken import — no plugins).
  4. Bridge component tests **mock `pixi.js`** (Application/Ticker/Container/Graphics)
     — a real WebGL canvas does not render under jsdom/Vitest, so unit tests assert
     lifecycle behavior (create on mount, destroy on unmount, ticker start/stop), not
     pixel output.
  5. **No accessible text fallback inside the canvas** for this phase — the scene is
     decorative/supplementary; the same real agent state remains available as text on
     `/agents` (already shipped, unchanged by this spec).
  6. Zero new backend endpoints — reuses `useIntakeAndJobs` exactly as `AgentRow` does
     today.
  7. New npm dependencies (`pixi.js`, `gsap`) are frontend-only
     (`applyr/ui/frontend/package.json`) — zero impact on the Python `applyr[ui]`
     extra, same precedent as Recharts (Slice 5).

### What does it do? (observable behavior, not implementation)

Replaces `AgentRow` (static illustrated cards) in `OfficePage.tsx` with a single
isometric WebGL canvas showing 5 fixed zones, one per agent (`recruiter`, `matching`,
`cv`, `ats`, `application`). Each zone shows a placeholder geometric sprite (colored
isometric shape, no character art — real art is a future phase, out of scope here).

- The `recruiter` and `matching` zones have real driving state today (via
  `deriveAgentStatuses`): their sprite visibly reacts (e.g. a state change — idle vs.
  working — plus a smooth, tweened transition, never an instant snap) whenever a poll
  (every 3s) reports a changed `AgentStatus`.
- The `cv`, `ats`, `application` zones have no persisted backend state yet (existing,
  unchanged limitation) — their sprite renders in a fixed "not connected" visual state,
  never animated to look active, matching the same honesty principle `AgentCard`
  already applies elsewhere.
- Movement between two known states is **interpolated** (GSAP tween) over a duration
  bounded by the poll interval, so sprites never appear to teleport.
- `IntakeForm`/`PendingIntakeList` below the scene are unchanged.

### Acceptance criteria

#### Engine & bridge

- `[MUST]` The system shall render exactly one PixiJS `Application` instance when
  `OfficePage` mounts, and destroy it (including its canvas, textures, and ticker) when
  `OfficePage` unmounts — no leaked WebGL context on repeated navigation away/back to
  `/office`.
- `[MUST]` WHEN the bridge component mounts THE system SHALL start the Pixi ticker;
  WHEN it unmounts THE system SHALL stop the ticker before destroying the application.
- `[MUST]` The system shall isolate all Pixi lifecycle logic (create/mount/destroy) in
  one reusable bridge component (`features/office-scene/PixiStage.tsx` or equivalent) —
  no ad-hoc `new PIXI.Application()` calls anywhere else in the codebase.
- `[SHOULD]` The bridge component shall accept children/render-prop access to the Pixi
  `Application` so future sprite types (Phase 2 art swap) can mount without changing the
  bridge itself.

#### Scene content

- `[MUST]` The system shall render exactly 5 fixed zones, one per `AgentId` in
  `agent-config.ts` (`recruiter`, `matching`, `cv`, `ats`, `application`), positioned
  with isometric (2.5D) depth — no free-roaming/dynamic zone count.
- `[MUST]` Given the `recruiter` or `matching` zone, When the polled `AgentStatus` for
  that agent changes state (e.g. `idle` → `working`), Then the zone's sprite
  transitions to a visually distinct representation of the new state within one tween
  duration — never an instant, unanimated snap.
- `[MUST]` Given the `cv`, `ats`, or `application` zone, When the scene renders, Then
  the zone's sprite always shows the same fixed "not connected" visual (no animation,
  no state changes) — the system shall never fabricate activity for an agent with no
  real backing state.
- `[MUST]` The system shall never render agent state that does not come from
  `useIntakeAndJobs`'s polled data — no timers, randomness, or fixtures driving visible
  state.

#### Interpolation

- `[MUST]` WHEN a poll (every `POLL_INTERVAL_MS` = 3000ms) reports a changed
  `AgentStatus` for `recruiter` or `matching` THE system SHALL animate the transition
  using a GSAP tween with a fixed duration strictly less than `POLL_INTERVAL_MS`, so one
  transition always completes before the next poll can start another.
- `[SHOULD]` IF a new poll result arrives while a previous tween is still running THEN
  the system SHALL interrupt/kill the in-flight tween and start the new one from the
  sprite's current (mid-tween) position — never queue tweens or let two run
  concurrently on the same sprite.

#### Integration

- `[MUST]` Given `/office`, When the page renders, Then the canvas occupies the layout
  slot `AgentRow` previously occupied; `IntakeForm` and `PendingIntakeList` render
  below it, unchanged from current behavior.
- `[MUST]` The system shall remove `AgentRow` usage from `OfficePage.tsx`. **Correction
  during `/code-review` (2026-08-24):** the original assumption that `AgentRow` "stays
  in the codebase — still used by `/agents`" was wrong — `AgentsPage.tsx` renders
  `AgentCard` directly (`variant="detailed"`), never `AgentRow`. Once `OfficePage.tsx`
  stopped using it, `AgentRow.tsx` had zero remaining callers (grep-verified across
  `src/`). Deleted rather than left as dead code.
- `[WONT]` This phase does not add or modify any backend endpoint, table, or column.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/ui/frontend/src/features/office-scene/pixi-lifecycle.ts` | CREATE | Pure lifecycle logic (create Application, start, stop, destroy) — no React, testable without a DOM environment |
| `applyr/ui/frontend/src/features/office-scene/pixi-lifecycle.test.ts` | CREATE | Unit tests mocking `pixi.js`: mount creates Application+starts ticker, unmount stops ticker+destroys app, no leak on repeated mount/unmount |
| `applyr/ui/frontend/src/features/office-scene/PixiStage.tsx` | CREATE | Thin React wrapper — `useRef`/`useEffect` calling `pixi-lifecycle.ts`, no lifecycle logic of its own, not directly unit-tested (same pattern as `pages/*.tsx`) |
| `applyr/ui/frontend/src/features/office-scene/scene-layout.ts` | CREATE | Pure function: 5 fixed zone positions (isometric coords) for the 5 `AgentId`s — no React/Pixi/DOM |
| `applyr/ui/frontend/src/features/office-scene/scene-layout.test.ts` | CREATE | Unit tests for zone position calculation |
| `applyr/ui/frontend/src/features/office-scene/agent-sprite.ts` | CREATE | Factory for one zone's placeholder Pixi `Graphics` sprite; owns its own GSAP tween on state change; static "not connected" visual for `cv`/`ats`/`application` — plain PixiJS (no `@pixi/react`), so this is a factory function, not a `.tsx` component |
| `applyr/ui/frontend/src/features/office-scene/agent-sprite.test.ts` | CREATE | Unit tests (mocked `pixi.js`+`gsap`): tween starts on state change, skipped when state unchanged, in-flight tween killed and restarted on new poll result |
| `applyr/ui/frontend/src/features/office-scene/OfficeScene.tsx` | CREATE | Composes `PixiStage` + 5×`AgentSprite`, consumes `deriveAgentStatuses` output — thin, no logic of its own |
| `applyr/ui/frontend/src/pages/OfficePage.tsx` | MODIFY | Replace `<AgentRow statuses={agentStatuses} />` with `<OfficeScene statuses={agentStatuses} />` |
| `applyr/ui/frontend/src/features/agents/AgentRow.tsx` | DELETE | Dead code after the swap above — `/code-review` caught that `AgentsPage.tsx` never used it (renders `AgentCard` directly), so it had zero remaining callers |
| `applyr/ui/frontend/package.json` | MODIFY | Add `pixi.js`, `gsap` to `dependencies` |

### Dependencies

- APIs/endpoints used: none new — `GET /api/intake` + `GET /api/jobs` via existing
  `useIntakeAndJobs` (unchanged).
- DB tables: none touched.
- Reused components/logic: `deriveAgentStatuses` (`features/agents/agent-status.ts`,
  unchanged), `AGENT_CONFIG` (`features/agents/agent-config.ts`, unchanged) for
  agent identity/labels only (not illustrations — those are Phase 2).
- New npm packages: `pixi.js` (WebGL rendering), `gsap` (tweening) — frontend only.

### Explicit assumptions

- We assume 5 zones (not 6) is correct per the real `AgentId` union → if the user
  actually wants a 6th conceptual zone with no backing `AgentId`, that requires a
  backend/type change first, out of scope here.
- We assume "not connected" zones render fully static (zero animation) → if a subtle
  idle animation (e.g. gentle sprite bob) is wanted even for disconnected agents to
  avoid the scene looking broken, that is a `[COULD]`-tier follow-up, not blocking.
- We assume GSAP's core bundle (no premium plugins) is sufficient for a linear/eased
  position tween → confirmed sufficient for this scope, no paid GSAP plugins needed.

### Non-functional requirements

- Performance: tween duration fixed below 3000ms (poll interval) so transitions never
  overlap on the same sprite; canvas must not visibly drop frames on the reference dev
  machine at 5 sprites (trivial sprite count for PixiJS — no perf budget beyond "no
  dropped frames" is meaningful at this scale).
- Security: no new attack surface — no new endpoints, no user input rendered into the
  canvas.
- Memory safety: zero leaked PixiJS `Application`/`Texture`/`Ticker` instances across
  repeated mount/unmount of `/office` (this is the ADR's explicitly flagged risk;
  covered by `PixiStage.test.tsx`).
- Accessibility: out of scope for this phase per confirmed assumption #5 — real agent
  state remains available as accessible text on `/agents`, unchanged.

### Edge cases / risks

- **Poll arrives mid-tween** → mitigated by AC "interrupt/kill in-flight tween, restart
  from current position" (GSAP `tween.kill()` + re-tween from current x/y, not from the
  stale target).
- **Component unmounts mid-tween** (user navigates away from `/office` while a tween is
  running) → `PixiStage` unmount must kill all active GSAP tweens targeting its sprites
  before destroying the Pixi `Application`, or GSAP will hold a reference to destroyed
  Pixi objects. Covered by `PixiStage.test.tsx`.
- **jsdom/Vitest cannot render real WebGL** → tests mock `pixi.js` at the module
  boundary; this verifies lifecycle correctness, not visual output. Visual verification
  is manual (dev server + browser), same disclosed limitation as Slices 5-7.
- **Discovered during implementation**: the project has no jsdom/`@testing-library/react`
  configured (`vitest.config.ts` uses `environment: "node"`; every existing test is
  pure-logic, none render a component). Rather than add that test infra for one
  component, lifecycle logic was extracted into `pixi-lifecycle.ts` (plain functions,
  no React) so it stays testable under the existing node environment — consistent with
  `AGENTS.md`'s rule #4 (pure logic separate from its component). `PixiStage.tsx`
  itself is a thin, untested wrapper, same as every `pages/*.tsx` file.
- **`/adversarial-test` gate**: the ADR flags the agent state-transition behavior as
  "state-machine-like." Evaluated here — this phase's states are a simple 2-value
  enum per agent (`idle`/`working` for recruiter/matching, fixed `not_connected` for
  the rest) with no persistence, no transitions written back to the DB, and no
  idempotency concern (it's a pure read-and-render derivation, already covered by
  existing `agent-status.test.ts`). Classified **not** a state machine in the sense the
  project's gate targets (that gate is aimed at persisted/DB-backed state machines) —
  `/adversarial-test` is skipped for this phase. Revisit if a future phase persists
  offer-level pipeline-stage state.

### Task breakdown (execution order)

1. Add `pixi.js` + `gsap` to `package.json`, verify `tsc --noEmit` + build still pass
   with no other changes [S]
2. `scene-layout.ts` — pure isometric zone-position function for the 5 `AgentId`s, unit
   tested [S]
3. `pixi-lifecycle.ts` — pure mount/unmount/ticker lifecycle logic, mocked-`pixi.js`
   unit tests for create/destroy/no-leak; `PixiStage.tsx` thin wrapper calling it [M]
4. `agent-sprite.ts` — placeholder geometric sprite factory per zone, GSAP tween on
   state change (skipped when unchanged), fixed "not connected" visual for
   cv/ats/application, kill-and-restart logic for mid-tween polls, unit tested [M]
5. `OfficeScene.tsx` — composes `PixiStage` + 5×`AgentSprite`, wired to
   `deriveAgentStatuses` [S]
6. `OfficePage.tsx` — swap `AgentRow` for `OfficeScene` [S]
7. Manual verification: dev server, visually confirm the 5 zones render, trigger a
   real state change (submit intake / add an offer) and confirm the tween plays without
   teleporting, confirm repeated `/office` navigation shows no console warnings/leaks [S]

## Traceability Matrix

| AC | Priority | Description | Test / Verification | Implementation | Status |
|----|----------|--------------|---------------------|-----------------|--------|
| AC-01 | MUST | One Pixi Application per mount, destroyed on unmount, no leak | `pixi-lifecycle.test.ts` "repeated mount/destroy cycles create and tear down one Application each time" | `pixi-lifecycle.ts` | PASS |
| AC-02 | MUST | Ticker starts on mount, stops before destroy on unmount | `pixi-lifecycle.test.ts` "destroy() stops the ticker before destroying the application" | `pixi-lifecycle.ts` | PASS |
| AC-03 | MUST | All Pixi lifecycle logic isolated in one reusable bridge | `pixi-lifecycle.ts` is the sole `new Application()` call site (grep-verified); `PixiStage.tsx` only calls it | `pixi-lifecycle.ts`, `PixiStage.tsx` | PASS |
| AC-04 | SHOULD | Bridge exposes stage to future sprite types without changing itself | `onReady(stage)` callback contract, consumed generically by `OfficeScene.tsx` | `PixiStage.tsx` | PASS |
| AC-05 | MUST | Exactly 5 fixed zones, one per real `AgentId` | `scene-layout.test.ts` "returns exactly 5 zones, one per real AgentId" | `scene-layout.ts` | PASS |
| AC-06 | MUST | recruiter/matching zone tweens on real state change | `agent-sprite.test.ts` "tweens alpha from a dimmed value back to 1 when state actually changes" | `agent-sprite.ts` | PASS |
| AC-07 | MUST | cv/ats/application always static, never fabricated activity | `agent-sprite.test.ts` "never tweens a not_connected zone, regardless of repeated updates" | `agent-sprite.ts` | PASS |
| AC-08 | MUST | Scene state always sourced from polled data, never simulated | Code inspection: `OfficeScene` takes `statuses` prop straight from `deriveAgentStatuses`/`useIntakeAndJobs`, no local timers/fixtures; existing `agent-status.test.ts` unchanged | `OfficeScene.tsx`, `OfficePage.tsx` | PASS |
| AC-09 | MUST | Tween duration strictly below `POLL_INTERVAL_MS` (3000ms) | `TWEEN_DURATION_S = 1.2` (1200ms) constant, code-inspected against `useIntakeAndJobs.ts`'s `POLL_INTERVAL_MS = 3000` | `agent-sprite.ts` | PASS |
| AC-10 | SHOULD | In-flight tween killed and restarted, never queued | `agent-sprite.test.ts` "kills the in-flight tween and starts a new one if state changes again before it finishes" | `agent-sprite.ts` | PASS |
| AC-11 | MUST | Canvas occupies `AgentRow`'s old layout slot; `IntakeForm`/`PendingIntakeList` unchanged | Manual browser verification by user, 2026-08-24 (5 zones rendered, form/list intact below) | `OfficePage.tsx` | PASS |
| AC-12 | MUST | `AgentRow` usage removed from `OfficePage.tsx` | Grep-verified zero remaining callers after the swap; `AgentRow.tsx` deleted (corrected during `/code-review` — the original "still used by /agents" assumption was wrong) | `OfficePage.tsx`, `AgentRow.tsx` (deleted) | PASS |
| AC-13 | WONT | Zero backend changes | `git status --short` on the worktree: no `.py` files touched | — | PASS |

All MUST/SHOULD ACs have a test or an explicit, checked verification. AC-11 is manual
(disclosed limitation — no browser-driving tool this session, same as Slices 5-7) but
was independently confirmed live by the user, including a real `idle→working` state
transition triggered by processing 2 real pending offers through the actual Matcher
pipeline (Menhir AI → offer #248, 72% APPLY; Diverger → offer #249, 61% MAYBE).

**Drift check**: two implementation-time deviations from the original file list, both
already recorded above under "Discovered during implementation" — `PixiStage.tsx`
split into `pixi-lifecycle.ts`+thin wrapper (no jsdom/RTL in the project), and
`AgentSprite.tsx` renamed to `agent-sprite.ts` (plain PixiJS, no `@pixi/react`, so no
JSX). Both are naming/structure corrections that preserve every AC — no scope drift.
One unplanned addition: `preference: "webgl"` on `app.init()` in `pixi-lifecycle.ts`,
added after manual verification surfaced a benign-but-noisy `Failed to create WebGPU
Context Provider` console warning on every mount — skips the WebGPU probe entirely
since this scene has no WebGPU-specific need. No new file, no AC change, `tsc` verified
the option is valid against the installed `pixi.js` v8 types.

`/adversarial-test` gate: skipped, per the reasoning already recorded above under
"Edge cases / risks" (derived-only enum state, no DB persistence, not the kind of
state machine the gate targets).

### Out of scope

- `[WONT]` Real isometric sprite art (walk-cycle sheets per agent/direction) — Phase 2,
  separate spec, swaps `AgentSprite`'s placeholder rendering only.
- `[WONT]` Any backend change (new endpoint, table, or column) — including persisting
  per-offer pipeline-stage state for `cv`/`ats`/`application`.
- `[WONT]` Accessible text/aria fallback inside the canvas.
- `[WONT]` Multiple simultaneous per-offer sprites ("N offers walking at once") —
  requires backend data this phase does not add.
- `[WONT]` WebSocket or any non-polling real-time mechanism.
