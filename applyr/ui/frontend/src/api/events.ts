import { API_BASE } from "./client";

/**
 * A real pipeline-stage transition (ADR-013). "recruiter" is deliberately
 * absent — that zone still derives its state from ui_intake, not from a
 * pushed event (Phase 1's agent-status.ts).
 */
export type PipelineStageEvent = {
  offer_id: number;
  stage: "matching" | "cv" | "ats" | "application";
  /** Stamped by the backend at broadcast time (ISO 8601) — informational
   * only, not guaranteed to match the DB row's stored pipeline_stage_at to
   * the second. Unused by the scene today; not every consumer needs it. */
  pipeline_stage_at: string;
};

/**
 * Subscribes to GET /api/events (Server-Sent Events). Receive-only by
 * design — the browser's native EventSource reconnects automatically on
 * drop, so no hand-written retry logic here (ADR-013's reason for choosing
 * SSE over WebSocket in the first place).
 *
 * Returns an unsubscribe function that closes the connection — call it from
 * a React effect's cleanup so the scene never leaks a connection across
 * remounts.
 */
export function subscribeToPipelineEvents(onEvent: (event: PipelineStageEvent) => void): () => void {
  const source = new EventSource(`${API_BASE}/api/events`);

  source.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data) as PipelineStageEvent);
    } catch {
      // A malformed payload must never crash the scene — drop it silently,
      // same "never let this optional visualization break anything real"
      // principle the CLI's notify_stage() follows on the other end.
    }
  };

  return () => source.close();
}
