import { describe, expect, it } from "vitest";
import { getZonePositions } from "./scene-layout";

describe("getZonePositions", () => {
  it("returns exactly 5 zones, one per real AgentId", () => {
    const zones = getZonePositions();
    expect(zones).toHaveLength(5);
    expect(zones.map((z) => z.agentId)).toEqual([
      "recruiter",
      "matching",
      "cv",
      "ats",
      "application",
    ]);
  });

  it("increases y monotonically in pipeline order, for stable depth-sort", () => {
    const zones = getZonePositions();
    for (let i = 1; i < zones.length; i++) {
      expect(zones[i].y).toBeGreaterThan(zones[i - 1].y);
    }
  });

  it("increases x monotonically in pipeline order", () => {
    const zones = getZonePositions();
    for (let i = 1; i < zones.length; i++) {
      expect(zones[i].x).toBeGreaterThan(zones[i - 1].x);
    }
  });

  it("is deterministic across calls", () => {
    expect(getZonePositions()).toEqual(getZonePositions());
  });
});
