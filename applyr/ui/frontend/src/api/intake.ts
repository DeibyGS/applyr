import { request } from "./client";

export type IntakeRow = {
  id: number;
  raw_text: string;
  source_note: string | null;
  status: "pending" | "promoted";
  offer_id: number | null;
  created_at: string;
  promoted_at: string | null;
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
