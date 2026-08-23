import { describe, expect, it } from "vitest";
import type { JobSummary } from "@/api/jobs";
import { groupByStatus, OFFER_STATUSES } from "./group-by-status";

function job(overrides: Partial<JobSummary> = {}): JobSummary {
  return {
    id: 1,
    title: "Backend Dev",
    company: "Acme",
    status: "pending",
    compatibility_pct: 80,
    work_mode: null,
    location: null,
    seniority_level: null,
    role_category: null,
    created_at: "2026-08-23 10:00:00",
    date_applied: null,
    ...overrides,
  };
}

describe("groupByStatus", () => {
  it("mirrors applyr's real VALID_STATUSES exactly (applyr/db.py) — a tripwire for drift", () => {
    expect(OFFER_STATUSES).toEqual([
      "pending",
      "applied",
      "waiting",
      "in_process",
      "rejected",
      "discarded",
      "offer",
    ]);
  });

  it("returns all 7 sections even with zero offers", () => {
    const grouped = groupByStatus([]);
    expect(Object.keys(grouped)).toEqual([...OFFER_STATUSES]);
    for (const status of OFFER_STATUSES) {
      expect(grouped[status]).toEqual([]);
    }
  });

  it("groups offers into their real status section", () => {
    const jobs = [
      job({ id: 1, status: "pending" }),
      job({ id: 2, status: "applied" }),
      job({ id: 3, status: "applied" }),
      job({ id: 4, status: "offer" }),
    ];
    const grouped = groupByStatus(jobs);
    expect(grouped.pending.map((j) => j.id)).toEqual([1]);
    expect(grouped.applied.map((j) => j.id)).toEqual([2, 3]);
    expect(grouped.offer.map((j) => j.id)).toEqual([4]);
    expect(grouped.waiting).toEqual([]);
    expect(grouped.in_process).toEqual([]);
    expect(grouped.rejected).toEqual([]);
    expect(grouped.discarded).toEqual([]);
  });
});
