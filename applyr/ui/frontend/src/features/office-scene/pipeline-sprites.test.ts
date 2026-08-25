import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PipelineStageEvent } from "@/api/events";

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
const CV_ZONE = { x: 120 + 2 * 80, y: 60 + 2 * 40 }; // {280, 140}
const MATCHING_ZONE = { x: 120 + 1 * 80, y: 60 + 1 * 40 }; // {200, 100}
const REST_OFFSET_Y = 28;
const SLOT_OFFSET_X = 16;

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

describe("setInitial", () => {
  it("places a single offer directly at its zone's rest position, with no animation", () => {
    const container = fakeContainer();
    const manager = createPipelineSpriteManager(container as never);

    manager.setInitial([{ offerId: 1, stage: "cv" }]);

    expect(MockGraphics.instances).toHaveLength(1);
    expect(MockGraphics.instances[0].x).toBe(CV_ZONE.x);
    expect(MockGraphics.instances[0].y).toBe(CV_ZONE.y + REST_OFFSET_Y);
    expect(container.addChild).toHaveBeenCalledWith(MockGraphics.instances[0]);
    expect(gsapToMock).not.toHaveBeenCalled();
  });

  it("slots multiple offers resting in the same zone by ascending offerId, not insertion order", () => {
    const container = fakeContainer();
    const manager = createPipelineSpriteManager(container as never);

    // offerId 3 created first, offerId 1 second — but slotting sorts by id.
    manager.setInitial([
      { offerId: 3, stage: "cv" },
      { offerId: 1, stage: "cv" },
    ]);

    const [graphicsForOffer3, graphicsForOffer1] = MockGraphics.instances;
    expect(graphicsForOffer1.x).toBe(CV_ZONE.x); // slot 0
    expect(graphicsForOffer3.x).toBe(CV_ZONE.x + SLOT_OFFSET_X); // slot 1
  });

  it("caps visible sprites per zone and shows a +N badge for the overflow", () => {
    const container = fakeContainer();
    const manager = createPipelineSpriteManager(container as never);

    manager.setInitial(
      Array.from({ length: 6 }, (_, i) => ({ offerId: i + 1, stage: "matching" as const }))
    );

    const visibleCount = MockGraphics.instances.filter((g) => g.visible).length;
    expect(visibleCount).toBe(5);
    expect(MockGraphics.instances[5].visible).toBe(false); // 6th offer (id 6) is the overflow

    expect(MockText.instances).toHaveLength(1);
    expect(MockText.instances[0].text).toBe("+1");
    expect(MockText.instances[0].x).toBe(MATCHING_ZONE.x + 5 * SLOT_OFFSET_X);
  });
});

describe("applyEvent", () => {
  it("places a never-seen offer directly at the target zone, with no animation", () => {
    const container = fakeContainer();
    const manager = createPipelineSpriteManager(container as never);

    manager.applyEvent({ offer_id: 1, stage: "matching", pipeline_stage_at: "2026-08-25T00:00:00Z" });

    expect(MockGraphics.instances).toHaveLength(1);
    expect(MockGraphics.instances[0].x).toBe(MATCHING_ZONE.x);
    expect(gsapToMock).not.toHaveBeenCalled();
  });

  it("tweens an already-tracked offer's sprite toward the new zone", () => {
    const container = fakeContainer();
    const manager = createPipelineSpriteManager(container as never);
    manager.setInitial([{ offerId: 1, stage: "matching" }]);

    manager.applyEvent({ offer_id: 1, stage: "cv", pipeline_stage_at: "2026-08-25T00:00:00Z" });

    expect(gsapToMock).toHaveBeenCalledTimes(1);
    expect(gsapToMock).toHaveBeenCalledWith(
      MockGraphics.instances[0],
      expect.objectContaining({ x: CV_ZONE.x, y: CV_ZONE.y + REST_OFFSET_Y })
    );
  });

  it("excludes a mid-flight offer from its old zone's slot layout immediately", () => {
    const container = fakeContainer();
    const manager = createPipelineSpriteManager(container as never);
    manager.setInitial([
      { offerId: 1, stage: "matching" },
      { offerId: 2, stage: "matching" },
    ]);
    const offer2Graphics = MockGraphics.instances[1];
    expect(offer2Graphics.x).toBe(MATCHING_ZONE.x + SLOT_OFFSET_X); // slot 1, behind offer 1

    manager.applyEvent({ offer_id: 1, stage: "cv", pipeline_stage_at: "2026-08-25T00:00:00Z" }); // offer 1 leaves — mid-flight, not yet in "cv"

    // Offer 2 must have been re-slotted into slot 0 of "matching" now that
    // offer 1 no longer occupies it.
    expect(offer2Graphics.x).toBe(MATCHING_ZONE.x);
  });

  it("re-slots the sprite into its new zone once the tween completes", () => {
    let onComplete: (() => void) | undefined;
    gsapToMock.mockImplementationOnce((target, vars) => {
      onComplete = vars.onComplete as (() => void) | undefined;
      // A real gsap tween leaves the target's x/y at the given values once
      // it completes — this mock only records the call otherwise, so this
      // test simulates that end state explicitly.
      (target as { x: number; y: number }).x = vars.x as number;
      (target as { x: number; y: number }).y = vars.y as number;
      return { kill: vi.fn() };
    });

    const container = fakeContainer();
    const manager = createPipelineSpriteManager(container as never);
    manager.setInitial([{ offerId: 1, stage: "matching" }]);
    manager.applyEvent({ offer_id: 1, stage: "cv", pipeline_stage_at: "2026-08-25T00:00:00Z" });

    onComplete?.();

    expect(MockGraphics.instances[0].x).toBe(CV_ZONE.x); // slot 0 of "cv", now at rest
  });

  it("kills the in-flight tween if a second event arrives before the first completes", () => {
    const firstTween = { kill: vi.fn() };
    gsapToMock.mockReturnValueOnce(firstTween);

    const container = fakeContainer();
    const manager = createPipelineSpriteManager(container as never);
    manager.setInitial([{ offerId: 1, stage: "matching" }]);
    manager.applyEvent({ offer_id: 1, stage: "cv", pipeline_stage_at: "2026-08-25T00:00:00Z" });
    manager.applyEvent({ offer_id: 1, stage: "ats", pipeline_stage_at: "2026-08-25T00:00:00Z" });

    expect(firstTween.kill).toHaveBeenCalledTimes(1);
  });
});

describe("destroy", () => {
  it("kills in-flight tweens and destroys every tracked sprite", () => {
    const activeTween = { kill: vi.fn() };
    gsapToMock.mockReturnValueOnce(activeTween);

    const container = fakeContainer();
    const manager = createPipelineSpriteManager(container as never);
    manager.setInitial([{ offerId: 1, stage: "matching" }]);
    manager.applyEvent({ offer_id: 1, stage: "cv", pipeline_stage_at: "2026-08-25T00:00:00Z" });

    manager.destroy();

    expect(activeTween.kill).toHaveBeenCalledTimes(1);
    expect(MockGraphics.instances[0].destroy).toHaveBeenCalledTimes(1);
  });
});
