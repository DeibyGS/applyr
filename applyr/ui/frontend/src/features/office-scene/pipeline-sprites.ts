import { Graphics, Text } from "pixi.js";
import type { Container } from "pixi.js";
import type { PipelineStageEvent } from "@/api/events";
import { tweenPosition, type PositionTweenHandle } from "./agent-sprite";
import { getZonePositions } from "./scene-layout";

export type PipelineStage = PipelineStageEvent["stage"];
export type PipelineOffer = { offerId: number; stage: PipelineStage };

const RADIUS = 7; // smaller than the 20px zone sprites — an offer must read as distinct from the zone marker it's resting in or moving through
const COLOR = 0xf59e0b; // amber — distinct from the zone sprite's idle/working/not_connected palette (agent-sprite.ts)
const REST_OFFSET_Y = 28; // below the zone sprite, so the two never visually overlap
const SLOT_OFFSET_X = 16; // horizontal spacing between offers resting in the same zone
const MAX_VISIBLE_PER_ZONE = 5;
const BADGE_STYLE = { fontSize: 10, fill: 0xffffff } as const;

interface TrackedOffer {
  graphics: Graphics;
  stage: PipelineStage;
  tween: PositionTweenHandle | null;
}

export interface PipelineSpriteManager {
  /** Places every offer directly at its real zone, no animation — for
   * initial load and SSE reconnect (spec's "no retroactive replay": only
   * transitions that arrive while connected ever animate). */
  setInitial(offers: PipelineOffer[]): void;
  /** A live transition for one offer. Animates from its last-known position
   * to the new zone; an offer never seen before appears directly at the
   * target zone (there is no real "from" position to animate out of). */
  applyEvent(event: PipelineStageEvent): void;
  destroy(): void;
}

/**
 * Owns every per-offer sprite in the scene — the "offer walking through the
 * pipeline" layer, separate from the 5 fixed zone-status sprites
 * agent-sprite.ts already manages. See specs/visual-ui-applyr-world-phase2.
 */
export function createPipelineSpriteManager(stage: Container): PipelineSpriteManager {
  const zones = new Map(getZonePositions().map((zone) => [zone.agentId, zone]));
  const offers = new Map<number, TrackedOffer>();
  const badges = new Map<PipelineStage, Text>();

  const restPosition = (pipelineStage: PipelineStage, slotIndex: number) => {
    const zone = zones.get(pipelineStage);
    if (!zone) throw new Error(`No zone position for pipeline stage "${pipelineStage}"`);
    return { x: zone.x + slotIndex * SLOT_OFFSET_X, y: zone.y + REST_OFFSET_Y };
  };

  const paint = (graphics: Graphics) => {
    graphics.clear();
    graphics.circle(0, 0, RADIUS).fill(COLOR);
  };

  const clearBadges = () => {
    for (const badge of badges.values()) {
      stage.removeChild(badge);
      badge.destroy();
    }
    badges.clear();
  };

  // Slots and the "+N" overflow badge only apply to offers currently at
  // rest (tween === null) — a sprite mid-flight keeps flying to its raw
  // zone target and is re-slotted once it lands, in the tween's onComplete.
  const recomputeLayout = () => {
    const restingByZone = new Map<PipelineStage, number[]>();
    for (const [offerId, tracked] of offers) {
      if (tracked.tween) continue;
      const list = restingByZone.get(tracked.stage) ?? [];
      list.push(offerId);
      restingByZone.set(tracked.stage, list);
    }

    clearBadges();
    for (const [pipelineStage, offerIds] of restingByZone) {
      offerIds.sort((a, b) => a - b);
      offerIds.forEach((offerId, slotIndex) => {
        const tracked = offers.get(offerId);
        if (!tracked) return;
        const visible = slotIndex < MAX_VISIBLE_PER_ZONE;
        tracked.graphics.visible = visible;
        if (visible) {
          const pos = restPosition(pipelineStage, slotIndex);
          tracked.graphics.x = pos.x;
          tracked.graphics.y = pos.y;
        }
      });

      const overflow = offerIds.length - MAX_VISIBLE_PER_ZONE;
      if (overflow > 0) {
        const pos = restPosition(pipelineStage, MAX_VISIBLE_PER_ZONE);
        const badge = new Text({ text: `+${overflow}`, style: BADGE_STYLE });
        badge.x = pos.x;
        badge.y = pos.y;
        stage.addChild(badge);
        badges.set(pipelineStage, badge);
      }
    }
  };

  const placeAtRest = (offerId: number, pipelineStage: PipelineStage): TrackedOffer => {
    const graphics = new Graphics();
    paint(graphics);
    const pos = restPosition(pipelineStage, 0); // recomputeLayout() slots it correctly right after
    graphics.x = pos.x;
    graphics.y = pos.y;
    stage.addChild(graphics);
    const tracked: TrackedOffer = { graphics, stage: pipelineStage, tween: null };
    offers.set(offerId, tracked);
    return tracked;
  };

  const setInitial = (initialOffers: PipelineOffer[]) => {
    for (const { offerId, stage: pipelineStage } of initialOffers) {
      placeAtRest(offerId, pipelineStage);
    }
    recomputeLayout();
  };

  const applyEvent = ({ offer_id: offerId, stage: nextStage }: PipelineStageEvent) => {
    const existing = offers.get(offerId);
    if (!existing) {
      placeAtRest(offerId, nextStage);
      recomputeLayout();
      return;
    }

    // Spec: a tween is contracted only for an event that actually changes
    // the stage. `existing.stage` is set to the target the moment a tween
    // starts (see below), not only once it lands, so this check also
    // correctly no-ops a duplicate/retried event for a stage the offer is
    // already mid-flight toward — not just a same-stage event at rest.
    // `update <id> applied` re-notifies "application" on an offer already
    // there (refreshing pipeline_stage_at, not a new zone, per the spec's
    // own wording); without this guard that reaches here as a same-stage
    // event and spuriously excludes this offer from recomputeLayout()'s
    // resting set for the length of a fake tween, reshuffling any sibling
    // sharing its zone slot. (Adversarial finding,
    // pipeline-sprites.adversarial.test.ts.)
    if (nextStage === existing.stage) return;

    existing.tween?.kill();
    existing.stage = nextStage;

    // Assign the tween handle BEFORE recomputeLayout() runs below — recompute
    // reads `tracked.tween` to decide who's mid-flight, so setting `stage`
    // without `tween` first would let this offer get slotted into its new
    // zone immediately, before it has actually arrived.
    const target = restPosition(nextStage, 0); // final slot resolved by recomputeLayout() once it lands
    const handle = tweenPosition(existing.graphics, target.x, target.y);
    existing.tween = handle;
    recomputeLayout(); // drops this offer out of its old zone's slots; it isn't slotted into the new one until it lands

    handle.done.then(() => {
      if (offers.get(offerId)?.tween === handle) {
        existing.tween = null;
        recomputeLayout();
      }
    });
  };

  const destroy = () => {
    for (const tracked of offers.values()) {
      tracked.tween?.kill();
      tracked.graphics.destroy();
    }
    offers.clear();
    clearBadges();
  };

  return { setInitial, applyEvent, destroy };
}
