# ADR 013 — Cross-zone offer movement and SSE push transport for "Applyr World"

**Status:** Accepted
**Supersedes (partially):** ADR-012's locked constraint "No WebSocket in v1 — real-time-feeling
updates must still come from polling (2-3s), the same mechanism every other page already
uses." Every other locked constraint from that ADR's RADAR session stays in force: no
scale-oriented infra beyond what this decision itself requires (single local user, one
process), and the scene must always reflect real state — never simulate or fake agent
progress.
**Date:** 2026-08-24

## Context

ADR-012 picked PixiJS as the rendering engine for "Applyr World" but explicitly deferred
scene design, movement, and asset planning to a future implementation spec. Its own Notes
section flagged, as open questions for that spec: (1) how polling-tick updates get
interpolated into smooth motion instead of teleporting sprites, and (2) the real
asset-production plan for isometric walk-cycle sprites.

Phase 1 (`specs/visual-ui-applyr-world-phase1/spec.md`) shipped the smallest slice that
could stand on its own: 5 fixed, zone-bound sprites whose color/alpha tweens on real
`AgentStatus` polling changes. It explicitly scoped out, as "Phase 2, separate spec":
real sprite art, and any backend change to persist per-offer pipeline-stage state.

This session's pre-spec questions (see chat log, 2026-08-24) asked the project owner to
resolve Phase 2's actual shape before writing that spec, since "Phase 2" as named in the
Phase 1 spec undersells what the owner now wants:

1. **Art origin** — owner generates/sources the art and hands it to the agent; the spec
   only needs to cover integration, not generation.
2. **Movement scope** — not a static art swap, and not an in-place idle animation either:
   agents must **physically walk offers between zones** (Recruiter → Matching → CV → ATS →
   Application), the original "Applyr World" pitch, not the narrower Phase 1 "Phase 2".
3. **Event source** — the CLI itself must emit stage-transition events (`add`,
   `cv generate`, `cv review`, `cv pdf`, `update applied` each mark a real transition),
   not something the UI infers from existing columns alone — several stages
   (CV/ATS/Application) have no backing column to infer from today.
4. **Concurrency** — multiple offers must be able to animate in transit at once, not one
   at a time.
5. **Staleness behavior** — on open/reconnect, the scene jumps straight to each offer's
   real current stage; it never replays a retroactive animation for transitions that
   happened while the UI was closed.

Decision (4), multiple offers animating concurrently, is what reopens ADR-012's "no
WebSocket, polling only" constraint: at 2-3s polling granularity, several offers advancing
through different stages in the same window collapse into indistinguishable "teleports" —
exactly the risk ADR-012's own Consequences section flagged as unresolved. A push
transport is the direct fix; polling is not, regardless of interval, because the CLI-side
events (5 short-lived Python process invocations) don't reliably land inside any polling
window small enough to look continuous without either flooding the poll rate or still
missing fast successive transitions.

## Decision

1. **Cross-zone movement is in scope.** A sprite representing an in-flight offer moves
   from its current zone to the next one when the CLI marks that transition, following
   the same 5-zone layout Phase 1 already established (`agent-config.ts`). This directly
   supersedes Phase 1's "Phase 2 = art swap only" framing — that framing is retired, not
   extended.

2. **The CLI is instrumented to emit stage-transition events**, additively, at the five
   points identified above. Instrumentation must be **best-effort and non-blocking**: if
   the UI backend is not running (the common case — most `applyr` invocations, including
   everything in this session, run with no UI server up), the CLI command must complete
   exactly as it does today, with a short connection timeout and swallowed failure, never
   a hang or a new error surfaced to the CLI's own `--json` contract. This is non-negotiable:
   the CLI's stability and agent-operability (ADR-005, ADR-007) outrank this visualization
   feature.

3. **Persisted per-offer stage state**: `offers` gains a `pipeline_stage` column
   (nullable, one of `recruiter | matching | cv | ats | application | null`) and a
   `pipeline_stage_at` timestamp, via an additive schema migration (v12). `null` means "no
   stage tracked" (e.g., offers created before this migration, or added directly as
   `applied` bypassing the visualized flow) — the scene renders these with no in-transit
   sprite, not a fabricated stage.

4. **Push transport is Server-Sent Events (SSE), not WebSocket.** The UI backend exposes
   one `GET /api/events` SSE stream that broadcasts stage-transition events to connected
   clients; the CLI's instrumentation POSTs the transition to a small internal endpoint,
   which the backend fans out over SSE. This is the part of ADR-012's locked constraint
   that changes: real-time push is now required, but full-duplex WebSocket is not — the
   UI only ever receives, never sends, over this channel. SSE gives that with less
   surface: no connection-upgrade handshake to manage in FastAPI, and the browser's
   `EventSource` API reconnects automatically without hand-written retry logic.

5. **Multiple concurrent in-transit sprites are supported.** Each offer with a non-null
   `pipeline_stage` gets its own sprite; concurrent transitions are independent tweens,
   not serialized onto a single "currently walking" slot.

6. **No retroactive replay.** On page load or SSE reconnect, the frontend fetches current
   `pipeline_stage` for all offers via the existing polling endpoint and renders each
   sprite directly in its real zone — no animation plays for transitions that happened
   before the client connected. Only transitions that arrive live over the SSE stream
   animate.

This ADR decides **movement scope, event ownership, persistence, and transport**. It does
not decide sprite art direction, the exact tween/easing for cross-zone movement, or the
concurrent-sprite collision/layout algorithm when several offers occupy the same zone at
once — those are implementation-spec questions, same boundary ADR-012 drew for engine vs.
scene design.

## Consequences

### Positive

- Closes the exact gap ADR-012 flagged and left open: polling-driven "teleporting"
  sprites, now replaced with real push-driven continuous movement.
- `pipeline_stage` becomes a real, queryable field — useful beyond the animation itself
  (e.g., a future `applyr pipeline --stage cv` filter), not a UI-only side effect.
- SSE's automatic reconnection removes a whole class of connection-state bugs a
  hand-rolled WebSocket client would otherwise need to handle for a single-maintainer
  local tool.
- The non-blocking instrumentation requirement (Decision 2) protects the CLI's core
  identity — agent-operable, stable, `--json`-contracted — from ever depending on the UI
  process being alive.

### Negative

- First backend push-transport infrastructure in the project (SSE endpoint, an internal
  event-fan-out POST endpoint) — more moving parts than any other Visual UI slice shipped
  so far, all of which were pure polling reads.
- Five existing, stable CLI commands (`add`, `cv generate`, `cv review`, `cv pdf`,
  `update`) each need a new instrumentation call site — a wider blast radius across
  already-shipped, tested code than any single slice has touched before. Each call site
  needs its own non-blocking-failure test (per Decision 2), not just a happy-path test.
- Schema v12 migration adds a column every future `offers` row carries — small, additive
  cost, but the schema surface keeps growing (v10 → v11 for `ui_intake`, now v12).
- Concurrent multi-sprite animation is real additional PixiJS complexity (layout when
  several offers share a zone, per-sprite tween lifecycle, cleanup on unmount) on top of
  what Phase 1 shipped — and this project still has no browser-driving test tool, so this
  complexity ships with the same "could not visually confirm" disclosure every prior
  slice already carries, at higher stakes than a static color tween.
- Partially superseding an "Accepted" ADR is itself a cost: a future reader of ADR-012
  needs to know this ADR exists and changes one of its constraints — the header links
  make that discoverable, but it's an extra hop.

### Neutral

- SSE is scoped to this one event stream. It does not replace the existing polling
  mechanism other Visual UI pages use (Analytics, Offers, Settings, Interviews, Archive) —
  those stay polling-only, unchanged.

## Alternatives considered

**Keep polling only, interpolate client-side (ADR-012's original path).** Rejected for
the concurrency requirement specifically: several offers transitioning inside the same
2-3s window are indistinguishable from each other purely from polled snapshots — there's
no reliable way to reconstruct "which offer moved when" well enough to drive independent
per-offer tweens without the transition events themselves.

**WebSocket.** Rejected in favor of SSE for this feature: the UI never needs to send
anything back over this channel, so a full-duplex protocol buys nothing here.
Reconsider only if a genuine bidirectional need appears later (e.g., a future feature
where the UI pushes something back to a running agent process) — not as a default
upgrade path from SSE.

**Faster polling (e.g., 500ms) instead of real push.** Rejected: still fundamentally the
same teleporting-sprite problem at a smaller interval, plus meaningfully higher constant
load on the local SQLite-backed API for a single-user tool, for a worse result than SSE.

**Infer stage from existing columns instead of instrumenting the CLI.** Rejected: `cv`,
`ats`, and `application` stages have no backing column today (Phase 1 explicitly punted
this), so inference would either require guessing or leave 3 of 5 zones permanently
`not_connected` — the same limitation Phase 1 already has. Direct CLI instrumentation is
the only path that gives all 5 zones real state.

## Notes

- The next artifact is the implementation `/sdd` spec, hard-bounded per ADR-012's own
  Notes warning about unbounded scope. It must resolve: sprite art delivery mechanism
  (owner hands off files — format/location convention needed), cross-zone tween/easing,
  concurrent-sprite layout within a zone, and the exact instrumentation call sites and
  their non-blocking-failure tests.
- Per this project's `/adversarial-test` gate (state machine, DB migration), the
  implementation spec's `pipeline_stage` transitions and the schema v12 migration should
  both go through adversarial verification before merge — this was already anticipated in
  ADR-012's Notes and applies more directly now that the state machine is real, not
  hypothetical.
- The internal POST endpoint the CLI calls to emit events is not a public/documented API
  surface (unlike the CLI's own `--json` contracts) — it's private plumbing between the
  CLI process and the local UI backend, and should be treated as free to change without
  the compatibility guarantees `docs/adr/007-structured-json-errors.md` gives the CLI's
  own output contracts.
