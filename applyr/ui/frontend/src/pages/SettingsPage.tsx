import { Settings } from "lucide-react";
import { ComingSoon } from "@/layout/ComingSoon";

export default function SettingsPage() {
  return (
    <ComingSoon
      title="Settings"
      message="Viewing and editing your thresholds here is coming in a future update."
      icon={Settings}
    />
  );
}
