import { useEffect, useState } from "react";
import { getConfig, type Thresholds } from "@/api/config";

const DEFAULT_THRESHOLDS: Thresholds = { threshold_apply: 80, threshold_maybe: 60 };

export function useThresholds(): Thresholds {
  const [thresholds, setThresholds] = useState<Thresholds>(DEFAULT_THRESHOLDS);

  useEffect(() => {
    getConfig()
      .then(setThresholds)
      .catch(() => setThresholds(DEFAULT_THRESHOLDS));
  }, []);

  return thresholds;
}
