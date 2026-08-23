import { describe, expect, it } from "vitest";
import type { JobSummary } from "@/api/jobs";
import { filterInProcess } from "./filter-in-process";

function makeJob(overrides: Partial<JobSummary> = {}): JobSummary {
  return {
    id: 1,
    title: "Test",
    company: "Acme",
    status: "pending",
    compatibility_pct: 50,
    work_mode: "remote",
    location: null,
    seniority_level: null,
    role_category: null,
    created_at: "2026-01-01T00:00:00Z",
    date_applied: null,
    ...overrides,
  };
}

describe("filterInProcess", () => {
  it("keeps only offers with status == 'in_process'", () => {
    const jobs = [
      makeJob({ id: 1, status: "in_process" }),
      makeJob({ id: 2, status: "applied" }),
      makeJob({ id: 3, status: "in_process" }),
      makeJob({ id: 4, status: "waiting" }),
    ];
    expect(filterInProcess(jobs).map((j) => j.id)).toEqual([1, 3]);
  });

  it("preserves the input order (no re-sort)", () => {
    const jobs = [
      makeJob({ id: 5, status: "in_process" }),
      makeJob({ id: 2, status: "in_process" }),
      makeJob({ id: 8, status: "in_process" }),
    ];
    expect(filterInProcess(jobs).map((j) => j.id)).toEqual([5, 2, 8]);
  });

  it("returns an empty array when nothing is in_process", () => {
    const jobs = [makeJob({ status: "pending" }), makeJob({ status: "offer" })];
    expect(filterInProcess(jobs)).toEqual([]);
  });

  it("returns an empty array for an empty input", () => {
    expect(filterInProcess([])).toEqual([]);
  });
});
