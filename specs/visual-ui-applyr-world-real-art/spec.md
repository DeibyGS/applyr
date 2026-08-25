## Spec: Applyr World — Real Art Integration

### Status: SPECIFIED — implementation starting 2026-08-25
### Version: 1.0

### Recovered context

- **ADR-012** (`docs/adr/012-applyr-world-pixijs-engine.md`): PixiJS is the rendering
  engine. It explicitly flagged that the existing `assets/agents/*.webp` illustrations
  are **static portraits used by the Agents tab**, not sprite sheets — isometric scene
  art is a separate content-production cost. This spec is that content's integration.
- **Phase 1** (`specs/visual-ui-applyr-world-phase1/`, IMPLEMENTED): 5 fixed zones
  (`recruiter`, `matching`, `cv`, `ats`, `application`) laid out along a single fixed
  isometric diagonal (`scene-layout.ts::ZONE_ORDER`), placeholder circle sprites with
  color/alpha tween on status change (`agent-sprite.ts`).
- **Phase 2** (`specs/visual-ui-applyr-world-phase2/`, ADR-013, IMPLEMENTED): per-offer
  sprites walk between zones (`pipeline-sprites.ts`) driven by real SSE events;
  `SpriteDirection` (up/down/left/right) exists as a capability though the single-row
  layout only ever produces one diagonal. Real sprite art was explicitly `[WONT]`ed
  there: *"art integration is a later fast-follow spec once the project owner delivers
  the files."* This is that spec.
- **Post-#95 status semantics** (`features/agents/types.ts`): every agent reports only
  `working | idle`, derived exclusively from real API data (`agent-status.ts`). There
  is no `not_connected` runtime state anymore.
- **Canvas transparency** (`pixi-lifecycle.ts`): `backgroundAlpha: 0`; the page-level
  `.office-bg` CSS class (`index.css`, `office-bg.webp` with `background-size: cover`)
  shows through behind the canvas.
- Corrected assumptions from the pre-spec round (all confirmed by the project owner,
  2026-08-25):
  1. The art does **not exist yet** — this spec carries the normative **Art Asset
     Brief** (below) the owner will follow to produce it; engineering ships first with
     placeholders-as-fallback so nothing blocks on art delivery.
  2. Scope includes **in-canvas scenography** (desks/zone furniture), not just
     character swaps.
  3. Idle/working expression = **ground ring under the sprite** (owner accepted the
     recommendation: zero extra frames, keeps art pristine, preserves Phase 1 color
     semantics).
  4. Offer-in-transit sprites keep their amber circles this iteration.
  5. Fallback on texture-load failure = the existing placeholder shape (accepted).

### What does it do?

The Office scene stops looking like a geometric prototype: AI agents become visible
characters standing at isometric desks inside a furnished room, while keeping
everything that makes Applyr World trustworthy — every pixel of state shown still
comes from real API data, never simulated. Art is optional at runtime: until the owner
delivers asset files (or if any single file fails to load), each entity gracefully
renders today's placeholder shape instead.

### Acceptance criteria

#### Frontend — texture infrastructure

- `[MUST]` The system shall load every scene texture (agent characters, scenery)
  through one dedicated module (`office-scene/textures.ts`), the only place in the
  office-scene feature that touches PixiJS `Assets` or imports art URLs.
- `[MUST]` WHEN any texture fails to load (missing file, network error, decode error)
  THE system shall resolve that entry to `null` and render that entity's Phase 2
  placeholder shape instead — a missing asset shall never crash, blank, or block the
  scene.
- `[MUST]` WHILE textures are still loading THE system shall render placeholder shapes
  immediately (scene init is never awaited on art) and swap each entity to its art
  when that texture arrives.
- `[MUST]` WHEN a texture arrives after initial render THE system shall update the
  affected sprite in place — never tear down/recreate other sprites, never re-run the
  pipeline seeding race guard (`OfficeScene.tsx` seedPipelineIfReady semantics stay
  intact).
- `[SHOULD]` The system shall log exactly one `console.warn` per failed asset path
  (diagnosable without spamming on every poll cycle).

#### Frontend — agent character sprites

- `[MUST]` GIVEN a successfully loaded character texture for a zone, the zone sprite
  shall render that art anchored bottom-center (feet) at the zone's `(x, y)` position,
  replacing the filled-circle placeholder.
- `[MUST]` The system shall render an isometric ground ring beneath every zone sprite
  (character or fallback): static gray (`0x9ca3af`) while `idle`, teal (`0x2dd4bf`)
  while `working` — reusing Phase 1's exact palette so status stays readable even
  without art.
- `[SHOULD]` WHEN an agent's state changes to `working` THE ring shall run a bounded
  pulse (alpha oscillation, gsap repeat) until the state changes back to `idle`;
  WHEN `idle` THEN the ring shall be static.
- `[MUST]` WHEN a zone's character texture is unavailable THEN that zone shall render
  the current Phase 2 circle behavior (size, colors, alpha tween) unchanged — the
  fallback is byte-for-byte today's visuals plus the ground ring.

#### Frontend — scenography (desks)

- `[MUST]` The system shall render one desk sprite per zone at that zone's position,
  stacked behind the agent character (depth-sort order: desk `zIndex` < agent
  `zIndex` at equal y).
- `[MUST]` Desks shall participate in the existing sortable-container depth-sort
  (`sortableChildren`, sort-by-y) so walking offers visibly pass behind or in front
  of furniture according to their interpolated position.
- `[MUST]` WHEN a desk texture is unavailable THEN that zone shall render a flat
  isometric ellipse pad (same footprint, subtle neutral fill) as its fallback — a
  missing desk never leaves a zone visually unanchored.
- `[COULD]` Additional decor props beyond the 5 desks MAY be supported by the same
  mechanism (texture list entry + position), gated on art delivery.

#### Frontend — movement depth-correctness

- `[MUST]` WHILE an offer tween is in flight THE offer sprite's `zIndex` shall track
  its current interpolated y every frame (not only at completion), so it layers
  correctly against desks it passes; on completion the final `zIndex` equals the
  target zone's y (preserving Phase 2's landing behavior).

#### Frontend — layout constraints

- `[MUST]` The zone layout (`ZONE_ORDER`, single isometric row, `getZonePositions()`
  math) shall not change in this spec.
- `[SHOULD]` IF the delivered art's proportions need more vertical room THEN the
  canvas size may grow via the existing width/height constants only (`OfficeScene.tsx`
  `SCENE_WIDTH`/`SCENE_HEIGHT`), bounded to a maximum of 760×320, with `OfficePage.tsx`
  markup otherwise untouched.

#### Out of scope (explicit)

- `[WONT]` Walk-cycle / multi-frame animations (movement stays a smooth glide tween).
- `[WONT]` Changing offer-in-transit sprites (amber circles stay).
- `[WONT]` Touching the Agents tab portraits (`assets/agents/*.webp`,
  `agent-config.ts`) — different consumers, different files.
- `[WONT]` New zones, non-linear layouts, or player input.
- `[WONT]` Any backend/API change.

### Art Asset Brief (normative for delivered files)

> This section is the contract the project owner follows to produce the art. Files
> matching it are drop-in: no code change is needed to go from fallback to art.

**Where files go**

| Asset | Path (exact) | Count |
|-------|--------------|-------|
| Character per agent | `applyr/ui/frontend/src/assets/office-scene/agents/<agentId>.webp` where `<agentId>` ∈ `recruiter, matching, cv, ats, application` | 5 |
| Desk per zone | `applyr/ui/frontend/src/assets/office-scene/scenery/desk-<agentId>.webp` (same 5 ids) | 5 |

**Format rules (all files)**

- WebP (preferred) or PNG; **transparent background required**.
- One consistent style across all 10 files — pick ONE: pixel art or clean isometric
  vector. Do not mix.
- Palette should harmonize with `assets/office/office-bg.webp` (warm indoor tones);
  give each agent one distinct accent hue so zones read apart at a glance.
- Keep individual files under ~150 KB.

**Character sprites (agents/*.webp)**

- Single standing pose, facing **down-right** (toward the viewer's right, isometric
  SE — the direction offers walk).
- Export canvas: **128×128 px** (2× headroom for crisp rendering). Character feet at
  bottom-center ≈ (64, 122). Visual height 90–110 px within the canvas.
- Suggested role identity: recruiter = phone/headset + papers; matching = magnifier /
  chart; cv = document + pen; ats = shield/checklist; application = envelope/stamp.

**Desks (scenery/desk-*.webp)**

- Isometric desk seen slightly from above, empty top surface readable at small size.
- Export canvas: **256×160 px**; desk occupies center ~220×120. Display size in-scene
  will be ~120×75 px, so test legibility scaled down.
- Distinct prop silhouette per role (as above) but same desk geometry/color family.

**Explicitly NOT required now**: multi-frame sheets, walk cycles, per-direction
variants, background/room art (CSS `office-bg.webp` already covers the room).

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `specs/visual-ui-applyr-world-real-art/spec.md` | CREATE | This spec |
| `applyr/ui/frontend/src/features/office-scene/textures.ts` | CREATE | Single texture-loading module w/ null-fallback |
| `applyr/ui/frontend/src/features/office-scene/textures.test.ts` | CREATE | Loader failure/pending/arrival tests |
| `applyr/ui/frontend/src/features/office-scene/agent-sprite.ts` | MODIFY | Art swap + ground ring + pulse; keep fallback circle |
| `applyr/ui/frontend/src/features/office-scene/agent-sprite.test.ts` | MODIFY | Ring + fallback coverage |
| `applyr/ui/frontend/src/features/office-scene/scene-scenery.ts` | CREATE | Desk layer w/ ellipse-pad fallback |
| `applyr/ui/frontend/src/features/office-scene/scene-scenery.test.ts` | CREATE | Placement + z-order + fallback tests |
| `applyr/ui/frontend/src/features/office-scene/pipeline-sprites.ts` | MODIFY | Per-frame zIndex tracking during tween |
| `applyr/ui/frontend/src/features/office-scene/pipeline-sprites.test.ts` | MODIFY | Mid-flight z-index assertions |
| `applyr/ui/frontend/src/features/office-scene/OfficeScene.tsx` | MODIFY | Wire textures + scenery into composition |

### Dependencies

- Reused: `pixi.js` `Assets`/`Sprite` (already a dependency — no new npm packages),
  `gsap` tweens, `scene-layout.ts` positions, existing sortable-stage pattern.
- Build tooling: Vite already resolves `.webp` imports as URLs (proven by
  `office-bg.webp` in CSS and tab portraits in TSX).
- APIs/DB: none touched.

### Explicit assumptions

- We assume the brief's paths/canvas sizes are stable before art production starts;
  if the owner needs different dimensions, the fix is editing this brief **before**
  producing files, then a one-line constant change in `textures.ts`.
- We assume `working|idle` are the only runtime states (post-#95 reality); if a third
  state ever returns, the ring gains a color case in one function.
- We assume glide-without-walk-cycle remains acceptable (confirmed in pre-spec round).

### Non-functional requirements

- Performance: texture loading is async and never blocks scene init; art adds payload
  weight only via the owner's own files (brief caps ~150 KB each).
- Trustworthiness: no behavioral coupling between art presence and state derivation —
  `agent-status.ts` untouched; the scene keeps "never simulate state" (visual-ui
  governing rule).

### Edge cases / risks

- **Art never arrives** → the scene ships and runs indefinitely on placeholders +
  rings; nothing rots because the integration path is exercised from day one.
- **Partial delivery** (e.g., 3 of 5 characters done) → mixed scene: art where
  provided, circles elsewhere; acceptable by design, per-entity fallback.
- **Texture arrives mid-poll while a tween runs** → swap updates texture/material in
  place; position/tween objects untouched (AC under texture infrastructure).
- **Desk overlapping resting offers** → offers rest at `zone.y + REST_OFFSET_Y`
  (below the desk's anchor), desks sort behind at equal y; verified by a unit test
  pinning the relative z-order triple (desk < offer-at-rest < next-front-desk).
- **Owner iterates on art files later** → same-path overwrite + browser cache refresh
  is enough; no code involvement.

### Task breakdown

1. [ ] This spec + art brief committed and PR'd against `feat/cc-visual-ui` [S]
2. [ ] `textures.ts`: typed registry, async load-all, null-on-failure, warn-once; tests [M]
3. [ ] `agent-sprite.ts`: character swap + ground ring (+pulse SHOULD); fallback parity; tests [M]
4. [ ] `OfficeScene.tsx`: wire loader + scenery into composition without disturbing
       seeding race guards [S]
5. [ ] `scene-scenery.ts`: desk placement, pad fallback, z-order vs agents/offers; tests [M]
6. [ ] `pipeline-sprites.ts`: per-frame zIndex during tween; tests [S]
7. [ ] `/adversarial-test` pass + traceability matrix filled here [M]

Task sizes: S (<1h) | M (1-3h) | L (3-6h)

### Traceability matrix

_Filled in during implementation (task 7)._

| AC | Priority | Description | Test | Implementation | Status |
|----|----------|-------------|------|----------------|--------|
| — | — | pending implementation | — | — | — |
