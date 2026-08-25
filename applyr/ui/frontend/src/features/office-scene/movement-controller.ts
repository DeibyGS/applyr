import { gsap } from "gsap";
import type { AgentId, AgentVisualState, WorkArtifact } from "./types";
import type { AgentSpriteHandle } from "./agent-sprite";
import { getZonePositions } from "./scene-layout";

/** Duration constants for natural movement */
export const WALK_DURATION = 1.5;
export const HANDOFF_PAUSE_DURATION = 0.3;
export const TRANSFER_DURATION = 0.6;
export const SETTLE_DURATION = 0.2;

/** Easing functions for natural feel */
export const WALK_EASE = "sine.inOut";
export const TRANSFER_EASE_OUT = "power2.out";
export const TRANSFER_EASE_IN = "power2.in";
export const SETTLE_EASE = "power2.out";

/** Path waypoints for arc trajectory */
export function computeArcWaypoints(
  fromX: number,
  fromY: number,
  toX: number,
  toY: number
): { x: number; y: number }[] {
  const midX = (fromX + toX) / 2;
  const midY = Math.min(fromY, toY) - 50; // Arc upward
  return [
    { x: fromX, y: fromY },
    { x: midX, y: midY },
    { x: toX, y: toY },
  ];
}

/** Handoff state for tracking in-flight handoffs */
export interface HandoffState {
  id: string;
  fromAgent: AgentId;
  toAgent: AgentId;
  artifact: WorkArtifact;
  stage: "walking" | "transferring" | "settling" | "complete";
  startTime: number;
  walkTween?: gsap.core.Tween;
  transferTween?: gsap.core.Tween;
  settleTween?: gsap.core.Tween;
}

/**
 * MovementController — orchestrates physical handoffs between agents.
 * 
 * Responsibilities:
 * - Compute paths between agent positions
 * - Drive sender agent walk animation (with artifact)
 * - Coordinate artifact transfer animation
 * - Trigger receiver state transitions
 * - Handle multiple concurrent handoffs
 * - Ensure smooth easing and timing
 */
export class MovementController {
  private activeHandoffs: Map<string, HandoffState> = new Map();
  private agentSprites: Map<AgentId, AgentSpriteHandle> = new Map();
  private artifactSprites: Map<string, any> = new Map(); // WorkArtifactSpriteHandle
  private zonePositions: Map<AgentId, { x: number; y: number }> = new Map();
  private onHandoffComplete: ((handoffId: string, fromAgent: AgentId, toAgent: AgentId) => void) | null = null;

  constructor(agentSprites: Map<AgentId, AgentSpriteHandle>) {
    this.agentSprites = agentSprites;
    this.initializeZonePositions();
  }

  private initializeZonePositions(): void {
    for (const zone of getZonePositions()) {
      this.zonePositions.set(zone.agentId, { x: zone.x, y: zone.y });
    }
  }

  setArtifactSprites(artifactSprites: Map<string, any>): void {
    this.artifactSprites = artifactSprites;
  }

  setHandoffCompleteCallback(
    callback: (handoffId: string, fromAgent: AgentId, toAgent: AgentId) => void
  ): void {
    this.onHandoffComplete = callback;
  }

  /** Start a handoff from one agent to another */
  async startHandoff(
    handoffId: string,
    fromAgent: AgentId,
    toAgent: AgentId,
    artifact: WorkArtifact
  ): Promise<void> {
    const fromSprite = this.agentSprites.get(fromAgent);
    const toSprite = this.agentSprites.get(toAgent);
    const fromZone = this.zonePositions.get(fromAgent);
    const toZone = this.zonePositions.get(toAgent);

    if (!fromSprite || !toSprite || !fromZone || !toZone) {
      console.warn(`[MovementController] Missing sprite/zone for handoff: ${fromAgent} -> ${toAgent}`);
      return;
    }

    // Check if already in progress
    if (this.activeHandoffs.has(handoffId)) {
      console.warn(`[MovementController] Handoff ${handoffId} already in progress`);
      return;
    }

    const state: HandoffState = {
      id: handoffId,
      fromAgent,
      toAgent,
      artifact,
      stage: "walking",
      startTime: Date.now(),
    };
    this.activeHandoffs.set(handoffId, state);

    try {
      // Phase 1: Sender walks to receiver
      await this.walkAgent(fromAgent, toAgent, state);
      
      // Phase 2: Artifact transfer (arc animation)
      await this.transferArtifact(fromAgent, toAgent, artifact, state);
      
      // Phase 3: Settle - sender returns, receiver starts working
      await this.settleHandoff(fromAgent, toAgent, state);
      
      state.stage = "complete";
      this.onHandoffComplete?.(handoffId, fromAgent, toAgent);
    } catch (error) {
      console.error(`[MovementController] Handoff ${handoffId} failed:`, error);
      state.stage = "complete";
    } finally {
      this.activeHandoffs.delete(handoffId);
    }
  }

  /** Walk the sender agent to the receiver's position */
  private async walkAgent(
    fromAgent: AgentId,
    toAgent: AgentId,
    state: HandoffState
  ): Promise<void> {
    const fromSprite = this.agentSprites.get(fromAgent)!;
    const fromZone = this.zonePositions.get(fromAgent)!;
    const toZone = this.zonePositions.get(toAgent)!;

    // Set sender to walking state
    fromSprite.setVisualState("walking");

    // Start walk bob animation
    fromSprite.walkTo(toZone.x, toZone.y);

    // Wait for walk to complete
    return new Promise<void>((resolve) => {
      // We'll use a timeout based on walk duration since we can't easily
      // hook into the agent sprite's internal walk tween
      setTimeout(resolve, WALK_DURATION * 1000);
    });
  }

  /** Animate artifact transfer from sender to receiver */
  private async transferArtifact(
    fromAgent: AgentId,
    toAgent: AgentId,
    artifact: WorkArtifact,
    state: HandoffState
  ): Promise<void> {
    state.stage = "transferring";

    const artifactKey = `handoff-${fromAgent}-${toAgent}`;
    const artifactSprite = this.artifactSprites.get(artifactKey);
    const fromZone = this.zonePositions.get(fromAgent)!;
    const toZone = this.zonePositions.get(toAgent)!;

    if (!artifactSprite) {
      console.warn(`[MovementController] No artifact sprite for ${artifactKey}`);
      return;
    }

    // Animate artifact transfer along arc
    await artifactSprite.transfer(
      fromZone.x, fromZone.y - 40,
      toZone.x, toZone.y - 40
    );
  }

  /** Settle phase: sender returns, receiver transitions to working */
  private async settleHandoff(
    fromAgent: AgentId,
    toAgent: AgentId,
    state: HandoffState
  ): Promise<void> {
    state.stage = "settling";

    const fromSprite = this.agentSprites.get(fromAgent)!;
    const toSprite = this.agentSprites.get(toAgent)!;
    const fromZone = this.zonePositions.get(fromAgent)!;

    // Sender: detach artifact and return to position
    fromSprite.detachArtifact();
    fromSprite.setVisualState("completed");
    
    // Brief pause, then sender returns to idle position
    await new Promise(resolve => setTimeout(resolve, HANDOFF_PAUSE_DURATION * 1000));
    
    // Walk back to original position
    await fromSprite.walkTo(fromZone.x, fromZone.y);
    fromSprite.setVisualState("idle");

    // Receiver: already in receiving state from event, now transition to working
    // This is triggered by the event system, not directly here
    toSprite.setVisualState("working");

    // Settle animation
    await new Promise(resolve => setTimeout(resolve, SETTLE_DURATION * 1000));
  }

  /** Cancel an in-progress handoff */
  cancelHandoff(handoffId: string): void {
    const state = this.activeHandoffs.get(handoffId);
    if (!state) return;

    // Kill any active tweens
    state.walkTween?.kill();
    state.transferTween?.kill();
    state.settleTween?.kill();

    // Reset agents
    const fromSprite = this.agentSprites.get(state.fromAgent);
    const toSprite = this.agentSprites.get(state.toAgent);
    const fromZone = this.zonePositions.get(state.fromAgent);

    if (fromSprite && fromZone) {
      fromSprite.stopWalking();
      fromSprite.detachArtifact();
      fromSprite.walkTo(fromZone.x, fromZone.y);
      fromSprite.setVisualState("idle");
    }

    this.activeHandoffs.delete(handoffId);
  }

  /** Get all active handoffs */
  getActiveHandoffs(): HandoffState[] {
    return Array.from(this.activeHandoffs.values());
  }

  /** Check if a handoff is in progress between two agents */
  isHandoffInProgress(fromAgent: AgentId, toAgent: AgentId): boolean {
    for (const state of this.activeHandoffs.values()) {
      if (state.fromAgent === fromAgent && state.toAgent === toAgent) {
        return true;
      }
    }
    return false;
  }

  /** Update zone positions (if layout changes) */
  updateZonePositions(): void {
    this.zonePositions.clear();
    for (const zone of getZonePositions()) {
      this.zonePositions.set(zone.agentId, { x: zone.x, y: zone.y });
    }
  }

  /** Cleanup all */
  destroy(): void {
    for (const state of this.activeHandoffs.values()) {
      state.walkTween?.kill();
      state.transferTween?.kill();
      state.settleTween?.kill();
    }
    this.activeHandoffs.clear();
  }
}