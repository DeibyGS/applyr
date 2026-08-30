import { useState } from "react";
import { Link } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogBody, DialogFooter } from "@/components/ui/dialog";
import { AgentLiveTranscript } from "./AgentLiveTranscript";
import { useAgentResponse } from "@/hooks/useAgentResponse";
import type { AgentId, IntakeQueueItem, JobQueueItem } from "./types";

type AgentQueueModalProps = {
  agentId: AgentId;
  agentName: string;
  items: IntakeQueueItem[] | JobQueueItem[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

function isJobItems(items: IntakeQueueItem[] | JobQueueItem[]): items is JobQueueItem[] {
  return items.length === 0 || "offerId" in items[0];
}

export function AgentQueueModal({ agentId, agentName, items, open, onOpenChange }: AgentQueueModalProps) {
  const [response, setResponse] = useState("");
  const { send, sending } = useAgentResponse();
  const jobItems = isJobItems(items) ? items : null;
  const intakeItems = jobItems ? null : (items as IntakeQueueItem[]);

  async function handleSend() {
    if (!response.trim()) return;
    await send(agentId, response);
    setResponse("");
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader className="px-6 pt-6 pb-0">
          <DialogTitle>{agentName}</DialogTitle>
          <DialogDescription>
            {items.length > 0
              ? `${items.length} item${items.length === 1 ? "" : "s"} in queue`
              : "Live activity stream"}
          </DialogDescription>
        </DialogHeader>

        <DialogBody>
          {/* Live transcript */}
          <AgentLiveTranscript agentId={agentId} />

          {/* Queue items */}
          {items.length > 0 && (
            <div className="flex flex-col gap-2 mt-3">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Queue</p>
              <ul className="flex flex-col gap-1" data-agent-id={agentId}>
                {jobItems?.map((item) => (
                  <li key={item.offerId}>
                    {agentId === "application" ? (
                      <div className="flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm ring-1 ring-foreground/10 transition-colors hover:bg-muted">
                        <span className="flex flex-col">
                          <span className="font-medium text-foreground">{item.company}</span>
                          <span className="text-muted-foreground">{item.title}</span>
                        </span>
                        <Badge variant="outline">{item.compatibilityPct}%</Badge>
                      </div>
                    ) : (
                      <Link
                        to={`/offers?jobId=${item.offerId}`}
                        onClick={() => onOpenChange(false)}
                        className="flex items-center justify-between gap-3 rounded-lg px-3 py-2 text-sm ring-1 ring-foreground/10 transition-colors hover:bg-muted"
                      >
                        <span className="flex flex-col">
                          <span className="font-medium text-foreground">{item.company}</span>
                          <span className="text-muted-foreground">{item.title}</span>
                        </span>
                        <Badge variant="outline">{item.compatibilityPct}%</Badge>
                      </Link>
                    )}
                  </li>
                ))}
                {intakeItems?.map((item) => (
                  <li
                    key={item.intakeId}
                    className="rounded-lg px-3 py-2 text-sm text-muted-foreground ring-1 ring-foreground/10"
                  >
                    {item.preview}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </DialogBody>

        {/* Response input */}
        <DialogFooter className="border-t border-border">
          <div className="flex items-center gap-2 w-full">
            <Input
              value={response}
              onChange={(e) => setResponse(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a response..."
              className="flex-1"
            />
            <Button
              type="button"
              size="sm"
              disabled={!response.trim() || sending}
              onClick={handleSend}
            >
              {sending ? "..." : "Send"}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
