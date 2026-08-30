import { IntakeForm } from "@/features/intake/IntakeForm";
import { PendingIntakeList } from "@/features/intake/PendingIntakeList";
import type { IntakeRow } from "@/api/intake";

type IntakeSectionProps = {
  rows: IntakeRow[];
  onCreated: () => void;
};

export function IntakeSection({ rows, onCreated }: IntakeSectionProps) {
  return (
    <div className="flex flex-col gap-3">
      <IntakeForm onCreated={onCreated} />
      <PendingIntakeList rows={rows} />
    </div>
  );
}
