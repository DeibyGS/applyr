import { describe, expect, it } from "vitest";
import { getScoreBand } from "./score-color";

describe("getScoreBand", () => {
  const thresholds = { threshold_apply: 65, threshold_maybe: 55 };

  it("returns success at or above threshold_apply", () => {
    expect(getScoreBand(65, thresholds)).toBe("success");
    expect(getScoreBand(90, thresholds)).toBe("success");
  });

  it("returns warning between threshold_maybe and threshold_apply", () => {
    expect(getScoreBand(55, thresholds)).toBe("warning");
    expect(getScoreBand(64, thresholds)).toBe("warning");
  });

  it("returns danger below threshold_maybe", () => {
    expect(getScoreBand(54, thresholds)).toBe("danger");
    expect(getScoreBand(0, thresholds)).toBe("danger");
  });

  it("respects a different user's own configured thresholds, not hardcoded ones", () => {
    const strict = { threshold_apply: 90, threshold_maybe: 80 };
    expect(getScoreBand(85, strict)).toBe("warning");
    expect(getScoreBand(85, thresholds)).toBe("success");
  });
});
