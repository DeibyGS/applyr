import { request } from "./client";

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
