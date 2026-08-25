import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentVisualState, WorkArtifact, ApplyrEvent, VisualProps } from "@/features/office-scene/types";
import { AgentStateMachine, AgentStateManager } from "@/features/office-scene/agent-state-machine";
import { EventBus } from "@/features/office-scene/event-bus";
import {
  DEFAULT_PIPELINE,
  VISUAL_PROPS,
  isValidTransition,
} from "@/features/office-scene/types";
import {
  parsePipelineConfig,
  validatePipelineConfig,
  mergePipelineConfig,
} from "@/features/office-scene/pipeline-definition";

function makeEvent(overrides: Partial<ApplyrEvent> = {}): ApplyrEvent {
  const base: ApplyrEvent = {
    type: "agent.started",
    agent_id: "recruiter",
    timestamp: new Date().toISOString(),
    correlation_id: "test-correlation",
    payload: { task: "Test task" },
  };
  return { ...base, ...overrides } as ApplyrEvent;
}

function makeArtifact(type: WorkArtifact["type"], data: Record<string, any> = {}): WorkArtifact {
  const base = { type, offerId: 1, timestamp: new Date().toISOString() };
  return { ...base, ...data } as WorkArtifact;
}

describe("AgentStateMachine", () => {
  let machine: AgentStateMachine;

  beforeEach(() => {
    machine = new AgentStateMachine("recruiter");
  });

  it("starts in idle state", () => {
    expect(machine.getVisualState()).toBe("idle");
  });

  it("transitions idle -> receiving on agent.started", () => {
    const event = makeEvent({ type: "agent.started", payload: { task: "Analyze offer" } });
    const result = machine.transition(event);
    expect(result.previous).toBe("idle");
    expect(result.current).toBe("receiving");
    expect(result.changed).toBe(true);
  });

  it("transitions receiving -> working on agent.command", () => {
    machine.transition(makeEvent({ type: "agent.started" }));
    const event = makeEvent({ type: "agent.command", payload: { command: "applyr add", args: [] } });
    const result = machine.transition(event);
    expect(result.current).toBe("working");
  });

  it("transitions working -> completed on agent.completed", () => {
    machine.transition(makeEvent({ type: "agent.started" }));
    machine.transition(makeEvent({ type: "agent.command" }));
    const event = makeEvent({
      type: "agent.completed",
      payload: { artifact: makeArtifact("job_offer", { title: "Dev", company: "Acme" }), output_summary: "Done" },
    });
    const result = machine.transition(event);
    expect(result.current).toBe("completed");
  });

  it("transitions working -> error on agent.failed", () => {
    machine.transition(makeEvent({ type: "agent.started" }));
    const event = makeEvent({ type: "agent.failed", payload: { error: "Failed", recoverable: true } });
    const result = machine.transition(event);
    expect(result.current).toBe("error");
  });

  it("transitions to waiting on agent.waiting", () => {
    machine.transition(makeEvent({ type: "agent.started" }));
    machine.transition(makeEvent({ type: "agent.command" }));
    const event = makeEvent({ type: "agent.waiting", payload: { reason: "Upstream" } });
    const result = machine.transition(event);
    expect(result.current).toBe("waiting");
  });

  it("transitions to blocked on agent.blocked", () => {
    machine.transition(makeEvent({ type: "agent.started" }));
    machine.transition(makeEvent({ type: "agent.command" }));
    const event = makeEvent({ type: "agent.blocked", payload: { reason: "Downstream full", blocked_by: "cv" } });
    const result = machine.transition(event);
    expect(result.current).toBe("blocked");
  });

  it("handles handoff.started -> handoff", () => {
    // Start in working state (valid for handoff.started)
    machine.transition(makeEvent({ type: "agent.started" }));
    machine.transition(makeEvent({ type: "agent.command" }));
    machine.transition(makeEvent({ type: "agent.completed" }));
    const event = makeEvent({
      type: "handoff.started",
      payload: { from_agent: "recruiter", to_agent: "matching", artifact: makeArtifact("job_offer") },
    });
    const result = machine.transition(event);
    expect(result.current).toBe("handoff");
  });

  it("handles handoff.walking -> walking", () => {
    // Start in handoff state (valid for handoff.walking)
    machine.transition(makeEvent({ type: "agent.started" }));
    machine.transition(makeEvent({ type: "agent.command" }));
    machine.transition(makeEvent({ type: "agent.completed" }));
    machine.transition(makeEvent({
      type: "handoff.started",
      payload: { from_agent: "recruiter", to_agent: "matching", artifact: makeArtifact("job_offer") },
    }));
    const event = makeEvent({
      type: "handoff.walking",
      payload: { from_agent: "recruiter", to_agent: "matching", progress: 0.5 },
    });
    const result = machine.transition(event);
    expect(result.current).toBe("walking");
  });

  it("handles handoff.completed for sender -> completed", () => {
    // Start in handoff state (valid for handoff.completed for sender)
    machine.transition(makeEvent({ type: "agent.started" }));
    machine.transition(makeEvent({ type: "agent.command" }));
    machine.transition(makeEvent({ type: "agent.completed" }));
    machine.transition(makeEvent({
      type: "handoff.started",
      payload: { from_agent: "recruiter", to_agent: "matching", artifact: makeArtifact("job_offer") },
    }));
    const event = makeEvent({
      type: "handoff.completed",
      payload: { from_agent: "recruiter", to_agent: "matching", artifact: makeArtifact("job_offer") },
    });
    const result = machine.transition(event);
    expect(result.current).toBe("completed");
  });

  it("rejects invalid transition", () => {
    // Set up valid completed state
    machine.transition(makeEvent({ type: "agent.started" }));
    machine.transition(makeEvent({ type: "agent.command" }));
    machine.transition(makeEvent({ type: "agent.completed" }));
    // Try to go from completed to working (invalid - completed only goes to idle or receiving)
    const event = makeEvent({ type: "agent.command" });
    const result = machine.transition(event);
    expect(result.current).toBe("completed"); // Stays in completed
    expect(result.changed).toBe(false);
  });

  it("snapshot includes all fields", () => {
    machine.transition(makeEvent({ type: "agent.started", payload: { task: "Test" } }));
    const snapshot = machine.getSnapshot();
    expect(snapshot.agentId).toBe("recruiter");
    expect(snapshot.visualState).toBe("receiving");
    expect(snapshot.currentTask).toBe("Test");
    expect(snapshot.timestamps.startedAt).toBeDefined();
    expect(Array.isArray(snapshot.eventHistory)).toBe(true);
  });

  it("getVisualProps returns correct props per state", () => {
    expect(machine.getVisualProps().label).toBe("Idle");
    machine.transition(makeEvent({ type: "agent.started" }));
    expect(machine.getVisualProps().label).toBe("Receiving");
  });
});

describe("AgentStateManager", () => {
  let manager: AgentStateManager;

  beforeEach(() => {
    manager = new AgentStateManager();
  });

  it("initializes all 5 agents", () => {
    const snapshots = manager.getAllSnapshots();
    expect(snapshots).toHaveLength(5);
    expect(snapshots.map((s) => s.agentId)).toEqual(["recruiter", "matching", "cv", "ats", "application"]);
  });

  it("processes event for correct agent", () => {
    const event = makeEvent({ type: "agent.started", agent_id: "cv" });
    const results = manager.processEvent(event);
    expect(results.has("cv")).toBe(true);
    expect(results.get("cv")?.current).toBe("receiving");
  });

  it("handoff events affect both sender and receiver", () => {
    // First set up sender (recruiter) in working state
    manager.processEvent(makeEvent({ type: "agent.started", agent_id: "recruiter" }));
    manager.processEvent(makeEvent({ type: "agent.command", agent_id: "recruiter" }));
    manager.processEvent(makeEvent({ type: "agent.completed", agent_id: "recruiter" }));

    // Emit handoff.started for sender
    const handoffEvent = makeEvent({
      type: "handoff.started",
      agent_id: "recruiter",
      payload: { from_agent: "recruiter", to_agent: "matching", artifact: makeArtifact("job_offer") },
    });
    const results = manager.processEvent(handoffEvent);

    // Emit agent.receiving for receiver (simulating what notify_handoff_started does)
    const receivingEvent = makeEvent({
      type: "agent.receiving",
      agent_id: "matching",
      payload: { artifact: makeArtifact("job_offer"), from_agent: "recruiter" },
    });
    manager.processEvent(receivingEvent);

    expect(results.has("recruiter")).toBe(true);
    expect(results.has("matching")).toBe(true);
    expect(results.get("recruiter")?.current).toBe("handoff");
    const matchingSnapshot = manager.getMachine("matching")?.getSnapshot();
    expect(matchingSnapshot?.visualState).toBe("receiving");
  });

  it("pipeline.stage events affect stage agent", () => {
    // pipeline.stage transitions the target agent to working
    const event = makeEvent({
      type: "pipeline.stage",
      agent_id: "matching",
      payload: { offer_id: 1, stage: "cv", pipeline_stage_at: new Date().toISOString() },
    });
    const results = manager.processEvent(event);
    expect(results.has("cv")).toBe(true);
    expect(results.get("cv")?.current).toBe("working");
  });

  it("resetAll resets all machines", () => {
    manager.processEvent(makeEvent({ type: "agent.started", agent_id: "recruiter" }));
    manager.resetAll();
    const snapshots = manager.getAllSnapshots();
    expect(snapshots.every((s) => s.visualState === "idle")).toBe(true);
  });
});

describe("EventBus", () => {
  let bus: EventBus;

  beforeEach(() => {
    // Reset singleton
    (EventBus as any).instance = null;
    bus = EventBus.getInstance();
    bus.clearHistory();
  });

  it("singleton returns same instance", () => {
    const bus2 = EventBus.getInstance();
    expect(bus).toBe(bus2);
  });

  it("subscribe and emit", () => {
    const handler = vi.fn();
    const id = bus.subscribe(handler);
    bus.emit(makeEvent({ type: "agent.started", agent_id: "recruiter" }));
    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(expect.objectContaining({ type: "agent.started" }));
  });

  it("unsubscribe removes handler", () => {
    const handler = vi.fn();
    const id = bus.subscribe(handler);
    bus.unsubscribe(id);
    bus.emit(makeEvent({ type: "agent.started" }));
    expect(handler).not.toHaveBeenCalled();
  });

  it("subscribeToAgent filters by agent", () => {
    const handler = vi.fn();
    bus.subscribeToAgent("recruiter", handler);
    bus.emit(makeEvent({ type: "agent.started", agent_id: "recruiter" }));
    bus.emit(makeEvent({ type: "agent.started", agent_id: "cv" }));
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("subscribeToType filters by type", () => {
    const handler = vi.fn();
    bus.subscribeToType("agent.started", handler);
    bus.emit(makeEvent({ type: "agent.started" }));
    bus.emit(makeEvent({ type: "agent.completed" }));
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("maintains agent history", () => {
    bus.emit(makeEvent({ type: "agent.started", agent_id: "recruiter" }));
    bus.emit(makeEvent({ type: "agent.command", agent_id: "recruiter" }));
    bus.emit(makeEvent({ type: "agent.started", agent_id: "cv" }));
    const history = bus.getAgentHistory("recruiter");
    expect(history).toHaveLength(2);
    expect(history.every((e) => e.agent_id === "recruiter")).toBe(true);
  });

  it("maintains global history", () => {
    bus.emit(makeEvent({ type: "agent.started", agent_id: "recruiter" }));
    bus.emit(makeEvent({ type: "agent.completed", agent_id: "cv" }));
    const history = bus.getGlobalHistory();
    expect(history).toHaveLength(2);
  });

  it("getEventsByType filters correctly", () => {
    bus.emit(makeEvent({ type: "agent.started" }));
    bus.emit(makeEvent({ type: "agent.completed" }));
    bus.emit(makeEvent({ type: "handoff.started" }));
    const started = bus.getEventsByType("agent.started");
    expect(started).toHaveLength(1);
    expect(started[0].type).toBe("agent.started");
  });

  it("getEventsByCorrelationId returns linked events", () => {
    const corr = "test-correlation-123";
    bus.emit(makeEvent({ correlation_id: corr, type: "agent.started" }));
    bus.emit(makeEvent({ correlation_id: corr, type: "agent.completed" }));
    bus.emit(makeEvent({ correlation_id: "other", type: "agent.started" }));
    const linked = bus.getEventsByCorrelation(corr);
    expect(linked).toHaveLength(2);
  });

  it("clearHistory resets everything", () => {
    bus.emit(makeEvent({ type: "agent.started" }));
    bus.clearHistory();
    expect(bus.getGlobalHistory()).toHaveLength(0);
    expect(bus.getAgentHistory("recruiter")).toHaveLength(0);
  });

  it("history is bounded", () => {
    for (let i = 0; i < 300; i++) {
      bus.emit(makeEvent({ type: "agent.started", agent_id: "recruiter" }));
    }
    expect(bus.getAgentHistory("recruiter").length).toBeLessThanOrEqual(200);
  });
});

describe("PipelineDefinition", () => {
  it("DEFAULT_PIPELINE has 5 stages", () => {
    expect(DEFAULT_PIPELINE.stages).toHaveLength(5);
    expect(DEFAULT_PIPELINE.stages.map((s) => s.id)).toEqual(["recruiter", "matching", "cv", "ats", "application"]);
  });

  it("parsePipelineConfig converts config to definition", () => {
    const config = {
      id: "custom",
      name: "Custom Pipeline",
      stages: [
        { id: "a", name: "A", position: { x: 0, y: 0 }, inputs: ["job_offer"], outputs: ["job_offer"], next_stages: ["b"] },
        { id: "b", name: "B", position: { x: 100, y: 0 }, inputs: ["job_offer"], outputs: ["result"], next_stages: [] },
      ],
    };
    const pipeline = parsePipelineConfig(config);
    expect(pipeline.id).toBe("custom");
    expect(pipeline.stages).toHaveLength(2);
  });

  it("validatePipelineConfig catches duplicate IDs", () => {
    const config = {
      id: "test",
      name: "Test",
      stages: [
        { id: "a", name: "A", position: { x: 0, y: 0 }, inputs: [], outputs: [], next_stages: [] },
        { id: "a", name: "A dup", position: { x: 100, y: 0 }, inputs: [], outputs: [], next_stages: [] },
      ],
    };
    const errors = validatePipelineConfig(config);
    expect(errors).toContain("Duplicate stage IDs");
  });

  it("validatePipelineConfig catches unknown next_stages", () => {
    const config = {
      id: "test",
      name: "Test",
      stages: [
        { id: "a", name: "A", position: { x: 0, y: 0 }, inputs: [], outputs: [], next_stages: ["b"] },
      ],
    };
    const errors = validatePipelineConfig(config);
    expect(errors.some((e) => e.includes("unknown next_stage"))).toBe(true);
  });

  it("mergePipelineConfig uses defaults when null", () => {
    const merged = mergePipelineConfig(null);
    expect(merged.id).toBe(DEFAULT_PIPELINE.id);
    expect(merged.stages).toHaveLength(5);
  });

  it("mergePipelineConfig overrides specific stages", () => {
    const userConfig = {
      id: "custom",
      name: "Custom",
      stages: [
        { id: "recruiter", name: "Custom Recruiter", position: { x: 50, y: 50 }, inputs: ["job_offer"], outputs: ["job_offer"], next_stages: ["matching"] },
      ],
    };
    const merged = mergePipelineConfig(userConfig);
    const recruiter = merged.stages.find((s) => s.id === "recruiter");
    expect(recruiter?.name).toBe("Custom Recruiter");
    expect(recruiter?.position).toEqual({ x: 50, y: 50 });
  });
});