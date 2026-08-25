/**
 * Animation Tokens — centralized timing, easing, and duration constants
 * for consistent, polished animations across the entire office visualization.
 * 
 * All values tuned for 60fps on 5-year-old Intel hardware.
 */

// ============================================================================
// Duration Tokens (ms)
// ============================================================================

export const DURATION = {
  // Core transitions
  instant: 0,
  fast: 80,
  normal: 150,
  slow: 250,
  slower: 400,
  
  // Agent state transitions
  agentStateChange: 150,
  agentStateChangeSlow: 250,
  
  // Walking
  walk: 1500,
  walkFast: 1000,
  walkSlow: 2000,
  walkReturn: 1200,
  
  // Handoff phases
  handoffPause: 300,
  handoffTransfer: 600,
  handoffSettle: 200,
  
  // Artifact
  artifactSpawn: 300,
  artifactFade: 200,
  artifactTransfer: 600,
  
  // Bubbles
  bubbleAppear: 150,
  bubbleDisappear: 100,
  
  // Inspector
  inspectorSlide: 200,
  inspectorFade: 100,
  
  // Micro-animations
  pulse: 900,
  glow: 600,
  shake: 150,
  burst: 500,
  bob: 800,
  walkBob: 400,
  
  // Particles
  particleBurst: 600,
  particleFade: 400,
  
  // Typing indicator
  typingDot: 400,
  
  // Scene
  sceneInit: 300,
  textureLoad: 200,
} as const;

// ============================================================================
// Easing Tokens
// ============================================================================

export const EASING = {
  // Standard
  linear: "linear",
  easeIn: "power2.in",
  easeOut: "power2.out",
  easeInOut: "power2.inOut",
  sineIn: "sine.in",
  sineOut: "sine.out",
  sineInOut: "sine.inOut",
  
  // Springy (for organic feel)
  springGentle: "back.out(1.2)",
  springMedium: "back.out(1.5)",
  springStrong: "back.out(1.7)",
  elasticGentle: "elastic.out(1, 0.5)",
  
  // Sharp (for UI)
  sharpIn: "power3.in",
  sharpOut: "power3.out",
  sharpInOut: "power3.inOut",
  
  // Expressive
  expoIn: "expo.in",
  expoOut: "expo.out",
  expoInOut: "expo.inOut",
  circInOut: "circ.inOut",
  
  // Bounce
  bounceOut: "bounce.out",
  bounceInOut: "bounce.inOut",
} as const;

// ============================================================================
// Animation Presets (duration + easing combinations)
// ============================================================================

export const PRESETS = {
  // State transitions
  stateChange: { duration: DURATION.agentStateChange, ease: EASING.easeInOut },
  stateChangeSlow: { duration: DURATION.agentStateChangeSlow, ease: EASING.sineInOut },
  
  // Walking
  walk: { duration: DURATION.walk, ease: EASING.sineInOut },
  walkFast: { duration: DURATION.walkFast, ease: EASING.easeInOut },
  walkReturn: { duration: DURATION.walkReturn, ease: EASING.easeOut },
  
  // Handoff
  handoffPause: { duration: DURATION.handoffPause, ease: EASING.linear },
  handoffTransfer: { duration: DURATION.handoffTransfer, ease: EASING.easeInOut },
  handoffSettle: { duration: DURATION.handoffSettle, ease: EASING.easeOut },
  
  // Artifact
  artifactSpawn: { duration: DURATION.artifactSpawn, ease: EASING.springMedium },
  artifactFade: { duration: DURATION.artifactFade, ease: EASING.easeIn },
  artifactTransfer: { duration: DURATION.artifactTransfer, ease: EASING.easeInOut },
  
  // Bubbles
  bubbleAppear: { duration: DURATION.bubbleAppear, ease: EASING.springMedium },
  bubbleDisappear: { duration: DURATION.bubbleDisappear, ease: EASING.easeIn },
  
  // Inspector
  inspectorSlide: { duration: DURATION.inspectorSlide, ease: EASING.easeOut },
  inspectorFade: { duration: DURATION.inspectorFade, ease: EASING.easeIn },
  
  // Micro
  pulse: { duration: DURATION.pulse, ease: EASING.sineInOut },
  glow: { duration: DURATION.glow, ease: EASING.sineInOut },
  shake: { duration: DURATION.shake, ease: EASING.linear },
  burst: { duration: DURATION.burst, ease: EASING.easeOut },
  bob: { duration: DURATION.bob, ease: EASING.sineInOut },
  walkBob: { duration: DURATION.walkBob, ease: EASING.sineInOut },
  
  // Particles
  particleBurst: { duration: DURATION.particleBurst, ease: EASING.easeOut },
  particleFade: { duration: DURATION.particleFade, ease: EASING.easeIn },
  
  // Typing
  typingDot: { duration: DURATION.typingDot, ease: EASING.sineInOut },
} as const;

// ============================================================================
// Stagger Tokens
// ============================================================================

export const STAGGER = {
  tight: 30,
  normal: 50,
  loose: 80,
  cascade: 100,
} as const;

// ============================================================================
// Z-Index Layers
// ============================================================================

export const Z_INDEX = {
  floor: 0,
  scenery: 10,
  agent: 100,
  artifact: 500,
  artifactCarried: 600,
  artifactTransfer: 700,
  bubble: 800,
  inspector: 1000,
  overlay: 2000,
} as const;

// ============================================================================
// Visual Constants
// ============================================================================

export const VISUAL = {
  // Agent
  agentRadius: 20,
  agentRingWidth: 52,
  agentRingHeight: 26,
  characterDisplayHeight: 56,
  agentSpacing: 120,
  
  // Bubbles
  bubbleOffsetY: -80,
  bubbleWidth: 220,
  bubbleHeight: 100,
  bubblePadding: 12,
  bubbleRadius: 8,
  bubbleTailHeight: 16,
  bubbleTailWidth: 20,
  
  // Artifacts
  artifactRadius: 14,
  artifactLabelOffsetY: -28,
  
  // Shadows
  contactShadowRadius: 20,
  contactShadowHeight: 8,
  contactShadowAlpha: 0.15,
  
  // Scene
  sceneWidth: 720,
  sceneHeight: 260,
} as const;

// ============================================================================
// Helper: Create GSAP config from preset
// ============================================================================

export function createTweenConfig(
  preset: keyof typeof PRESETS,
  overrides: Partial<{ duration: number; ease: string }> = {}
) {
  const base = PRESETS[preset];
  return {
    duration: overrides.duration ?? base.duration,
    ease: overrides.ease ?? base.ease,
  };
}

// ============================================================================
// Helper: Staggered delays
// ============================================================================

export function getStaggeredDelay(index: number, stagger: keyof typeof STAGGER = "normal"): number {
  return index * STAGGER[stagger];
}