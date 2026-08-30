import { request } from "./client";

export type CvMasterStatusResponse = {
  filled: boolean;
  content_words: number;
  reason: string | null;
};

export type CvMasterContentResponse = {
  content: string;
};

export function getCvMasterStatus(): Promise<CvMasterStatusResponse> {
  return request("/api/cv-master");
}

// 404 (file missing) surfaces as a thrown ApiError — caller (CvMasterModal) handles it.
export function getCvMasterContent(): Promise<CvMasterContentResponse> {
  return request("/api/cv-master/content");
}
