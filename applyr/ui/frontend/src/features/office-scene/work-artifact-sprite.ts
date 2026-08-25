import { Container, Graphics, Text, Sprite } from "pixi.js";
import type { Texture } from "pixi.js";
import { gsap } from "gsap";
import type { WorkArtifact, WorkArtifactType } from "./types";
import { ARTIFACT_ICONS, ARTIFACT_LABELS } from "./types";
import {
  DURATION,
  EASING,
  PRESETS,
  VISUAL,
  Z_INDEX,
} from "./animation-tokens";

/** Artifact display size */
const ARTIFACT_RADIUS = VISUAL.artifactRadius;
const ARTIFACT_LABEL_OFFSET_Y = -28;

/** Artifact colors by type (matching the visual design) */
const ARTIFACT_COLORS: Record<WorkArtifactType, number> = {
  job_offer: 0x3fa98b,           // teal
  compatibility_score: 0xd95926, // orange/red
  cv: 0x3987e5,                  // blue
  ats_review: 0xc98500,          // gold/yellow
  cover_letter: 0xd55181,        // pink/magenta
  application_package: 0x008300, // green
  interview_scheduled: 0x199e70, // emerald
};

/** Glow pulse for carried artifacts */
const CARRIED_GLOW_DURATION = DURATION.glow / 1000;
const CARRIED_GLOW_ALPHA_MIN = 0.5;

/** Transfer animation duration */
const TRANSFER_DURATION = DURATION.artifactTransfer / 1000;

/** Artifact spawn/fade duration */
const SPAWN_DURATION = DURATION.artifactSpawn / 1000;
const FADE_DURATION = DURATION.artifactFade / 1000;

/** Contact shadow for artifact */
const ARTIFACT_SHADOW_RADIUS = 12;
const ARTIFACT_SHADOW_HEIGHT = 4;
const ARTIFACT_SHADOW_ALPHA = 0.2;

export interface WorkArtifactSpriteHandle {
  view: Container;
  /** Show the artifact at the agent's position (carried) */
  showAtAgent: (agentX: number, agentY: number) => void;
  /** Hide the artifact */
  hide: () => void;
  /** Animate transfer from one agent position to another */
  transfer: (fromX: number, fromY: number, toX: number, toY: number) => Promise<void>;
  /** Spawn animation (scale up from 0) */
  spawn: () => void;
  /** Fade out and destroy */
  destroy: () => void;
  /** Get the artifact data */
  getArtifact: () => WorkArtifact;
}

/**
 * Creates a visual representation of a work artifact.
 * The artifact can be:
 * - Carried by an agent (attached to their sprite, moves with them)
 * - In transit between agents (animated transfer)
 * - Floating at a zone (waiting to be picked up)
 */
export function createWorkArtifactSprite(artifact: WorkArtifact): WorkArtifactSpriteHandle {
  const view = new Container();
  view.visible = false;
  view.zIndex = Z_INDEX.artifact; // Above agents but below bubbles

  // Contact shadow
  const contactShadow = new Graphics();
  contactShadow.ellipse(0, ARTIFACT_SHADOW_HEIGHT, ARTIFACT_SHADOW_RADIUS, ARTIFACT_SHADOW_HEIGHT)
    .fill({ color: 0x000000, alpha: ARTIFACT_SHADOW_ALPHA });
  view.addChild(contactShadow);

  // Main artifact circle with gradient-like appearance
  const body = new Graphics();
  const color = ARTIFACT_COLORS[artifact.type];
  body.circle(0, 0, ARTIFACT_RADIUS).fill(color);
  body.stroke({ color: 0xffffff, width: 2, alpha: 0.9 });
  view.addChild(body);

  // Inner highlight for depth
  const highlight = new Graphics();
  highlight.circle(-3, -3, ARTIFACT_RADIUS * 0.4)
    .fill({ color: 0xffffff, alpha: 0.2 });
  view.addChild(highlight);

  // Icon text in center
  const iconText = new Text({
    text: ARTIFACT_ICONS[artifact.type],
    style: {
      fontSize: 18,
      fill: 0xffffff,
      fontFamily: "Inter Variable, ui-sans-serif, system-ui",
    },
  });
  iconText.anchor.set(0.5, 0.5);
  view.addChild(iconText);

  // Label below
  const labelText = new Text({
    text: ARTIFACT_LABELS[artifact.type],
    style: {
      fontSize: 9,
      fill: 0xf0ede6,
      fontFamily: "Inter Variable, ui-sans-serif, system-ui",
      fontWeight: "500",
    },
  });
  labelText.anchor.set(0.5, 0);
  labelText.y = ARTIFACT_LABEL_OFFSET_Y;
  labelText.visible = false; // Hidden by default, show on hover or when stationary
  view.addChild(labelText);

  // Glow effect for carried state
  let glowTween: gsap.core.Tween | null = null;
  let carriedGlowGraphics: Graphics | null = null;

  const startCarriedGlow = () => {
    if (glowTween) return;
    if (!carriedGlowGraphics) {
      carriedGlowGraphics = new Graphics();
      carriedGlowGraphics.circle(0, 0, ARTIFACT_RADIUS + 6)
        .fill({ color: 0xffffff, alpha: 0.1 });
      view.addChildAt(carriedGlowGraphics, 0);
    }
    const { duration, ease } = PRESETS.glow;
    glowTween = gsap.to(carriedGlowGraphics, {
      alpha: CARRIED_GLOW_ALPHA_MIN,
      scaleX: 1.4,
      scaleY: 1.4,
      duration,
      yoyo: true,
      repeat: -1,
      ease,
    });
  };

  const stopCarriedGlow = () => {
    glowTween?.kill();
    glowTween = null;
    if (carriedGlowGraphics) {
      carriedGlowGraphics.alpha = 0;
    }
  };

  // Transfer animation (arc trajectory with easing)
  let transferTween: gsap.core.Tween | null = null;

  const showAtAgent = (agentX: number, agentY: number) => {
    view.visible = true;
    view.x = agentX;
    view.y = agentY - 45; // Above agent's head
    view.zIndex = Z_INDEX.artifactCarried;
    startCarriedGlow();
  };

  const hide = () => {
    view.visible = false;
    stopCarriedGlow();
    transferTween?.kill();
    transferTween = null;
  };

  const transfer = (fromX: number, fromY: number, toX: number, toY: number): Promise<void> => {
    return new Promise((resolve) => {
      view.visible = true;
      view.x = fromX;
      view.y = fromY - 45;
      view.zIndex = Z_INDEX.artifactTransfer;
      stopCarriedGlow();

      // Arc trajectory for natural handoff feel
      const midX = (fromX + toX) / 2;
      const midY = Math.min(fromY, toY) - 70; // Arc upward

      transferTween?.kill();
      
      // First half: to midpoint (arc up)
      const { duration: halfDur, ease: easeOut } = PRESETS.artifactTransfer;
      transferTween = gsap.to(view, {
        x: midX,
        y: midY,
        duration: halfDur * 0.5,
        ease: EASING.easeOut,
        onComplete: () => {
          // Second half: to target (arc down)
          transferTween = gsap.to(view, {
            x: toX,
            y: toY - 45,
            duration: halfDur * 0.5,
            ease: EASING.easeIn,
            onComplete: () => {
              view.zIndex = Z_INDEX.artifactCarried;
              startCarriedGlow();
              transferTween = null;
              resolve();
            },
          });
        },
      });
    });
  };

  const spawn = () => {
    view.visible = true;
    view.scale.set(0);
    view.alpha = 0;
    const { duration, ease } = PRESETS.artifactSpawn;
    gsap.to(view, {
      scale: 1,
      alpha: 1,
      duration,
      ease,
    });
  };

  const destroy = () => {
    return new Promise<void>((resolve) => {
      stopCarriedGlow();
      transferTween?.kill();
      const { duration, ease } = PRESETS.artifactFade;
      gsap.to(view, {
        scale: 0,
        alpha: 0,
        duration,
        ease,
        onComplete: () => {
          view.visible = false;
          view.destroy({ children: true });
          resolve();
        },
      });
    });
  };

  const getArtifact = () => artifact;

  return { view, showAtAgent, hide, transfer, spawn, destroy, getArtifact };
}

/**
 * Factory for creating artifact sprites from event payloads.
 * Maps the event's artifact data to the appropriate WorkArtifact type.
 */
export function createArtifactSpriteFromEvent(
  artifactData: WorkArtifact
): WorkArtifactSpriteHandle {
  return createWorkArtifactSprite(artifactData);
}