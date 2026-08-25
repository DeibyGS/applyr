/**
 * Agent State Machine — pure TypeScript, no React/Pixi dependencies.
 * Deterministic, fully testable, framework-agnostic.
 */

import {
  AgentId,
  AgentVisualState,
  ApplyrEvent,
  VisualProps,
  VISUAL_PROPS,
  isValidTransition,
  WorkArtifact,
} from "./types";

export interface AgentStateSnapshot {
  agentId: string;
  visualState: AgentVisualState;
  currentTask: string | null;
  currentCommand: string | null;
  currentArtifact: WorkArtifact | null;
  outputSummary: string | null;
  error: string | null;
  timestamps: {
    startedAt: string | null;
    completedAt: string | null;
    lastTransitionAt: string | null;
  };
  eventHistory: ApplyrEvent[];
}

interface InternalState {
  visualState: AgentVisualState;
  currentTask: string | null;
  currentCommand: string | null;
  currentArtifact: WorkArtifact | null;
  outputSummary: string | null;
  error: string | null;
  timestamps: {
    startedAt: string | null;
    completedAt: string | null;
    lastTransitionAt: string | null;
  };
  eventHistory: ApplyrEvent[];
}

const INITIAL_STATE: InternalState = {
  visualState: "idle",
  currentTask: null,
  currentCommand: null,
  currentArtifact: null,
  outputSummary: null,
  error: null,
  timestamps: {
    startedAt: null,
    completedAt: null,
    lastTransitionAt: null,
  },
  eventHistory: [],
};

const MAX_HISTORY = 100;

/**
 * Pure state machine for agent visual state.
 * All transitions driven by ApplyrEvent — no internal timers or async.
 */
export class AgentStateMachine {
  private state: InternalState;
  private agentId: string;

  constructor(agentId: string) {
    this.agentId = agentId;
    this.state = { ...INITIAL_STATE };
  }

  /** Current visual state */
  getVisualState(): AgentVisualState {
    return this.state.visualState;
  }

  /** Full snapshot for inspector/UI */
  getSnapshot(): AgentStateSnapshot {
    return {
      agentId: this.agentId,
      visualState: this.state.visualState,
      currentTask: this.state.currentTask,
      currentCommand: this.state.currentCommand,
      currentArtifact: this.state.currentArtifact,
      outputSummary: this.state.outputSummary,
      error: this.state.error,
      timestamps: { ...this.state.timestamps },
      eventHistory: [...this.state.eventHistory],
    };
  }

  /** Visual properties for rendering (color, animation, icon, label) */
  getVisualProps(): VisualProps {
    return VISUAL_PROPS[this.state.visualState];
  }

  /** Process an event and transition state if valid */
  transition(event: ApplyrEvent): { previous: AgentVisualState; current: AgentVisualState; changed: boolean } {
    const previous = this.state.visualState;
    const next = this.computeNextState(event);

    if (next !== previous && !isValidTransition(previous, next)) {
      // Invalid transition — log but don't crash; stay in current state
      console.warn(
        `[AgentStateMachine:${this.agentId}] Invalid transition ${previous} -> ${next} from event ${event.type}`
      );
      return { previous, current: previous, changed: false };
    }

    if (next !== previous) {
      this.state.visualState = next;
      this.state.timestamps.lastTransitionAt = event.timestamp;
    }

    // Update contextual data based on event type
    this.applyEventData(event);

    // Append to history (bounded)
    this.state.eventHistory.push(event);
    if (this.state.eventHistory.length > MAX_HISTORY) {
      this.state.eventHistory.shift();
    }

    return { previous, current: next, changed: next !== previous };
  }

  /** Compute next visual state from event — pure logic */
  private computeNextState(event: ApplyrEvent): AgentVisualState {
    const current = this.state.visualState;

    switch (event.type) {
      case "agent.started":
        return "receiving";

      case "agent.command":
      case "agent.output":
        // Transition to working from receiving or stay in working
        return current === "working" || current === "receiving" ? "working" : current;

      case "agent.completed":
        // Valid from working or handoff
        return current === "working" || current === "handoff" ? "completed" : current;

      case "agent.failed":
        return "error";

      case "agent.waiting":
        return "waiting";

      case "agent.blocked":
        return "blocked";

      case "agent.receiving":
        return "receiving";

      case "handoff.started":
        // Can start handoff from working or completed
        return current === "working" || current === "completed" ? "handoff" : current;

      case "handoff.walking":
        return "walking";

      case "handoff.completed":
        // Sender goes to completed, receiver handled by agent.receiving
        return this.agentId === event.payload.from_agent ? "completed" : current;

      case "pipeline.stage":
        // Legacy pipeline stage event — map to working for that agent
        if (event.payload.stage === this.agentId) {
          return "working";
        }
        return current;

      default:
        return current;
    }
  }

  /** Apply event-specific data to state */
  private applyEventData(event: ApplyrEvent): void {
    switch (event.type) {
      case "agent.started":
        this.state.currentTask = event.payload.task;
        this.state.currentCommand = event.payload.command ?? null;
        this.state.error = null;
        if (!this.state.timestamps.startedAt) {
          this.state.timestamps.startedAt = event.timestamp;
        }
        break;

      case "agent.command":
        this.state.currentCommand = event.payload.command;
        break;

      case "agent.output":
        // Keep last 500 chars of stdout as output summary
        const stdout = event.payload.stdout;
        this.state.outputSummary = stdout.length > 500 ? stdout.slice(-500) : stdout;
        break;

      case "agent.completed":
        this.state.currentArtifact = event.payload.artifact;
        this.state.outputSummary = event.payload.output_summary;
        this.state.currentTask = null;
        this.state.currentCommand = null;
        this.state.timestamps.completedAt = event.timestamp;
        break;

      case "agent.failed":
        this.state.error = event.payload.error;
        this.state.currentTask = null;
        this.state.currentCommand = null;
        break;

      case "agent.waiting":
        this.state.currentTask = event.payload.reason;
        break;

      case "agent.blocked":
        this.state.currentTask = event.payload.reason;
        break;

      case "agent.receiving":
        this.state.currentArtifact = event.payload.artifact;
        this.state.currentTask = `Receiving ${event.payload.artifact.type.replace("_", " ")} from ${event.payload.from_agent}`;
        break;

      case "handoff.started":
        this.state.currentArtifact = event.payload.artifact;
        this.state.currentTask = `Handing off ${event.payload.artifact.type.replace("_", " ")} to ${event.payload.to_agent}`;
        break;

      case "handoff.walking":
        // Progress tracked but state remains walking
        break;

      case "handoff.completed":
        if (this.agentId === event.payload.from_agent) {
          this.state.currentArtifact = null;
          this.state.currentTask = null;
        }
        break;

      case "pipeline.stage":
        // Legacy: minimal update
        if (event.payload.stage === this.agentId) {
          this.state.currentTask = `Processing offer #${event.payload.offer_id}`;
        }
        break;
    }
  }

  /** Force state (for testing or reset) */
  setState(visualState: AgentVisualState): void {
    this.state.visualState = visualState;
    this.state.timestamps.lastTransitionAt = new Date().toISOString();
  }

  /** Reset to initial state */
  reset(): void {
    this.state = { ...INITIAL_STATE };
  }
}

/**
 * Multi-agent state machine manager — holds one AgentStateMachine per agent.
 */
export class AgentStateManager {
  private machines: Map<string, AgentStateMachine> = new Map();
  private pipeline: any; // PipelineDefinition - avoided circular import

  constructor(pipeline?: any) {
    this.pipeline = pipeline;
    // Initialize machines for all known agents
    for (const agentId of ["recruiter", "matching", "cv", "ats", "application"]) {
      this.machines.set(agentId, new AgentStateMachine(agentId));
    }
  }

  getMachine(agentId: string): AgentStateMachine | undefined {
    return this.machines.get(agentId);
  }

  getAllSnapshots(): AgentStateSnapshot[] {
    return Array.from(this.machines.values()).map((m) => m.getSnapshot());
  }

  /** Process event for the relevant agent(s) */
  processEvent(event: ApplyrEvent): Map<string, { previous: AgentVisualState; current: AgentVisualState; changed: boolean }> {
    const results = new Map();

    // Determine which agent(s) this event affects
    const targetAgents = this.getTargetAgents(event);

    for (const agentId of targetAgents) {
      const machine = this.machines.get(agentId);
      if (machine) {
        results.set(agentId, machine.transition(event));
      }
    }

    return results;
  }

  /** Determine which agents should process this event */
  private getTargetAgents(event: ApplyrEvent): AgentId[] {
    // Primary agent from event
    const agents: AgentId[] = [event.agent_id];

    // Handoff events affect both sender and receiver
    if (event.type === "handoff.started" || event.type === "handoff.walking" || event.type === "handoff.completed") {
      const payload = event.payload as { from_agent: AgentId; to_agent: AgentId };
      if (!agents.includes(payload.from_agent)) agents.push(payload.from_agent);
      if (!agents.includes(payload.to_agent)) agents.push(payload.to_agent);
    }

    // Pipeline stage events affect the stage agent (from payload.stage, not event.agent_id)
    if (event.type === "pipeline.stage") {
      const payload = event.payload as { stage: AgentId };
      if (!agents.includes(payload.stage)) agents.push(payload.stage);
    }

    // Filter to known agents
    return agents.filter((a) => this.machines.has(a));
  }

  /** Set pipeline definition (updates positions, transitions) */
  setPipeline(pipeline: any): void {
    this.pipeline = pipeline;
  }

  /** Reset all machines */
  resetAll(): void {
    for (const machine of this.machines.values()) {
      machine.reset();
    }
  }
}