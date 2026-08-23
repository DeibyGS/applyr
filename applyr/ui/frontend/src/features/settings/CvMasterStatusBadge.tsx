import { CheckCircle2, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { CvMasterStatus } from "@/api/settings";

export function CvMasterStatusBadge({
  status,
  message,
}: {
  status: CvMasterStatus;
  message: string;
}) {
  const isOk = status === "ok";

  return (
    <Card>
      <CardHeader>
        <CardTitle>CV Master</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2">
          {/* Icon + text label alongside the color — status color never carries
              meaning alone (dataviz skill's status-color rule). */}
          <Badge className={isOk ? "bg-success text-background" : "bg-warning text-background"}>
            {isOk ? <CheckCircle2 /> : <AlertTriangle />}
            {isOk ? "OK" : "Warning"}
          </Badge>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
      </CardContent>
    </Card>
  );
}
