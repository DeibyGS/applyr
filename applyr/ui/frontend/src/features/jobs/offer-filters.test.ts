import { describe, expect, it } from "vitest";
import type { JobSummary } from "@/api/jobs";
import { DEFAULT_FILTERS, filterJobs, nextSortState, sortJobs } from "./offer-filters";

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

describe("filterJobs", () => {
  it("returns every job when filters are the defaults", () => {
    const jobs = [makeJob({ id: 1 }), makeJob({ id: 2 })];
    expect(filterJobs(jobs, DEFAULT_FILTERS)).toHaveLength(2);
  });

  it("filters by exact status", () => {
    const jobs = [makeJob({ id: 1, status: "pending" }), makeJob({ id: 2, status: "applied" })];
    const result = filterJobs(jobs, { ...DEFAULT_FILTERS, status: "applied" });
    expect(result.map((j) => j.id)).toEqual([2]);
  });

  it("filters by exact work_mode", () => {
    const jobs = [makeJob({ id: 1, work_mode: "remote" }), makeJob({ id: 2, work_mode: "onsite" })];
    const result = filterJobs(jobs, { ...DEFAULT_FILTERS, workMode: "onsite" });
    expect(result.map((j) => j.id)).toEqual([2]);
  });

  it("filters by minimum score, inclusive", () => {
    const jobs = [makeJob({ id: 1, compatibility_pct: 60 }), makeJob({ id: 2, compatibility_pct: 80 })];
    const result = filterJobs(jobs, { ...DEFAULT_FILTERS, minScore: 80 });
    expect(result.map((j) => j.id)).toEqual([2]);
  });

  it("combines active filters with AND logic", () => {
    const jobs = [
      makeJob({ id: 1, status: "applied", work_mode: "remote", compatibility_pct: 90 }),
      makeJob({ id: 2, status: "applied", work_mode: "onsite", compatibility_pct: 90 }),
      makeJob({ id: 3, status: "pending", work_mode: "remote", compatibility_pct: 90 }),
    ];
    const result = filterJobs(jobs, { status: "applied", workMode: "remote", minScore: 50 });
    expect(result.map((j) => j.id)).toEqual([1]);
  });
});

describe("sortJobs", () => {
  const older = makeJob({ id: 1, created_at: "2026-01-01T00:00:00Z", compatibility_pct: 40 });
  const newer = makeJob({ id: 2, created_at: "2026-02-01T00:00:00Z", compatibility_pct: 90 });

  it("sorts by date descending", () => {
    expect(sortJobs([older, newer], "date", "desc").map((j) => j.id)).toEqual([2, 1]);
  });

  it("sorts by date ascending", () => {
    expect(sortJobs([older, newer], "date", "asc").map((j) => j.id)).toEqual([1, 2]);
  });

  it("sorts by score descending", () => {
    expect(sortJobs([older, newer], "score", "desc").map((j) => j.id)).toEqual([2, 1]);
  });

  it("sorts by score ascending", () => {
    expect(sortJobs([older, newer], "score", "asc").map((j) => j.id)).toEqual([1, 2]);
  });

  it("does not mutate the input array", () => {
    const jobs = [older, newer];
    sortJobs(jobs, "score", "desc");
    expect(jobs.map((j) => j.id)).toEqual([1, 2]);
  });
});

describe("nextSortState", () => {
  it("reverses direction when the active field is clicked again", () => {
    expect(nextSortState("date", "desc", "date")).toEqual({ field: "date", direction: "asc" });
    expect(nextSortState("date", "asc", "date")).toEqual({ field: "date", direction: "desc" });
  });

  it("switches to the new field defaulting to descending", () => {
    expect(nextSortState("date", "asc", "score")).toEqual({ field: "score", direction: "desc" });
  });
});
