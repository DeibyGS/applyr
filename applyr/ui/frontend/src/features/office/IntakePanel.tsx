import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Inbox } from "lucide-react";
import { IntakeForm } from "@/features/intake/IntakeForm";
import { PendingIntakeList } from "@/features/intake/PendingIntakeList";
import type { IntakeRow } from "@/api/intake";

const PANEL_ID = "office-intake-panel";

export function IntakePanel({ rows, onCreated }: { rows: IntakeRow[]; onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLElement>(null);
  const buttonText = open ? "Close" : rows.length > 0 ? `Paste offer (${rows.length})` : "Paste offer";

  // @types/react 18 doesn't type the `inert` JSX attribute (added in React 19's types) —
  // set it imperatively on the DOM node instead so closed-panel content is untabbable.
  useEffect(() => {
    if (panelRef.current) {
      panelRef.current.inert = !open;
    }
  }, [open]);

  return (
    <div className="pointer-events-none absolute inset-y-0 right-0 z-10 flex">
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-expanded={open}
        aria-controls={PANEL_ID}
        onClick={() => setOpen((value) => !value)}
        className="pointer-events-auto h-fit gap-2 self-start rounded-r-none border-r-0 bg-card"
      >
        <Inbox className="h-4 w-4" />
        {buttonText}
      </Button>
      <section
        id={PANEL_ID}
        ref={panelRef}
        className={`pointer-events-auto flex w-full max-w-sm flex-col gap-3 overflow-y-auto border-l border-border bg-card/95 p-4 backdrop-blur-md transition-transform duration-200 ease-out ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <IntakeForm onCreated={onCreated} />
        <PendingIntakeList rows={rows} />
      </section>
    </div>
  );
}
