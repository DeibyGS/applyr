import { Graphics } from "pixi.js";
import { gsap } from "gsap";
import type { AgentStatus } from "@/features/agents/types";
import type { ZonePosition } from "./scene-layout";

const RADIUS = 20;
const COLOR_IDLE = 0x9ca3af;
const COLOR_WORKING = 0x2dd4bf;
const COLOR_NOT_CONNECTED = 0x4b5563;

/** Strictly below POLL_INTERVAL_MS (3000ms, useIntakeAndJobs.ts) so a
 * transition always finishes before the next poll could start another. */
const TWEEN_DURATION_S = 1.2;

export interface AgentSpriteHandle {
  graphics: Graphics;
  update: (status: AgentStatus) => void;
  destroy: () => void;
}

function colorForStatus(status: AgentStatus): number {
  if (status.state === "not_connected") return COLOR_NOT_CONNECTED;
  return status.state === "working" ? COLOR_WORKING : COLOR_IDLE;
}

/**
 * One zone's placeholder sprite: a filled isometric-positioned circle whose
 * color reflects agent state. cv/ats/application always render
 * COLOR_NOT_CONNECTED and are never tweened — they have no real backing
 * state, so animating them would fabricate activity (AGENTS.md invariant).
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
    if (status.state === "not_connected") return;

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
