import { request } from "./client";

// ADR-014: the async intake pipeline's job state, one per intake row.
export type JobState =
  | "queued"
  | "structuring"
  | "deduping"
  | "duplicate"
  | "pending_agent"
  | "ready"
  | "failed";

export type StructuredData = {
  company: string | null;
  title: string | null;
  tech_stack: string | null;
  extraction_method: "labeled" | "heuristic";
};

export type JobRow = {
  id: number;
  intake_id: number;
  state: JobState;
  structured_data: StructuredData | null;
  extraction_method: string | null;
  duplicate_of_offer_id: number | null;
  failed_step: string | null;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
};

export type IntakeRow = {
  id: number;
  raw_text: string;
  source_note: string | null;
  status: "pending" | "promoted";
  offer_id: number | null;
  created_at: string;
  promoted_at: string | null;
  job: JobRow | null;
};

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

// ADR-014: manually reset a `failed` job back to `queued`. Never automatic —
// the backend rejects this for any job that isn't currently `failed`.
export function retryIntakeJob(intakeId: number): Promise<JobRow> {
  return request(`/api/intake/${intakeId}/retry`, { method: "POST" });
}
