import { useEffect, useState } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import { ComingSoon } from "@/layout/ComingSoon";
import { getSettings, type Settings } from "@/api/settings";
import { ThresholdsCard } from "@/features/settings/ThresholdsCard";
import { WeightsCard } from "@/features/settings/WeightsCard";
import { CvMasterStatusBadge } from "@/features/settings/CvMasterStatusBadge";

export default function SettingsPage() {
  // Single fetch on mount, no polling — config values don't change on a
  // 2-3s timescale, same reasoning as the Analytics page.
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    getSettings()
      .then(setSettings)
      .catch(() => setLoadError(true));
  }, []);

  if (loadError) {
    return (
      <ComingSoon
        title="Settings"
        message="Could not load settings. Is the applyr backend running?"
        icon={SettingsIcon}
      />
    );
  }

  if (settings === null) {
    return null;
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <h1 className="font-display text-2xl font-medium text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Read-only — edit ~/.applyr/applyr.toml to change these.
        </p>
      </header>

      <ThresholdsCard thresholdApply={settings.threshold_apply} thresholdMaybe={settings.threshold_maybe} />
      <WeightsCard weights={settings.weights} />
      <CvMasterStatusBadge status={settings.cv_master_status} message={settings.cv_master_message} />
    </div>
  );
}
