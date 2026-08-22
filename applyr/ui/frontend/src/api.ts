const API_BASE = "http://127.0.0.1:8000";

export type IntakeRow = {
  id: number;
  raw_text: string;
  source_note: string | null;
  status: "pending" | "promoted";
  offer_id: number | null;
  created_at: string;
  promoted_at: string | null;
};

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

class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(body?.message ?? `Request to ${path} failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export function createIntake(rawText: string, sourceNote?: string): Promise<IntakeRow> {
  return request("/api/intake", {
    method: "POST",
    body: JSON.stringify({ raw_text: rawText, source_note: sourceNote || null }),
  });
}

export function listIntake(status?: "pending" | "promoted"): Promise<IntakeRow[]> {
  const query = status ? `?status=${status}` : "";
  return request(`/api/intake${query}`);
}

export function listJobs(): Promise<JobSummary[]> {
  return request("/api/jobs");
}

export function getJob(id: number): Promise<JobDetail> {
  return request(`/api/jobs/${id}`);
}
