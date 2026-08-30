import { useEffect, useState } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import { ComingSoon } from "@/layout/ComingSoon";
import { getSettings, type Settings } from "@/api/settings";
import { getCvMasterStatus, type CvMasterStatusResponse } from "@/api/cv-master";
import { ThresholdsCard } from "@/features/settings/ThresholdsCard";
import { WeightsCard } from "@/features/settings/WeightsCard";
import { CvMasterModal } from "@/features/settings/CvMasterModal";
import { PageHeader, type PageHeaderChip } from "@/components/ui/page-header";

export default function SettingsPage() {
  // Single fetch on mount, no polling — config values don't change on a
  // 2-3s timescale, same reasoning as the Analytics page.
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [cvMasterStatus, setCvMasterStatus] = useState<CvMasterStatusResponse | null>(null);
  const [cvMasterModalOpen, setCvMasterModalOpen] = useState(false);

  useEffect(() => {
    getSettings()
      .then(setSettings)
      .catch(() => setLoadError(true));
    getCvMasterStatus()
      .then(setCvMasterStatus)
      .catch(() => setCvMasterStatus(null));
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

  const chips: PageHeaderChip[] = cvMasterStatus
    ? [
        {
          label: "CV Master",
          value: cvMasterStatus.filled
            ? `OK (${cvMasterStatus.content_words} words)`
            : (cvMasterStatus.reason ?? "Not filled"),
          tone: cvMasterStatus.filled ? "success" : "warning",
          onClick: () => setCvMasterModalOpen(true),
        },
      ]
    : [];

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Settings"
        description="Read-only — edit ~/.applyr/applyr.toml to change these."
        chips={chips}
      />

      <ThresholdsCard thresholdApply={settings.threshold_apply} thresholdMaybe={settings.threshold_maybe} />
      <WeightsCard weights={settings.weights} />
      <CvMasterModal open={cvMasterModalOpen} onOpenChange={setCvMasterModalOpen} />
    </div>
  );
}
