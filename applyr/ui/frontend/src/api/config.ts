import { request } from "./client";

export type Thresholds = {
  threshold_apply: number;
  threshold_maybe: number;
};

export function getConfig(): Promise<Thresholds> {
  return request("/api/config");
}
