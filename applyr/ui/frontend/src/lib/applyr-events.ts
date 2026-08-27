/**
 * Real-time event shapes carried by GET /api/events/enriched (ADR-013).
 * Extracted from the former features/office-scene/types.ts when the spatial
 * PixiJS scene was replaced by the flow diagram — these shapes are just the
 * SSE payload contract, no rendering concerns.
 */

import type { AgentId } from "@/features/agents/types";

export type { AgentId } from "@/features/agents/types";

// ============================================================================
// Work Artifacts (payload carried by agent/handoff events)
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
