import { Container, Graphics, Sprite } from "pixi.js";
import type { Texture } from "pixi.js";
import { gsap } from "gsap";
import type { AgentStatus } from "@/features/agents/types";
import type { ZonePosition } from "./scene-layout";

const RADIUS = 20;
export const COLOR_IDLE = 0x9ca3af;
export const COLOR_WORKING = 0x2dd4bf;

/** Ground ring under the agent — isometric ellipse (2:1 squash), the status
 * indicator that survives whether or not real art is present. */
const RING_WIDTH = 52;
const RING_HEIGHT = 26;

/** Real-art characters render at this display height regardless of their
 * source resolution (art brief ships them at 128×128 @2x). */
const CHARACTER_DISPLAY_HEIGHT = 56;

/** Strictly below POLL_INTERVAL_MS (3000ms, useIntakeAndJobs.ts) so a
 * transition always finishes before the next poll could start another. */
const TWEEN_DURATION_S = 1.2;

/** Working-state pulse (SHOULD AC): a bounded, slow breathing loop on the
 * ring — killed the moment the agent goes idle again. */
const PULSE_ALPHA_MIN = 0.45;
const PULSE_DURATION_S = 0.9;

export interface AgentSpriteHandle {
  /** The stage-level object: a container holding [ring, character]. */
  view: Container;
  /** Swaps the character layer between real art and the placeholder circle,
   * in place — never touches position/zIndex/in-flight tweens. */
  setArt: (texture: Texture | null) => void;
  update: (status: AgentStatus) => void;
  destroy: () => void;
}

function colorForStatus(status: AgentStatus): number {
  return status.state === "working" ? COLOR_WORKING : COLOR_IDLE;
}

/**
 * One zone's sprite: an isometric ground ring reflecting agent state plus a
 * character layer that shows real art when available and today's filled
 * circle otherwise (per-entity fallback, specs/visual-ui-applyr-world-real-art).
 * Every zone (including cv/ats/application, since ADR-013 gave them real
 * backing data via offers.pipeline_stage) is treated uniformly here.
 */
export function createAgentSprite(zone: ZonePosition, initialStatus: AgentStatus): AgentSpriteHandle {
  const view = new Container();
  view.x = zone.x;
  view.y = zone.y;
  view.zIndex = zone.y;

  const ring = new Graphics();
  const paintRing = (color: number) => {
    ring.clear();
    ring.ellipse(0, 0, RING_WIDTH, RING_HEIGHT).fill(color);
  };

  // Placeholder body — byte-for-byte Phase 2's circle, kept for the no-art
  // fallback and shown until/unless real art arrives.
  const fallbackBody = new Graphics();
  const paintFallback = (color: number) => {
    fallbackBody.clear();
    fallbackBody.circle(0, 0, RADIUS).fill(color);
  };
  view.addChild(ring, fallbackBody);

  let character: Sprite | null = null;
  let lastColor = colorForStatus(initialStatus);
  paintRing(lastColor);
  paintFallback(lastColor);

  let alphaTween: gsap.core.Tween | null = null;
  let pulseTween: gsap.core.Tween | null = null;

  const stopPulse = () => {
    pulseTween?.kill();
    pulseTween = null;
    ring.alpha = 1;
  };

  const startPulse = () => {
    if (pulseTween) return;
    pulseTween = gsap.to(ring, {
      alpha: PULSE_ALPHA_MIN,
      duration: PULSE_DURATION_S,
      yoyo: true,
      repeat: -1,
      ease: "sine.inOut",
    });
  };

  const setArt = (texture: Texture | null) => {
    if (!texture) {
      if (character) {
        view.removeChild(character);
        character.destroy();
        character = null;
      }
      fallbackBody.visible = true;
      return;
    }

    if (!character) {
      character = new Sprite(texture);
      character.anchor.set(0.5, 1);
      view.addChild(character);
    } else {
      character.texture = texture;
    }
    character.scale.set(CHARACTER_DISPLAY_HEIGHT / texture.height);
    fallbackBody.visible = false;
  };

  const update = (status: AgentStatus) => {
    const nextColor = colorForStatus(status);

    if (nextColor !== lastColor) {
      lastColor = nextColor;
      paintRing(nextColor);
      if (!character) paintFallback(nextColor);
      if (nextColor === COLOR_WORKING) startPulse();
      else stopPulse();

      // Only dim-then-fade on a fresh transition. If we're interrupting a
      // tween already in flight, keep whatever alpha it had reached and
      // fade on from there — resetting unconditionally would flash the
      // sprite on every interruption instead of continuing smoothly.
      const resumingMidTween = alphaTween !== null;
      alphaTween?.kill();
      if (!resumingMidTween) {
        view.alpha = 0.35;
      }
      alphaTween = gsap.to(view, {
        alpha: 1,
        duration: TWEEN_DURATION_S,
        onComplete: () => {
          alphaTween = null;
        },
      });
    }
  };

  const destroy = () => {
    alphaTween?.kill();
    stopPulse();
    view.destroy({ children: true });
  };

  return { view, setArt, update, destroy };
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
 * Tweens `graphics` from its current position to (targetX, targetY).
 * zIndex tracks the interpolated y every frame (onUpdate) so the offer layers
 * correctly against scenery it walks past, and lands on the target zone's y
 * (isometric depth-sort, per scene-layout.ts).
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
    onUpdate: () => {
      graphics.zIndex = graphics.y;
    },
    onComplete: () => {
      graphics.zIndex = targetY;
      resolveDone();
    },
  });

  return { direction, done, kill: () => tween.kill() };
}
