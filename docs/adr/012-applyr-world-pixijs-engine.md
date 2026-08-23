# ADR 012 — PixiJS as the rendering engine for "Applyr World" (Office page)

**Status:** Accepted
**Narrows:** `docs/visual-ui/AGENTS.md`'s Stack table, "Animation: Framer Motion,
2D/CSS only — no Three.js / 3D" row — narrowed specifically for the Office page's
future animated pipeline scene ("Applyr World"). Every other page in the Visual UI
(Analytics, Offers, Settings, Interviews, Archive, Agents) keeps Framer Motion/CSS as
its only animation layer, unchanged. The "no Three.js / 3D" half of that row is not
reopened — full 3D remains rejected (see Alternatives below).
**Date:** 2026-08-23

## Context

`docs/visual-ui/AGENTS.md` records a pivot the project owner proposed mid-session on
2026-08-23: instead of Office's simple ambient background, an isometric/2.5D animated
pipeline where agents (Scout/Analyst/Decision/CV/ATS/Writer) physically walk offers
through the pipeline stages, driven by real state changes. That proposal was classified
architectural (new render engine, new visual language, high cost of reversal) and
deferred to a dedicated RADAR + this ADR before any implementation — this is that
session.

Three already-locked decisions bound the RADAR:
- No WebSocket in v1 — real-time-feeling updates must still come from polling
  (2-3s), the same mechanism every other page already uses.
- No scale-oriented infra — single local user, one process, no new backend
  services.
- The animation must reflect real database state — never simulate or fake agent
  progress, the same principle that already governs the rest of the dashboard.

Pre-RADAR clarifying questions with the project owner established the actual
requirements this decision optimizes for: the primary motivator is visual delight
("que se vea lindo, que se sienta como un mundo propio"), with pipeline visibility as
a secondary benefit rather than the driving need — Office's existing card-based view
already covers the functional visibility case. The owner is willing to invest in one
large, dedicated build rather than many small increments, and set two additional hard
constraints beyond the three above: the scene must never fake state (extends the
existing "no simulated progress" principle explicitly to this feature), and it must
integrate into the existing Office page/sidebar navigation rather than replace or
silo it.

Full RADAR trade-off table (CSS/Framer Motion pushed further vs. PixiJS vs. Phaser)
lives in this session's chat log; the summary that drove the decision follows.

## Decision

Adopt **PixiJS** as the rendering engine for Office's future "Applyr World" scene: a
single WebGL-accelerated 2D canvas mounted inside the existing `OfficePage.tsx`,
rendering sprites for offers/agents with hand-written isometric depth-sorting
(sort-by-Y), driven entirely by React state populated from the existing
`useIntakeAndJobs`-style polling hooks — no WebSocket, no new backend endpoint
required to *render* the scene (state changes already reach the frontend through the
existing `GET /api/jobs`/`GET /api/intake` polling).

Rejected in favor of PixiJS: staying on Framer Motion/CSS (insufficient for real
isometric depth-sorting and WebGL-grade sprite animation — it's the status quo that
prompted this proposal in the first place, not a genuine alternative to it), and
Phaser (a full game framework — physics, input handling, multi-scene management —
none of which this single-scene, no-player-input visualization needs; its own game
loop also sits awkwardly next to React's render cycle for a solo maintainer coming
back to this code later).

This ADR decides the **engine only**. It does not approve a specific MVP scope, scene
design, asset list, or timeline — see Notes.

## Consequences

### Positive

- Gets the visual ceiling the proposal actually needs (true WebGL sprite animation,
  particles, smooth motion) without importing a full game engine's conceptual surface
  the feature will never exercise.
- PixiJS is a lean, well-documented, single-purpose rendering library (~250KB) —
  smaller footprint and narrower API surface than Phaser for a maintainer returning to
  this code months later.
- Isometric depth-sorting (the one piece a game framework would give "for free") is a
  bounded, well-known problem (sort sprites by Y) — writing it by hand is a contained
  cost, not an open-ended unknown.
- Stays fully compatible with the three pre-existing locked constraints: driven by
  polling (no WebSocket), no new backend infra, and state-only rendering (no fake
  progress) — this ADR does not reopen any of those.

### Negative

- Introduces the Visual UI's first canvas-based rendering dependency, alongside
  Recharts (Slice 5) as the second non-DOM rendering technology in the frontend.
  Contributors auditing "what renders this page" now need to know DOM/Tailwind for
  most pages, Recharts for Analytics, and PixiJS specifically for Office — this ADR is
  the record of why that split exists, not precedent for adding a fourth without its
  own decision.
- React ↔ Pixi bridging (canvas lifecycle vs. React's render cycle) is a known source
  of subtle bugs — stale closures inside the Pixi ticker, sprite/texture leaks if not
  destroyed on unmount. The eventual implementation spec must isolate this in one
  well-tested bridge component, not ad-hoc wiring per scene.
- Real asset cost: the 5 existing agent illustrations (Slice 2, `assets/agents/*.webp`)
  are static portraits, not sprite sheets — an isometric walk-cycle needs new art per
  agent per facing direction. This is a content-production cost separate from and
  additional to the engineering cost, easy to under-count in a "one big session"
  framing.
- Polling-driven animation (2-3s ticks, no WebSocket) risks looking like sprites
  "teleport" between updates unless the implementation explicitly interpolates
  between the last-known and newly-polled position rather than snapping to it — an
  open design question this ADR flags but does not resolve (see Notes).

### Neutral

- PixiJS is scoped strictly to `OfficePage.tsx`'s future scene. It is not adopted as a
  general-purpose animation layer for the rest of the Visual UI — Framer Motion/CSS
  remains the default everywhere else, unchanged from the original Stack table
  decision.

## Alternatives considered

**Push Framer Motion/CSS further instead of adopting a new renderer.** Rejected —
this is the status quo the "Applyr World" proposal was explicitly reacting against.
Real isometric depth-sorting and WebGL-grade sprite/particle animation are outside
what CSS transforms and DOM layout can deliver well at this visual ambition; the RADAR
found no realistic path to the "juicy," game-like feel the owner asked for without a
canvas-based renderer.

**Phaser** (full game framework, built on PixiJS internally). Rejected for this
feature. Its isometric-tilemap plugin would remove some hand-written math PixiJS
requires, but that saving is outweighed by importing an entire game framework's
surface — physics engine, input system, multi-scene lifecycle — none of which a
single-scene, no-player-input "watch offers walk through stages" visualization uses.
Phaser's own game loop also integrates less cleanly with React's render cycle than a
narrower PixiJS-only bridge does. Revisit only if a concrete future need for physics,
player input, or multiple distinct game-like scenes actually appears — not as a
default upgrade path from PixiJS.

**Three.js / full 3D.** Already rejected in `docs/visual-ui/AGENTS.md`'s "Explicitly
rejected" list before this RADAR ran; not reopened here. Noted for completeness of the
trade-off record, not evaluated as a live option — the "2.5D isometric" visual
language the owner asked for does not need a 3D scene graph, and 3D would reintroduce
exactly the scale-oriented complexity the project has consistently rejected for a
single local user.

## Notes

- **This ADR is an engine decision, not an implementation authorization.** Before any
  "Applyr World" code is written, it needs its own `/sdd` spec with an explicit,
  hard-bounded MVP cut (e.g., a fixed small number of lanes/zones, not a free-roaming
  world) — the RADAR flagged unbounded scope as the single biggest risk of the "one
  big investment session, delight-focused" framing that motivates this feature.
- That future spec must also resolve, as first-class design decisions rather than
  implicit assumptions: (1) how polling-tick updates get interpolated into smooth
  motion instead of teleporting sprites, (2) the actual asset-production plan for
  isometric walk-cycle sprites (new art, not a reuse of the existing static
  portraits), and (3) the React/Pixi lifecycle-bridge component's test coverage
  before it's reused across multiple sprite types.
- Given the project's `/adversarial-test` gate ("data integrity or DB migration, state
  machine, ... architecturally significant decision"), the state-machine-like nature of
  agents transitioning between pipeline stages should be evaluated for that gate when
  the implementation spec is written, even though this ADR itself makes no DB or
  data-integrity change.
