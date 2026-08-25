import { Graphics } from "pixi.js";
import { gsap } from "gsap";
import { DURATION, EASING } from "./animation-tokens";

/** Facing for the future real art (walk-cycle direction). */
export type SpriteDirection = "up" | "down" | "left" | "right";

/** Duration for movement tweens. */
const MOVE_DURATION_S = DURATION.walk / 1000;

/**
 * Computes the facing direction from a delta vector.
 */
export function directionFor(dx: number, dy: number): SpriteDirection {
  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx >= 0 ? "right" : "left";
  }
  return dy >= 0 ? "down" : "up";
}

/**
 * Tween handle for position animation.
 */
export interface PositionTweenHandle {
  direction: SpriteDirection;
  /** Resolves once the tween completes normally. Never resolves if kill() is called first. */
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
    ease: EASING.sineInOut,
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