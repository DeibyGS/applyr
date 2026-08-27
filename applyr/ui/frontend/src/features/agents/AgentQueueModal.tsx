import { Link } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
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
  const jobItems = isJobItems(items) ? items : null;
  const intakeItems = jobItems ? null : (items as IntakeQueueItem[]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{agentName} queue</DialogTitle>
          <DialogDescription>
            {items.length} item{items.length === 1 ? "" : "s"} waiting
          </DialogDescription>
        </DialogHeader>

        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing here right now.</p>
        ) : (
          <ul className="flex flex-col gap-2 overflow-y-auto" data-agent-id={agentId}>
            {jobItems?.map((item) => (
              <li key={item.offerId}>
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
        )}
      </DialogContent>
    </Dialog>
  );
}
