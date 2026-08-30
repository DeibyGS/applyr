import { useState, useCallback } from "react";
import { respondToAgent } from "@/api/agent-response";
import type { AgentId } from "@/features/agents/types";

export function useAgentResponse() {
  const [sending, setSending] = useState(false);

  const send = useCallback(async (agentId: AgentId, message: string, correlationId?: string) => {
    if (!message.trim()) return;
    setSending(true);
    try {
      await respondToAgent(agentId, message.trim(), correlationId);
    } catch (err) {
      console.error("[useAgentResponse] Failed to send:", err);
    } finally {
      setSending(false);
    }
  }, []);

  return { send, sending };
}
