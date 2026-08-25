/**
 * Adversarial verification of the frontend movement-rendering contract
 * (specs/visual-ui-applyr-world-phase2/spec.md):
 *
 *   "Given an offer whose pipeline_stage DIFFERS from its last-known value,
 *   When an SSE event for that offer arrives while the Office page is open,
 *   Then the offer's sprite shall visibly tween ..."
 *
 * The condition is explicit: a tween is contracted only for an event that
 * changes the stage. `applyEvent` in pipeline-sprites.ts never checks that —
 * it unconditionally kills any existing tween, overwrites `existing.stage`,
 * and starts a new `tweenPosition()` call regardless of whether `nextStage`
 * equals the offer's current stage.
 *
 * This isn't a hypothetical: the backend's own `update <id> applied` call
 * site (applyr/commands/core.py) calls `notify_stage(offer_id, "application")`
 * unconditionally whenever status becomes "applied" — including when the
 * offer already reached "application" via `cv pdf` and this call is only
 * "refreshing pipeline_stage_at" per the spec's own wording for that event.
 * That refresh event reaches this exact frontend code as a same-stage
 * SSE payload.
 *
 * Reuses the mocking pattern already established in pipeline-sprites.test.ts
 * (mock pixi.js Graphics/Text, mock gsap.to to observe animation calls).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

class MockGraphics {
  static instances: MockGraphics[] = [];
  x = 0;
  y = 0;
  visible = true;
  clear = vi.fn(function (this: MockGraphics) {
    return this;
  });
  circle = vi.fn(function (this: MockGraphics) {
    return this;
  });
  fill = vi.fn(function (this: MockGraphics) {
    return this;
  });
  destroy = vi.fn();

  constructor() {
    MockGraphics.instances.push(this);
  }
}

class MockText {
  static instances: MockText[] = [];
  text: string;
  x = 0;
  y = 0;
  destroy = vi.fn();

  constructor({ text }: { text: string }) {
    this.text = text;
    MockText.instances.push(this);
  }
}

vi.mock("pixi.js", () => ({ Graphics: MockGraphics, Text: MockText }));

const gsapToMock = vi.fn((_target: unknown, _vars: Record<string, unknown>) => ({ kill: vi.fn() }));
vi.mock("gsap", () => ({ gsap: { to: gsapToMock } }));

const { createPipelineSpriteManager } = await import("./pipeline-sprites");

// Real getZonePositions() values (scene-layout.ts): ORIGIN_X=120, ORIGIN_Y=60,
// step = TILE_WIDTH/2=80, TILE_HEIGHT/2=40. index: recruiter=0, matching=1,
// cv=2, ats=3, application=4.
const APPLICATION_ZONE = { x: 120 + 4 * 80, y: 60 + 4 * 40 }; // {440, 220}
const REST_OFFSET_Y = 28;

function fakeContainer() {
  const children: unknown[] = [];
  return {
    children,
    addChild: vi.fn((child: unknown) => children.push(child)),
    removeChild: vi.fn((child: unknown) => {
      const index = children.indexOf(child);
      if (index >= 0) children.splice(index, 1);
    }),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  MockGraphics.instances = [];
  MockText.instances = [];
});

describe("applyEvent — same-stage event (no real transition)", () => {
  it("does NOT animate a sprite when the incoming stage equals its current stage", () => {
    const container = fakeContainer();
    const manager = createPipelineSpriteManager(container as never);
    manager.setInitial([{ offerId: 1, stage: "application" }]);

    // Mirrors `applyr update <id> applied` re-notifying "application" on an
    // offer that already reached it via `cv pdf` — a real, spec-documented
    // "refresh pipeline_stage_at, not a new zone" event, not a malformed one.
    manager.applyEvent({ offer_id: 1, stage: "application", pipeline_stage_at: "2026-08-25T00:00:00Z" });

    expect(gsapToMock).not.toHaveBeenCalled();
  });

  it("does not drop the offer out of its resting zone's slot layout for a same-stage event", () => {
    const container = fakeContainer();
    const manager = createPipelineSpriteManager(container as never);
    manager.setInitial([
      { offerId: 1, stage: "application" },
      { offerId: 2, stage: "application" },
    ]);
    const offer2Graphics = MockGraphics.instances[1];
    expect(offer2Graphics.x).toBe(APPLICATION_ZONE.x + 16); // slot 1, behind offer 1

    manager.applyEvent({ offer_id: 1, stage: "application", pipeline_stage_at: "2026-08-25T00:00:00Z" });

    // If applyEvent wrongly starts a tween for offer 1 (same stage), offer 1
    // gets excluded from recomputeLayout()'s "resting" set (tween !== null)
    // and offer 2 gets incorrectly re-slotted into slot 0 mid-flight, then
    // has to shuffle back to slot 1 once offer 1 "lands" a moment later —
    // a visible, spurious reshuffle for an event that changed nothing.
    expect(offer2Graphics.x).toBe(APPLICATION_ZONE.x + 16);
  });
});
