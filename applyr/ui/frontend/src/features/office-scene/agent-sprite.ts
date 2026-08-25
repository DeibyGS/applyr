import { Graphics } from "pixi.js";
import { gsap } from "gsap";
import type { AgentStatus } from "@/features/agents/types";
import type { ZonePosition } from "./scene-layout";

const RADIUS = 20;
const COLOR_IDLE = 0x9ca3af;
const COLOR_WORKING = 0x2dd4bf;

/** Strictly below POLL_INTERVAL_MS (3000ms, useIntakeAndJobs.ts) so a
 * transition always finishes before the next poll could start another. */
const TWEEN_DURATION_S = 1.2;

export interface AgentSpriteHandle {
  graphics: Graphics;
  update: (status: AgentStatus) => void;
  destroy: () => void;
}

function colorForStatus(status: AgentStatus): number {
  return status.state === "working" ? COLOR_WORKING : COLOR_IDLE;
}

/**
 * One zone's placeholder sprite: a filled isometric-positioned circle whose
 * color reflects agent state. Every zone (including cv/ats/application,
 * since ADR-013 gave them real backing data via offers.pipeline_stage) is
 * treated uniformly here — none are hardcoded to a fixed color anymore.
 */
export function createAgentSprite(zone: ZonePosition, initialStatus: AgentStatus): AgentSpriteHandle {
  const graphics = new Graphics();
  graphics.x = zone.x;
  graphics.y = zone.y;
  graphics.zIndex = zone.y;

  const paint = (color: number) => {
    graphics.clear();
    graphics.circle(0, 0, RADIUS).fill(color);
  };

  let lastColor = colorForStatus(initialStatus);
  paint(lastColor);

  let tween: gsap.core.Tween | null = null;

  const update = (status: AgentStatus) => {
    const nextColor = colorForStatus(status);
    if (nextColor === lastColor) return;
    lastColor = nextColor;

    // Only dim-then-fade on a fresh transition. If we're interrupting a
    // tween already in flight, keep whatever alpha it had reached and
    // fade on from there — resetting to 0.35 unconditionally would flash
    // the sprite on every interruption instead of continuing smoothly.
    const resumingMidTween = tween !== null;
    tween?.kill();
    paint(nextColor);
    if (!resumingMidTween) {
      graphics.alpha = 0.35;
    }
    tween = gsap.to(graphics, {
      alpha: 1,
      duration: TWEEN_DURATION_S,
      onComplete: () => {
        tween = null;
      },
    });
  };

  const destroy = () => {
    tween?.kill();
    graphics.destroy();
  };

  return { graphics, update, destroy };
}

// ---------------------------------------------------------------------------
// Applyr World Phase 2 (ADR-013): position tweening for per-offer sprites.
// The 5 zone sprites above never move — this is a separate capability
// pipeline-sprites.ts uses for the sprites that represent an offer walking
// between zones.
// ---------------------------------------------------------------------------

/** Facing for the future real art (walk-cycle direction). With today's
 * fixed single-row ZONE_ORDER (scene-layout.ts), movement is always one
 * diagonal step forward — "right" is the only direction this layout ever
 * produces in practice; "up"/"down"/"left" only fire once a future,
 * non-linear layout exists. See specs/visual-ui-applyr-world-phase2's Edge
 * cases. */
export type SpriteDirection = "up" | "down" | "left" | "right";

/** Bounded and fixed, same reasoning as TWEEN_DURATION_S: a move must always
 * visibly complete, never feel instantaneous or open-ended. */
const MOVE_DURATION_S = 1.0;

export function directionFor(dx: number, dy: number): SpriteDirection {
  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx >= 0 ? "right" : "left";
  }
  return dy >= 0 ? "down" : "up";
}

export interface PositionTweenHandle {
  direction: SpriteDirection;
  /** Resolves once the tween completes normally. Never resolves if kill()
   * is called first — callers that kill() must not also await this. */
  done: Promise<void>;
  kill: () => void;
}

/**
 * Tweens `graphics` from its current position to (targetX, targetY),
 * updating zIndex on completion so isometric depth-sort (sort-by-Y, per
 * scene-layout.ts) stays correct after the move.
 */
export function tweenPosition(graphics: Graphics, targetX: number, targetY: number): PositionTweenHandle {
  const direction = directionFor(targetX - graphics.x, targetY - graphics.y);

  let resolveDone: () => void;
  const done = new Promise<void>((resolve) => {
    resolveDone = resolve;
  });

  const tween = gsap.to(graphics, {
    x: targetX,
    y: targetY,
    duration: MOVE_DURATION_S,
    onComplete: () => {
      graphics.zIndex = targetY;
      resolveDone();
    },
  });

  return { direction, done, kill: () => tween.kill() };
}
