import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogBody, DialogFooter } from "@/components/ui/dialog";
import { Inbox } from "lucide-react";
import { IntakeForm } from "@/features/intake/IntakeForm";
import { PendingIntakeList } from "@/features/intake/PendingIntakeList";
import type { IntakeRow } from "@/api/intake";

export function IntakePanel({ rows, onCreated }: { rows: IntakeRow[]; onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const buttonText = rows.length > 0 ? `Paste offer (${rows.length})` : "Paste offer";

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-20 gap-2 bg-card shadow-lg"
      >
        <Inbox className="h-4 w-4" />
        {buttonText}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader className="px-6 pt-6 pb-0">
            <DialogTitle>Paste a job offer</DialogTitle>
            <DialogDescription>Paste the full job offer text and optionally add a source.</DialogDescription>
          </DialogHeader>
          <DialogBody>
            <IntakeForm onCreated={() => { onCreated(); setOpen(false); }} />
            {rows.length > 0 && <PendingIntakeList rows={rows} />}
          </DialogBody>
        </DialogContent>
      </Dialog>
    </>
  );
}
