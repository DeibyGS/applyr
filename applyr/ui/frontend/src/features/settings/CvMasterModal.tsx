import { useEffect, useState } from "react";
import Markdown from "markdown-to-jsx";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { getCvMasterContent } from "@/api/cv-master";

type LoadState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; content: string }
  | { status: "error" };

export function CvMasterModal({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [state, setState] = useState<LoadState>({ status: "idle" });

  // Fetch only when the dialog opens, not on Settings page mount — the file
  // can be large and most sessions never open this modal.
  useEffect(() => {
    if (!open) return;
    setState({ status: "loading" });
    getCvMasterContent()
      .then((res) => setState({ status: "loaded", content: res.content }))
      .catch(() => setState({ status: "error" }));
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>CV Master</DialogTitle>
        </DialogHeader>
        <div className="overflow-y-auto">
          {state.status === "loading" && <p className="text-sm text-muted-foreground">Loading...</p>}
          {state.status === "error" && (
            <p className="text-sm text-muted-foreground">
              Could not load ~/.applyr/cv-master.md. It may not exist yet — run{" "}
              <code className="rounded bg-muted px-1 py-0.5">applyr init</code>.
            </p>
          )}
          {state.status === "loaded" && (
            // No @tailwindcss/typography plugin in this project — style markdown
            // elements directly via [&_x] selectors instead of `prose` classes.
            <div className="max-w-none text-sm text-foreground [&_h1]:mt-4 [&_h1]:mb-2 [&_h1]:text-lg [&_h1]:font-display [&_h1]:font-medium [&_h2]:mt-4 [&_h2]:mb-2 [&_h2]:text-base [&_h2]:font-display [&_h2]:font-medium [&_p]:mb-2 [&_ul]:mb-2 [&_ul]:list-disc [&_ul]:pl-5 [&_li]:mb-1 [&_a]:text-primary [&_a]:underline">
              <Markdown>{state.content}</Markdown>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
