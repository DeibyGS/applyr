export type AgentId = "recruiter" | "matching" | "cv" | "ats" | "application";

/** Pipeline stages in order — used for progress bar calculation. */
export type PipelineStage = "matching" | "cv" | "ats" | "application";

/** A pending intake row, shaped for the Recruiter queue modal — not clickable,
 * no offer exists yet to navigate to. */
export type IntakeQueueItem = {
  intakeId: number;
  preview: string;
  createdAt: string;
};

/** A real offer, shaped for the Matching/CV/ATS/Application queue modals —
 * clickable, links to /offers/:id. */
export type JobQueueItem = {
  offerId: number;
  company: string;
  title: string;
  compatibilityPct: number;
  createdAt: string;
};

// ADR-013 gave cv/ats/application real backing data (offers.pipeline_stage),
// so — like recruiter/matching before them — they now report working/idle
// from that real state instead of a permanent "not_connected" placeholder.
//
// `items` carries the FULL backlog behind each "working" state, not just the
// single most-recent one the collapsed card already summarizes — the agent
// queue modal reads it to show what else is waiting.
//
// `pipelineStage` is the highest stage reached by the most recent offer in
// the queue — used by AgentCard to render the progress bar.
export type AgentStatus =
  | { agentId: "recruiter"; state: "working"; pendingCount: number; items: IntakeQueueItem[]; pipelineStage?: PipelineStage }
  | { agentId: "recruiter"; state: "idle" }
  | {
      agentId: "matching";
      state: "working";
      company: string;
      compatibilityPct: number;
      items: JobQueueItem[];
      pipelineStage?: PipelineStage;
    }
  | { agentId: "matching"; state: "idle" }
  | { agentId: "cv" | "ats" | "application"; state: "working"; count: number; items: JobQueueItem[]; pipelineStage?: PipelineStage }
  | { agentId: "cv" | "ats" | "application"; state: "idle" };
