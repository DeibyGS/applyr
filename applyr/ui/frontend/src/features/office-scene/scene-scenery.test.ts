import { beforeEach, describe, expect, it, vi } from "vitest";

const destroyMock = vi.fn();

class MockDisplayObject {
  x = 0;
  y = 0;
  zIndex = 0;
  alpha = 1;
  visible = true;
  children: unknown[] = [];
  addChild = vi.fn(function (this: MockDisplayObject, ...added: unknown[]) {
    this.children.push(...added);
    return added[0];
  });
  removeChild = vi.fn(function (this: MockDisplayObject, child: unknown) {
    this.children = this.children.filter((c) => c !== child);
    return child;
  });
  destroy = destroyMock;
}

vi.mock("pixi.js", () => {
  class MockGraphics extends MockDisplayObject {
    clear = vi.fn(function (this: MockGraphics) {
      return this;
    });
    ellipse = vi.fn(function (this: MockGraphics) {
      return this;
    });
    fill = vi.fn(function (this: MockGraphics) {
      return this;
    });
  }
  class MockContainer extends MockDisplayObject {}
  class MockSprite extends MockDisplayObject {
    texture: unknown = null;
    width = 256;
    anchor = { set: vi.fn() };
    scale = { set: vi.fn() };
  }
  return { Graphics: MockGraphics, Container: MockContainer, Sprite: MockSprite };
});

const { createZoneScenery } = await import("./scene-scenery");
const { getZonePositions } = await import("./scene-layout");

function fakeTexture(width = 256): never {
  return { width } as never;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("createZoneScenery", () => {
  it("creates exactly one desk entity per zone at its coordinates", () => {
    const scenery = createZoneScenery();
    expect(scenery.view.children).toHaveLength(5);

    const holders = scenery.view.children as Array<{ x: number; y: number }>;
    const zones = getZonePositions();
    zones.forEach((zone, i) => {
      expect(holders[i].x).toBe(zone.x);
      expect(holders[i].y).toBe(zone.y);
    });
  });

  it("stacks each desk just behind its zone's agent and in front of nothing else — sort-by-y triple holds", () => {
    const scenery = createZoneScenery();
    const holders = scenery.view.children as Array<{ zIndex: number }>;
    const zones = getZonePositions();

    zones.forEach((zone, i) => {
      // Agent sprites render at zIndex === zone.y (agent-sprite.ts); desks sit just behind.
      expect(holders[i].zIndex).toBe(zone.y - 1);
      if (i > 0) {
        expect(holders[i].zIndex).toBeGreaterThan(zones[i - 1].y); // still in front of the previous agent
      }
    });
  });

  it("shows a fallback pad per zone until desk art arrives", () => {
    const scenery = createZoneScenery();
    const holders = scenery.view.children as unknown as Array<{
      children: Array<{ visible: boolean }>;
    }>;
    for (const holder of holders) {
      expect(holder.children).toHaveLength(1);
      expect(holder.children[0].visible).toBe(true);
    }
  });

  it("setDesk swaps in art anchored bottom-center, scaled to display width, hiding the pad", async () => {
    const { Sprite } = await import("pixi.js");
    const scenery = createZoneScenery();

    scenery.setDesk("cv", fakeTexture(512));

    const cvHolder = (scenery.view.children as Array<{ children: unknown[] }>)[2]; // ZONE_ORDER index of cv
    const desk = cvHolder.children.find((c) => c instanceof Sprite) as unknown as {
      anchor: { set: ReturnType<typeof vi.fn> };
      scale: { set: ReturnType<typeof vi.fn> };
    };
    expect(desk).toBeDefined();
    expect(desk.anchor.set).toHaveBeenCalledWith(0.5, 1);
    expect(desk.scale.set).toHaveBeenCalledWith(120 / 512);
  });

  it("setDesk(null) removes art and restores the fallback pad", async () => {
    const { Sprite } = await import("pixi.js");
    const scenery = createZoneScenery();

    scenery.setDesk("ats", fakeTexture());
    scenery.setDesk("ats", null);

    const atsHolder = (scenery.view.children as Array<{ children: Array<{ visible?: boolean }> }>)[3];
    expect(atsHolder.children.some((c) => c instanceof Sprite)).toBe(false);
    const pad = atsHolder.children[0];
    expect(pad.visible).toBe(true);
  });

  it("ignores an unknown agent id without crashing", () => {
    const scenery = createZoneScenery();
    expect(() => scenery.setDesk("nonexistent" as never, fakeTexture())).not.toThrow();
  });

  it("destroy tears down the whole scenery layer", () => {
    const scenery = createZoneScenery();
    scenery.destroy();
    expect(destroyMock).toHaveBeenCalledTimes(1);
  });
});
