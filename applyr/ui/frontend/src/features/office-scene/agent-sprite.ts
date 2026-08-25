import { Container, Graphics, Sprite, Text, ParticleContainer } from "pixi.js";
import type { Texture } from "pixi.js";
import { gsap } from "gsap";
import type { AgentStatus } from "@/features/agents/types";
import type { ZonePosition } from "./scene-layout";
import { AgentVisualState, VISUAL_PROPS } from "./types";
import type { WorkArtifact } from "./types";
import { createWorkArtifactSprite, type WorkArtifactSpriteHandle } from "./work-artifact-sprite";
import {
  DURATION,
  EASING,
  PRESETS,
  VISUAL,
  Z_INDEX,
} from "./animation-tokens";
import { directionFor, tweenPosition, type PositionTweenHandle, type SpriteDirection } from "./movement-utils";

const RADIUS = VISUAL.agentRadius;

// Color constants for each visual state (matching VISUAL_PROPS in types.ts)
export const STATE_COLORS = {
  idle: 0x9ca3af,
  receiving: 0x3fa98b,
  working: 0x2dd4bf,
  handoff: 0xcb6e45,
  walking: 0xcb6e45,
  waiting: 0xd89b5a,
  blocked: 0xc96b52,
  completed: 0x4fa98a,
  error: 0xc96b52,
} as const satisfies Record<AgentVisualState, number>;

/** Ground ring under the agent — isometric ellipse (2:1 squash), the status
 * indicator that survives whether or not real art is present. */
const RING_WIDTH = VISUAL.agentRingWidth;
const RING_HEIGHT = VISUAL.agentRingHeight;

/** Real-art characters render at this display height regardless of their
 * source resolution (art brief ships them at 128×128 @2x). */
const CHARACTER_DISPLAY_HEIGHT = VISUAL.characterDisplayHeight;

/** Animation durations from tokens (converted to seconds for GSAP) */
const TWEEN_DURATION_S = DURATION.agentStateChange / 1000;
const PULSE_DURATION_S = DURATION.pulse / 1000;
const PULSE_ALPHA_MIN = 0.45;
const GLOW_DURATION_S = DURATION.glow / 1000;
const SHAKE_DURATION_S = DURATION.shake / 1000;
const SHAKE_INTENSITY = 4;
const BURST_DURATION_S = DURATION.burst / 1000;
const BURST_MAX_SCALE = 1.8;
const BOB_DURATION_S = DURATION.bob / 1000;
const BOB_INTENSITY = 3;
const WALK_BOB_DURATION_S = DURATION.walkBob / 1000;
const WALK_BOB_INTENSITY = 2;
const WALK_DURATION_S = DURATION.walk / 1000;

/** Contact shadow constants */
const CONTACT_SHADOW_RADIUS = VISUAL.contactShadowRadius;
const CONTACT_SHADOW_HEIGHT = VISUAL.contactShadowHeight;
const CONTACT_SHADOW_ALPHA = VISUAL.contactShadowAlpha;

/** Particle burst for completed/error */
const PARTICLE_COUNT = 8;
const PARTICLE_DURATION_S = DURATION.particleBurst / 1000;

/** Typing indicator */
const TYPING_DOT_DURATION_S = DURATION.typingDot / 1000;

/** Rim light intensity per state */
const RIM_LIGHT: Record<AgentVisualState, { color: number; intensity: number }> = {
  idle: { color: 0x000000, intensity: 0 },
  receiving: { color: 0x3fa98b, intensity: 0.3 },
  working: { color: 0x2dd4bf, intensity: 0.4 },
  handoff: { color: 0xcb6e45, intensity: 0.5 },
  walking: { color: 0xcb6e45, intensity: 0.3 },
  waiting: { color: 0xd89b5a, intensity: 0.2 },
  blocked: { color: 0xc96b52, intensity: 0.4 },
  completed: { color: 0x4fa98a, intensity: 0.5 },
  error: { color: 0xc96b52, intensity: 0.5 },
};

export interface AgentSpriteHandle {
  /** The stage-level object: a container holding [ring, character]. */
  view: Container;
  /** Swaps the character layer between real art and the placeholder circle,
   * in place — never touches position/zIndex/in-flight tweens. */
  setArt: (texture: Texture | null) => void;
  /** Update with legacy AgentStatus (backward compatible) */
  update: (status: AgentStatus) => void;
  /** Update with new visual state (Phase 2) */
  setVisualState: (state: AgentVisualState, task?: string, command?: string) => void;
  /** Attach a work artifact to the agent (shown in hand during handoff/walking) */
  attachArtifact: (artifact: WorkArtifact) => void;
  /** Detach the work artifact */
  detachArtifact: () => void;
  /** Get the currently attached artifact sprite handle */
  getArtifactSprite: () => WorkArtifactSpriteHandle | null;
  /** Start walking animation toward target position */
  walkTo: (targetX: number, targetY: number) => Promise<void>;
  /** Stop walking animation */
  stopWalking: () => void;
  /** Emit particles for completed/error feedback */
  emitParticles: (type: "success" | "error") => void;
  /** Show typing indicator (for working state with command) */
  showTypingIndicator: (show: boolean) => void;
  destroy: () => void;
}

function colorForStatus(status: AgentStatus): number {
  return status.state === "working" ? STATE_COLORS.working : STATE_COLORS.idle;
}

function colorForVisualState(state: AgentVisualState): number {
  return STATE_COLORS[state];
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

  // Contact shadow (rendered first, at bottom)
  const contactShadow = new Graphics();
  contactShadow.ellipse(0, CONTACT_SHADOW_HEIGHT, CONTACT_SHADOW_RADIUS, CONTACT_SHADOW_HEIGHT)
    .fill({ color: 0x000000, alpha: CONTACT_SHADOW_ALPHA });
  view.addChild(contactShadow);

  // Main ring (ground indicator)
  const ring = new Graphics();
  const paintRing = (color: number) => {
    ring.clear();
    ring.ellipse(0, 0, RING_WIDTH, RING_HEIGHT).fill(color);
  };

  // Rim light (dynamic lighting per state)
  const rimLight = new Graphics();
  view.addChild(rimLight);

  // Placeholder body — fallback circle shown until real art arrives
  const fallbackBody = new Graphics();
  const paintFallback = (color: number) => {
    fallbackBody.clear();
    fallbackBody.circle(0, 0, RADIUS).fill(color);
  };
  view.addChild(ring, fallbackBody);

  // Character sprite (real art)
  let character: Sprite | null = null;

  // Particle container for micro-feedback
  const particles = new Container();
  particles.zIndex = Z_INDEX.agent + 10;
  view.addChild(particles);

  let lastColor = colorForStatus(initialStatus);
  paintRing(lastColor);
  paintFallback(lastColor);

  // Animation tween references
  let alphaTween: gsap.core.Tween | null = null;
  let pulseTween: gsap.core.Tween | null = null;
  let glowTween: gsap.core.Tween | null = null;
  let shakeTween: gsap.core.Tween | null = null;
  let burstTween: gsap.core.Tween | null = null;
  let bobTween: gsap.core.Tween | null = null;
  let walkBobTween: gsap.core.Tween | null = null;
  let rimLightTween: gsap.core.Tween | null = null;
  let typingTween: gsap.core.Timeline | null = null;
  let typingDots: Text[] = [];

  // Artifact display
  let artifactSpriteHandle: WorkArtifactSpriteHandle | null = null;

  const stopPulse = () => {
    pulseTween?.kill();
    pulseTween = null;
    ring.alpha = 1;
  };

  const startPulse = () => {
    if (pulseTween) return;
    const { duration, ease } = PRESETS.pulse;
    pulseTween = gsap.to(ring, {
      alpha: PULSE_ALPHA_MIN,
      duration,
      yoyo: true,
      repeat: -1,
      ease,
    });
  };

  const stopGlow = () => {
    glowTween?.kill();
    glowTween = null;
    ring.alpha = 1;
  };

  const startGlow = () => {
    if (glowTween) return;
    const { duration, ease } = PRESETS.glow;
    glowTween = gsap.to(ring, {
      alpha: 0.3,
      duration,
      yoyo: true,
      repeat: -1,
      ease,
    });
  };

  const stopShake = () => {
    shakeTween?.kill();
    shakeTween = null;
    view.x = zone.x;
  };

  const startShake = () => {
    if (shakeTween) return;
    const { duration, ease } = PRESETS.shake;
    shakeTween = gsap.to(view, {
      x: zone.x + SHAKE_INTENSITY,
      duration,
      yoyo: true,
      repeat: -1,
      ease,
    });
  };

  const stopBob = () => {
    bobTween?.kill();
    bobTween = null;
    if (character) character.y = 0;
    if (fallbackBody) fallbackBody.y = 0;
  };

  const startBob = () => {
    if (bobTween) return;
    const target = character || fallbackBody;
    const { duration, ease } = PRESETS.bob;
    bobTween = gsap.to(target, {
      y: -BOB_INTENSITY,
      duration,
      yoyo: true,
      repeat: -1,
      ease,
    });
  };

  const stopWalkBob = () => {
    walkBobTween?.kill();
    walkBobTween = null;
    if (character) character.y = 0;
    if (fallbackBody) fallbackBody.y = 0;
  };

  const startWalkBob = () => {
    if (walkBobTween) return;
    const target = character || fallbackBody;
    const { duration, ease } = PRESETS.walkBob;
    walkBobTween = gsap.to(target, {
      y: -WALK_BOB_INTENSITY,
      duration,
      yoyo: true,
      repeat: -1,
      ease,
    });
  };

  const stopBurst = () => {
    burstTween?.kill();
    burstTween = null;
  };

  const startBurst = () => {
    if (burstTween) return;
    const { duration, ease } = PRESETS.burst;
    burstTween = gsap.to(ring, {
      scaleX: BURST_MAX_SCALE,
      scaleY: BURST_MAX_SCALE,
      alpha: 0,
      duration,
      ease,
      onComplete: () => {
        ring.scale.set(1);
        ring.alpha = 1;
        burstTween = null;
      },
    });
  };

  const stopRimLight = () => {
    rimLightTween?.kill();
    rimLightTween = null;
    rimLight.clear();
  };

  const updateRimLight = (state: AgentVisualState, animate = true) => {
    const { color, intensity } = RIM_LIGHT[state];
    if (intensity === 0) {
      stopRimLight();
      return;
    }

    const drawRim = (scale: number) => {
      rimLight.clear();
      if (intensity > 0 && scale > 0) {
        rimLight.ellipse(0, -RADIUS * 0.3, RADIUS * 0.9 * scale, RADIUS * 0.4 * scale)
          .fill({ color, alpha: intensity * 0.6 * scale });
      }
    };

    if (animate) {
      stopRimLight();
      drawRim(0);
      const { duration, ease } = PRESETS.pulse;
      rimLightTween = gsap.to({ scale: 0 }, {
        scale: 1,
        duration,
        yoyo: true,
        repeat: -1,
        ease,
        onUpdate: function() {
          drawRim(this.targets()[0].scale);
        },
      });
    } else {
      drawRim(1);
    }
  };

  const stopTyping = () => {
    typingTween?.kill();
    typingTween = null;
    for (const dot of typingDots) {
      view.removeChild(dot);
      dot.destroy();
    }
    typingDots = [];
  };

  const startTyping = () => {
    if (typingTween) return;
    
    // Create three dots
    for (let i = 0; i < 3; i++) {
      const dot = new Text({
        text: "●",
        style: {
          fontSize: 10,
          fill: 0x2dd4bf,
          fontFamily: "ui-monospace, SFMono-Regular",
        },
      });
      dot.anchor.set(0.5, 0);
      dot.x = -15 + i * 10;
      dot.y = -RADIUS - 20;
      dot.alpha = 0;
      view.addChild(dot);
      typingDots.push(dot);
    }

    // Animate dots in sequence
    const { duration, ease } = PRESETS.typingDot;
    const timeline = gsap.timeline({ repeat: -1, yoyo: true });
    typingTween = timeline;
    
    typingDots.forEach((dot, i) => {
      typingTween!.to(dot, {
        alpha: 1,
        duration: duration / 3,
        ease,
      }, i * duration / 6);
      
      typingTween!.to(dot, {
        alpha: 0.3,
        duration: duration / 3,
        ease,
      }, i * duration / 6 + duration / 3);
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
    // Legacy update - map to visual states
    const visualState = status.state === "working" ? "working" : "idle";
    setVisualStateInternal(visualState);
  };

  const setVisualStateInternal = (state: AgentVisualState) => {
    const nextColor = colorForVisualState(state);
    const props = VISUAL_PROPS[state];

    if (nextColor !== lastColor) {
      lastColor = nextColor;
      paintRing(nextColor);
      if (!character) paintFallback(nextColor);
    }

    // Stop all animations
    stopPulse();
    stopGlow();
    stopShake();
    stopBob();
    stopWalkBob();
    stopBurst();
    stopRimLight();
    stopTyping();

    // Start appropriate animation for state
    switch (state) {
      case "working":
        startPulse();
        startBob();
        updateRimLight(state);
        break;
      case "receiving":
        startGlow();
        updateRimLight(state);
        break;
      case "blocked":
      case "error":
        startShake();
        updateRimLight(state);
        break;
      case "completed":
        startBurst();
        updateRimLight(state);
        break;
      case "walking":
        startWalkBob();
        updateRimLight(state);
        break;
      case "handoff":
        updateRimLight(state);
        break;
      case "waiting":
        const { duration, ease } = PRESETS.pulse;
        pulseTween = gsap.to(ring, {
          alpha: 0.6,
          duration: DURATION.pulse / 1000 * 1.5,
          yoyo: true,
          repeat: -1,
          ease,
        });
        updateRimLight(state);
        break;
      case "idle":
      default:
        updateRimLight(state, false);
        break;
    }

    // Handle transition alpha fade
    const resumingMidTween = alphaTween !== null;
    alphaTween?.kill();
    if (!resumingMidTween) {
      view.alpha = 0.35;
    }
    const { duration, ease } = PRESETS.stateChange;
    alphaTween = gsap.to(view, {
      alpha: 1,
      duration,
      ease,
      onComplete: () => {
        alphaTween = null;
      },
    });
  };

  const setVisualState = (state: AgentVisualState, task?: string, command?: string) => {
    setVisualStateInternal(state);
    // Task and command could be used for bubble content (handled by OfficeScene)
    // Store them if needed for bubble rendering
  };

  // Artifact handling
  const attachArtifact = (artifact: WorkArtifact) => {
    if (artifactSpriteHandle) {
      artifactSpriteHandle.hide();
      artifactSpriteHandle = null;
    }

    artifactSpriteHandle = createWorkArtifactSprite(artifact);
    view.addChild(artifactSpriteHandle.view);
    artifactSpriteHandle.showAtAgent(zone.x, zone.y);
    artifactSpriteHandle.spawn();
  };

  const detachArtifact = () => {
    if (artifactSpriteHandle) {
      artifactSpriteHandle.hide();
      artifactSpriteHandle = null;
    }
  };

  const getArtifactSprite = () => artifactSpriteHandle;

  // Walking animation
  let walkTween: gsap.core.Tween | null = null;

  const walkTo = (targetX: number, targetY: number): Promise<void> => {
    return new Promise((resolve) => {
      stopWalkBob();
      startWalkBob();
      
      walkTween?.kill();
      const { duration, ease } = PRESETS.walk;
      walkTween = gsap.to(view, {
        x: targetX,
        y: targetY,
        duration,
        ease,
        onUpdate: () => {
          view.zIndex = view.y;
        },
        onComplete: () => {
          view.zIndex = targetY;
          stopWalkBob();
          walkTween = null;
          resolve();
        },
      });
    });
  };

  const stopWalking = () => {
    walkTween?.kill();
    walkTween = null;
    stopWalkBob();
  };

  // Particle emission for micro-feedback
  const emitParticles = (type: "success" | "error") => {
    const color = type === "success" ? 0x4fa98a : 0xc96b52;
    const icon = type === "success" ? "✓" : "✕";
    
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const angle = (i / PARTICLE_COUNT) * Math.PI * 2;
      const distance = 40 + Math.random() * 20;
      const targetX = Math.cos(angle) * distance;
      const targetY = Math.sin(angle) * distance - 20;
      
      const particle = new Text({
        text: icon,
        style: {
          fontSize: 14,
          fill: color,
          fontFamily: "ui-monospace, SFMono-Regular",
          fontWeight: "bold",
        },
      });
      particle.anchor.set(0.5);
      particle.x = 0;
      particle.y = -RADIUS;
      particle.alpha = 1;
      particle.scale.set(0.5);
      particles.addChild(particle);

      const { duration, ease } = PRESETS.particleBurst;
      gsap.to(particle, {
        x: targetX,
        y: targetY,
        alpha: 0,
        scale: 1.5,
        duration,
        ease,
        onComplete: () => {
          particles.removeChild(particle);
          particle.destroy();
        },
      });
    }
  };

  const showTypingIndicator = (show: boolean) => {
    if (show) {
      startTyping();
    } else {
      stopTyping();
    }
  };

  const destroy = () => {
    alphaTween?.kill();
    stopPulse();
    stopGlow();
    stopShake();
    stopBob();
    stopWalkBob();
    stopBurst();
    stopRimLight();
    stopTyping();
    stopWalking();
    if (artifactSpriteHandle) {
      artifactSpriteHandle.destroy();
      artifactSpriteHandle = null;
    }
    particles.destroy({ children: true });
    view.destroy({ children: true });
  };

  return { 
    view, 
    setArt, 
    update, 
    setVisualState, 
    attachArtifact, 
    detachArtifact, 
    getArtifactSprite, 
    walkTo, 
    stopWalking,
    emitParticles,
    showTypingIndicator,
    destroy 
  };
}

// Re-export movement utilities for pipeline-sprites.ts
export { directionFor, tweenPosition, type PositionTweenHandle, type SpriteDirection } from "./movement-utils";