/**
 * Unified type definitions for the spatial pipeline visualization (Phase 1).
 * These types are shared between the state machine, event bus, and UI components.
 */

import type { AgentId } from "@/features/agents/types";

export type { AgentId } from "@/features/agents/types";

// ============================================================================
// Agent Visual States
// ============================================================================

export type AgentVisualState =
  | "idle"
  | "receiving"
  | "working"
  | "handoff"
  | "walking"
  | "waiting"
  | "blocked"
  | "completed"
  | "error";

// Valid transitions between visual states
export const VALID_STATE_TRANSITIONS: Record<AgentVisualState, AgentVisualState[]> = {
  idle: ["receiving", "waiting", "working"],
  receiving: ["working", "blocked", "error"],
  working: ["handoff", "completed", "blocked", "error", "waiting"],
  handoff: ["walking", "error", "completed"],
  walking: ["handoff", "error"],
  waiting: ["receiving", "working", "idle", "blocked"],
  blocked: ["working", "waiting", "error", "idle"],
  completed: ["idle", "receiving", "handoff"],
  error: ["idle", "waiting", "blocked"],
};

export function isValidTransition(
  from: AgentVisualState,
  to: AgentVisualState
): boolean {
  return VALID_STATE_TRANSITIONS[from]?.includes(to) ?? false;
}

// Visual properties per state
export interface VisualProps {
  ringColor: string;
  bodyColor: string;
  ringAnimation: "none" | "pulse" | "glow" | "shake" | "burst";
  bodyAnimation: "none" | "bob" | "glow" | "shake";
  icon: string;
  label: string;
  bubblePrefix: string;
}

export const VISUAL_PROPS: Record<AgentVisualState, VisualProps> = {
  idle: {
    ringColor: "#9ca3af",
    bodyColor: "#9ca3af",
    ringAnimation: "none",
    bodyAnimation: "none",
    icon: "⏸",
    label: "Idle",
    bubblePrefix: "Waiting for work",
  },
  receiving: {
    ringColor: "#3fa98b",
    bodyColor: "#3fa98b",
    ringAnimation: "glow",
    bodyAnimation: "glow",
    icon: "📥",
    label: "Receiving",
    bubblePrefix: "Receiving",
  },
  working: {
    ringColor: "#2dd4bf",
    bodyColor: "#2dd4bf",
    ringAnimation: "pulse",
    bodyAnimation: "bob",
    icon: "⚙️",
    label: "Working",
    bubblePrefix: "Working",
  },
  handoff: {
    ringColor: "#cb6e45",
    bodyColor: "#cb6e45",
    ringAnimation: "none",
    bodyAnimation: "none",
    icon: "🤝",
    label: "Handoff",
    bubblePrefix: "Handing off",
  },
  walking: {
    ringColor: "#cb6e45",
    bodyColor: "#cb6e45",
    ringAnimation: "none",
    bodyAnimation: "none",
    icon: "🚶",
    label: "Walking",
    bubblePrefix: "Walking to",
  },
  waiting: {
    ringColor: "#d89b5a",
    bodyColor: "#d89b5a",
    ringAnimation: "pulse",
    bodyAnimation: "none",
    icon: "⏳",
    label: "Waiting",
    bubblePrefix: "Waiting for",
  },
  blocked: {
    ringColor: "#c96b52",
    bodyColor: "#c96b52",
    ringAnimation: "shake",
    bodyAnimation: "shake",
    icon: "🚫",
    label: "Blocked",
    bubblePrefix: "Blocked:",
  },
  completed: {
    ringColor: "#4fa98a",
    bodyColor: "#4fa98a",
    ringAnimation: "burst",
    bodyAnimation: "none",
    icon: "✅",
    label: "Completed",
    bubblePrefix: "Delivered",
  },
  error: {
    ringColor: "#c96b52",
    bodyColor: "#c96b52",
    ringAnimation: "shake",
    bodyAnimation: "shake",
    icon: "❌",
    label: "Error",
    bubblePrefix: "Failed:",
  },
};

// ============================================================================
// Work Artifacts
// ============================================================================

export type WorkArtifactType =
  | "job_offer"
  | "compatibility_score"
  | "cv"
  | "ats_review"
  | "cover_letter"
  | "application_package"
  | "interview_scheduled";

export interface BaseArtifact {
  type: WorkArtifactType;
  offerId: number;
  timestamp: string;
}

export interface JobOfferArtifact extends BaseArtifact {
  type: "job_offer";
  title: string;
  company: string;
}

export interface CompatibilityScoreArtifact extends BaseArtifact {
  type: "compatibility_score";
  score: number;
  breakdown: Array<{ topic: string; score: number; weight: number }>;
}

export interface CVArtifact extends BaseArtifact {
  type: "cv";
  sections: string[];
  language: string;
}

export interface ATSReviewArtifact extends BaseArtifact {
  type: "ats_review";
  score: number;
  issues: Array<{ rule: string; severity: "error" | "warning" | "info"; message: string }>;
}

export interface CoverLetterArtifact extends BaseArtifact {
  type: "cover_letter";
  text: string;
}

export interface ApplicationPackageArtifact extends BaseArtifact {
  type: "application_package";
  pdfPath: string;
}

export interface InterviewScheduledArtifact extends BaseArtifact {
  type: "interview_scheduled";
  date: string;
  format: "phone" | "video" | "onsite";
}

export type WorkArtifact =
  | JobOfferArtifact
  | CompatibilityScoreArtifact
  | CVArtifact
  | ATSReviewArtifact
  | CoverLetterArtifact
  | ApplicationPackageArtifact
  | InterviewScheduledArtifact;

export const ARTIFACT_ICONS: Record<WorkArtifactType, string> = {
  job_offer: "📋",
  compatibility_score: "📊",
  cv: "📄",
  ats_review: "🔍",
  cover_letter: "✉️",
  application_package: "📦",
  interview_scheduled: "📅",
};

export const ARTIFACT_LABELS: Record<WorkArtifactType, string> = {
  job_offer: "Job Offer",
  compatibility_score: "Score",
  cv: "CV",
  ats_review: "ATS Review",
  cover_letter: "Cover Letter",
  application_package: "Application",
  interview_scheduled: "Interview",
};

// Artifact sprite handle type (forward declaration for cross-module use)
export interface WorkArtifactSpriteHandle {
  view: any; // Container
  showAtAgent: (agentX: number, agentY: number) => void;
  hide: () => void;
  transfer: (fromX: number, fromY: number, toX: number, toY: number) => Promise<void>;
  spawn: () => void;
  destroy: () => void;
  getArtifact: () => WorkArtifact;
}

export function createArtifact(
  type: WorkArtifactType,
  data: Omit<WorkArtifact, "type" | "timestamp">,
  timestamp = new Date().toISOString()
): WorkArtifact {
  return { ...data, type, timestamp } as WorkArtifact;
}

// ============================================================================
// Event Model
// ============================================================================

export interface BaseApplyrEvent {
  type: string;
  agent_id: AgentId;
  timestamp: string;
  correlation_id: string;
  offer_id?: number;
  received_at?: string;
}

export interface AgentStartedEvent extends BaseApplyrEvent {
  type: "agent.started";
  payload: {
    task: string;
    command?: string;
  };
}

export interface AgentCommandEvent extends BaseApplyrEvent {
  type: "agent.command";
  payload: {
    command: string;
    args: string[];
  };
}

export interface AgentOutputEvent extends BaseApplyrEvent {
  type: "agent.output";
  payload: {
    stdout: string;
    stderr?: string;
  };
}

export interface AgentCompletedEvent extends BaseApplyrEvent {
  type: "agent.completed";
  payload: {
    artifact: WorkArtifact;
    output_summary: string;
  };
}

export interface AgentFailedEvent extends BaseApplyrEvent {
  type: "agent.failed";
  payload: {
    error: string;
    recoverable: boolean;
  };
}

export interface AgentWaitingEvent extends BaseApplyrEvent {
  type: "agent.waiting";
  payload: {
    reason: string;
  };
}

export interface AgentBlockedEvent extends BaseApplyrEvent {
  type: "agent.blocked";
  payload: {
    reason: string;
    blocked_by?: AgentId;
  };
}

export interface AgentReceivingEvent extends BaseApplyrEvent {
  type: "agent.receiving";
  payload: {
    artifact: WorkArtifact;
    from_agent: AgentId;
  };
}

export interface HandoffStartedEvent extends BaseApplyrEvent {
  type: "handoff.started";
  payload: {
    from_agent: AgentId;
    to_agent: AgentId;
    artifact: WorkArtifact;
  };
}

export interface HandoffWalkingEvent extends BaseApplyrEvent {
  type: "handoff.walking";
  payload: {
    from_agent: AgentId;
    to_agent: AgentId;
    progress: number; // 0-1
  };
}

export interface HandoffCompletedEvent extends BaseApplyrEvent {
  type: "handoff.completed";
  payload: {
    from_agent: AgentId;
    to_agent: AgentId;
    artifact: WorkArtifact;
  };
}

export interface PipelineStageEvent extends BaseApplyrEvent {
  type: "pipeline.stage";
  payload: {
    offer_id: number;
    stage: AgentId;
    pipeline_stage_at: string;
  };
}

export type ApplyrEvent =
  | AgentStartedEvent
  | AgentCommandEvent
  | AgentOutputEvent
  | AgentCompletedEvent
  | AgentFailedEvent
  | AgentWaitingEvent
  | AgentBlockedEvent
  | AgentReceivingEvent
  | HandoffStartedEvent
  | HandoffWalkingEvent
  | HandoffCompletedEvent
  | PipelineStageEvent;

// Type guards
export function isAgentEvent(event: ApplyrEvent): event is
  | AgentStartedEvent
  | AgentCommandEvent
  | AgentOutputEvent
  | AgentCompletedEvent
  | AgentFailedEvent
  | AgentWaitingEvent
  | AgentBlockedEvent
  | AgentReceivingEvent {
  return event.type.startsWith("agent.");
}

export function isHandoffEvent(event: ApplyrEvent): event is
  | HandoffStartedEvent
  | HandoffWalkingEvent
  | HandoffCompletedEvent {
  return event.type.startsWith("handoff.");
}

export function isPipelineEvent(event: ApplyrEvent): event is PipelineStageEvent {
  return event.type === "pipeline.stage";
}

// ============================================================================
// Pipeline Definition (Data-Driven)
// ============================================================================

export interface PipelineStage {
  id: AgentId;
  name: string;
  position: { x: number; y: number };
  inputs: WorkArtifactType[];
  outputs: WorkArtifactType[];
  next_stages: AgentId[];
}

export interface PipelineDefinition {
  id: string;
  name: string;
  stages: PipelineStage[];
}

// Default Applyr pipeline (can be overridden via applyr.toml)
export const DEFAULT_PIPELINE: PipelineDefinition = {
  id: "applyr-default",
  name: "Applyr Recruiting Pipeline",
  stages: [
    {
      id: "recruiter",
      name: "Recruiter",
      position: { x: 155, y: 80 },
      inputs: ["job_offer"],
      outputs: ["job_offer"],
      next_stages: ["matching"],
    },
    {
      id: "matching",
      name: "Matching",
      position: { x: 300, y: 80 },
      inputs: ["job_offer"],
      outputs: ["compatibility_score"],
      next_stages: ["cv"],
    },
    {
      id: "cv",
      name: "CV Agent",
      position: { x: 445, y: 80 },
      inputs: ["compatibility_score", "job_offer"],
      outputs: ["cv", "cover_letter"],
      next_stages: ["ats"],
    },
    {
      id: "ats",
      name: "ATS Review",
      position: { x: 215, y: 140 },
      inputs: ["cv"],
      outputs: ["ats_review"],
      next_stages: ["application"],
    },
    {
      id: "application",
      name: "Application",
      position: { x: 385, y: 140 },
      inputs: ["cv", "cover_letter", "ats_review"],
      outputs: ["application_package"],
      next_stages: [],
    },
  ],
};

export function getStageById(pipeline: PipelineDefinition, id: AgentId): PipelineStage | undefined {
  return pipeline.stages.find((s) => s.id === id);
}

export function getNextStages(pipeline: PipelineDefinition, id: AgentId): AgentId[] {
  const stage = getStageById(pipeline, id);
  return stage?.next_stages ?? [];
}

export function validatePipeline(pipeline: PipelineDefinition): string[] {
  const errors: string[] = [];
  const ids = new Set(pipeline.stages.map((s) => s.id));

  if (ids.size !== pipeline.stages.length) {
    errors.push("Duplicate stage IDs");
  }

  for (const stage of pipeline.stages) {
    for (const next of stage.next_stages) {
      if (!ids.has(next)) {
        errors.push(`Stage ${stage.id} references unknown next_stage: ${next}`);
      }
    }
    for (const input of stage.inputs) {
      if (!Object.values(ARTIFACT_ICONS).includes(input as any)) {
        errors.push(`Stage ${stage.id} has unknown input artifact: ${input}`);
      }
    }
    for (const output of stage.outputs) {
      if (!Object.values(ARTIFACT_ICONS).includes(output as any)) {
        errors.push(`Stage ${stage.id} has unknown output artifact: ${output}`);
      }
    }
  }

  return errors;
}