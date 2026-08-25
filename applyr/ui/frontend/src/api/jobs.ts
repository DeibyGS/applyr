import { request } from "./client";
import type { PipelineStageEvent } from "./events";

export type JobSummary = {
  id: number;
  title: string;
  company: string;
  status: string;
  compatibility_pct: number;
  work_mode: string | null;
  location: string | null;
  seniority_level: string | null;
  role_category: string | null;
  created_at: string;
  date_applied: string | null;
  /** ADR-013 — null means no real transition has been recorded for this
   * offer yet (pre-Phase-2 offer, or added directly as `applied`). */
  pipeline_stage: PipelineStageEvent["stage"] | null;
};

export type Topic = {
  topic: string;
  score: number;
  detail: string;
  confidence: string | null;
};

export type JobDetail = JobSummary & { topics: Topic[] };

export function listJobs(): Promise<JobSummary[]> {
  return request("/api/jobs");
}

export function getJob(id: number): Promise<JobDetail> {
  return request(`/api/jobs/${id}`);
}
