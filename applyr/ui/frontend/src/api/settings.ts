import { request } from "./client";

export type CvMasterStatus = "ok" | "warning";

export type Settings = {
  threshold_apply: number;
  threshold_maybe: number;
  weights: Record<string, number>;
  cv_master_status: CvMasterStatus;
  cv_master_message: string;
};

export function getSettings(): Promise<Settings> {
  return request("/api/settings");
}
