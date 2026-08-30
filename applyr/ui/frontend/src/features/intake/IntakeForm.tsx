import { useState, type FormEvent } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { createIntake } from "@/api/intake";

export function IntakeForm({ onCreated }: { onCreated: () => void }) {
  const [rawText, setRawText] = useState("");
  const [sourceNote, setSourceNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createIntake(rawText, sourceNote);
      setRawText("");
      setSourceNote("");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <Textarea
        value={rawText}
        onChange={(event) => setRawText(event.target.value)}
        placeholder="Paste the full job offer text here..."
        rows={5}
        required
      />
      <Input
        value={sourceNote}
        onChange={(event) => setSourceNote(event.target.value)}
        placeholder="Source (optional, e.g. LinkedIn)"
      />
      <Button type="submit" disabled={submitting || !rawText.trim()} className="w-fit">
        {submitting ? "Saving..." : "Add to pending"}
      </Button>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </form>
  );
}
