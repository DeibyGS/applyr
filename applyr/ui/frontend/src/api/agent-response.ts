import { request } from "./client";

export function respondToAgent(agentId: string, message: string, correlationId?: string): Promise<void> {
  return request("/api/agent-response", {
    method: "POST",
    body: JSON.stringify({
      agent_id: agentId,
      message,
      correlation_id: correlationId || null,
    }),
  });
}
