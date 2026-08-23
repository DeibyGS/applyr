import { describe, expect, it } from "vitest";
import type { Funnel, FunnelPct, TrendEntry } from "@/api/analytics";
import { breakdownEntries, funnelStages, trendChartData } from "./analytics-data";

describe("funnelStages", () => {
  it("orders stages applied -> responded -> interview -> offer with backend-computed percentages", () => {
    const funnel: Funnel = { applied: 10, responded: 5, interview: 2, offer: 1 };
    const funnel_pct: FunnelPct = { applied: 100, responded: 50, interview: 40, offer: 50 };
    const stages = funnelStages({ funnel, funnel_pct });

    expect(stages.map((s) => s.key)).toEqual(["applied", "responded", "interview", "offer"]);
    expect(stages[1]).toEqual({ key: "responded", label: "Responded", count: 5, pct: 50 });
  });

  it("passes through null percentages untouched (never re-derives them)", () => {
    const funnel: Funnel = { applied: 0, responded: 0, interview: 0, offer: 0 };
    const funnel_pct: FunnelPct = { applied: null, responded: null, interview: null, offer: null };
    const stages = funnelStages({ funnel, funnel_pct });

    expect(stages.every((s) => s.pct === null)).toBe(true);
  });
});

describe("breakdownEntries", () => {
  it("sorts by count descending regardless of input key order", () => {
    const result = breakdownEntries({ referral: 1, linkedin_easy: 5, email: 3 });
    expect(result).toEqual([
      { key: "linkedin_easy", count: 5 },
      { key: "email", count: 3 },
      { key: "referral", count: 1 },
    ]);
  });

  it("returns an empty array for an empty record", () => {
    expect(breakdownEntries({})).toEqual([]);
  });
});

describe("trendChartData", () => {
  it("reverses newest-first backend order into chronological ascending order", () => {
    const entries: TrendEntry[] = [
      { period: "2026-W34", count: 5, growth_pct: 25 },
      { period: "2026-W33", count: 4, growth_pct: null },
    ];
    const result = trendChartData(entries);
    expect(result.map((p) => p.period)).toEqual(["2026-W33", "2026-W34"]);
    expect(result[1]).toEqual({ period: "2026-W34", count: 5, growthPct: 25 });
  });

  it("returns an empty array for empty input", () => {
    expect(trendChartData([])).toEqual([]);
  });
});
