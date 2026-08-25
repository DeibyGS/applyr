import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentStatus } from "@/features/agents/types";
import type { ZonePosition } from "./scene-layout";

const destroyMock = vi.fn();

class MockDisplayObject {
  x = 0;
  y = 0;
  zIndex = 0;
  alpha = 1;
  visible = true;
  addChild = vi.fn(function (this: MockDisplayObject, ...added: unknown[]) {
    this.children.push(...added);
    return added[0];
  });
  removeChild = vi.fn(function (this: MockDisplayObject & { children: unknown[] }, child: unknown) {
    this.children = this.children.filter((c) => c !== child);
    return child;
  });
  children: unknown[] = [];
  destroy = destroyMock;
}

vi.mock("pixi.js", () => {
  class MockGraphics extends MockDisplayObject {
    clear = vi.fn(function (this: MockGraphics) {
      return this;
    });
    circle = vi.fn(function (this: MockGraphics) {
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
    height = 100;
    anchor = { set: vi.fn() };
    scale = { set: vi.fn() };
  }
  return { Graphics: MockGraphics, Container: MockContainer, Sprite: MockSprite };
});

const gsapToMock = vi.fn((_target: unknown, _vars: Record<string, unknown>) => ({ kill: vi.fn() }));
vi.mock("gsap", () => ({ gsap: { to: gsapToMock } }));

const { createAgentSprite, STATE_COLORS } = await import(
  "./agent-sprite"
);

const { directionFor, tweenPosition } = await import(
  "./movement-utils"
);

const COLOR_IDLE = STATE_COLORS.idle;
const COLOR_WORKING = STATE_COLORS.working;

/** tweenPosition only needs a position-mutable display object; test doubles
 * (view containers or bare Graphics mocks) satisfy it structurally. */
const asTarget = (obj: unknown): Parameters<typeof tweenPosition>[0] => obj as Parameters<typeof tweenPosition>[0];

const zone: ZonePosition = { agentId: "recruiter", x: 100, y: 50 };

function idle(): AgentStatus {
  return { agentId: "recruiter", state: "idle" };
}
function working(): AgentStatus {
  return { agentId: "recruiter", state: "working", pendingCount: 2 };
}
function cvIdle(): AgentStatus {
  return { agentId: "cv", state: "idle" };
}
function cvWorking(): AgentStatus {
  return { agentId: "cv", state: "working", count: 1 };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("createAgentSprite — layout & fallback parity", () => {
  it("positions the view at the zone's coordinates, holding ring + fallback body", () => {
    const sprite = createAgentSprite(zone, idle());
    expect(sprite.view.x).toBe(100);
    expect(sprite.view.y).toBe(50);
    expect(sprite.view.zIndex).toBe(50);
    expect(sprite.view.children).toHaveLength(2); // ring + placeholder body
    expect(gsapToMock).not.toHaveBeenCalled();
  });

  it("shows the fallback circle until art arrives, and keeps its colors in sync with the ring", () => {
    const sprite = createAgentSprite(zone, idle());
    const [ring, fallback] = sprite.view.children as never as [
      { clear: ReturnType<typeof vi.fn>; ellipse: ReturnType<typeof vi.fn>; fill: ReturnType<typeof vi.fn> },
      { clear: ReturnType<typeof vi.fn>; circle: ReturnType<typeof vi.fn>; fill: ReturnType<typeof vi.fn> },
    ];
    expect(ring.ellipse).toHaveBeenCalledWith(0, 0, expect.any(Number), expect.any(Number));
    expect(ring.fill).toHaveBeenCalledWith(COLOR_IDLE);
    expect(fallback.circle).toHaveBeenCalledWith(0, 0, expect.any(Number));
    expect(fallback.fill).toHaveBeenCalledWith(COLOR_IDLE);

    sprite.update(working());
    expect(ring.fill).toHaveBeenLastCalledWith(COLOR_WORKING);
    expect(fallback.fill).toHaveBeenLastCalledWith(COLOR_WORKING);
  });

  it("does not tween when the new status has the same visual state", () => {
    const sprite = createAgentSprite(zone, idle());
    sprite.update(idle());
    expect(gsapToMock).not.toHaveBeenCalled();
  });

  it("tweens alpha from a dimmed value back to 1 when state actually changes", () => {
    const sprite = createAgentSprite(zone, idle());
    sprite.update(working());

    expect(sprite.view.alpha).toBe(0.35);
    expect(gsapToMock).toHaveBeenCalledTimes(2); // pulse + alpha
    const calls = gsapToMock.mock.calls.map(([, vars]) => vars);
    expect(calls).toContainEqual(expect.objectContaining({ alpha: 1, duration: expect.any(Number) }));
  });

  it("kills the in-flight tweens and starts new ones if state changes again before they finish", () => {
    const kills = [{ kill: vi.fn() }, { kill: vi.fn() }];
    let i = 0;
    gsapToMock.mockImplementation(() => kills[i++ % kills.length]);

    const sprite = createAgentSprite(zone, idle());
    sprite.update(working()); // starts pulse + alpha tween
    gsapToMock.mockClear();
    sprite.update(idle()); // stops pulse, restarts alpha tween

    const killCalls = kills.flatMap((k) => k.kill.mock.calls.length).reduce((a, b) => a + b, 0);
    expect(killCalls).toBeGreaterThanOrEqual(2);
    expect(gsapToMock).toHaveBeenCalled();
  });

  it("does not reset alpha when interrupting a mid-flight tween — continues from the current value", () => {
    const sprite = createAgentSprite(zone, idle());
    sprite.update(working());
    expect(sprite.view.alpha).toBe(0.35); // fresh transition — dims first

    // Simulate the first tween having partially progressed before it's interrupted.
    sprite.view.alpha = 0.7;
    sprite.update(idle());

    expect(sprite.view.alpha).toBe(0.7); // untouched — no flash back to 0.35
  });

  it("resets alpha to a dimmed value again once a prior tween has actually completed", () => {
    // Each transition fires TWO gsap tweens (ring pulse + view alpha); only
    // the alpha one carries onComplete — capture it across all calls.
    const completers: Array<() => void> = [];
    gsapToMock.mockImplementation((_target, vars) => {
      if (typeof vars.onComplete === "function") completers.push(vars.onComplete as () => void);
      return { kill: vi.fn() };
    });

    const sprite = createAgentSprite(zone, idle());
    sprite.update(working());
    expect(completers).toHaveLength(1);
    completers[0](); // alpha tween finishes naturally
    sprite.view.alpha = 1;

    sprite.update(idle());

    expect(sprite.view.alpha).toBe(0.35); // no tween in flight — dims again as a fresh transition
  });

  it("treats cv/ats/application zones the same as recruiter/matching — ADR-013 gave them real backing data too", () => {
    const sprite = createAgentSprite(zone, cvIdle());
    sprite.update(cvWorking());
    expect(gsapToMock).toHaveBeenCalled();
  });

  it("destroy() kills any active tween and destroys the view", () => {
    const activeTween = { kill: vi.fn() };
    gsapToMock.mockReturnValueOnce(activeTween);

    const sprite = createAgentSprite(zone, idle());
    sprite.update(working());
    sprite.destroy();

    expect(activeTween.kill).toHaveBeenCalledTimes(1);
    expect(destroyMock).toHaveBeenCalledTimes(1);
  });
});

describe("createAgentSprite — working-state pulse", () => {
  it("starts a bounded repeating pulse on the ring while working", () => {
    const sprite = createAgentSprite(zone, idle());
    sprite.update(working());

    const pulses = gsapToMock.mock.calls.filter(([, vars]) => (vars as { repeat?: number }).repeat === -1);
    expect(pulses).toHaveLength(1);
    const vars = pulses[0][1] as { yoyo: boolean; alpha: number; ease: string };
    expect(vars.yoyo).toBe(true);
    expect(vars.alpha).toBeLessThan(1);
  });

  it("keeps the ring static when idle — pulse killed and alpha restored", () => {
    const pulse = { kill: vi.fn() };
    gsapToMock.mockImplementation((_target, vars) =>
      (vars as { repeat?: number }).repeat === -1 ? pulse : { kill: vi.fn() }
    );

    const sprite = createAgentSprite(zone, idle());
    sprite.update(working());
    sprite.update(idle());

    expect(pulse.kill).toHaveBeenCalledTimes(1);
  });

  it("does not stack a second pulse when already working and updated again", () => {
    const sprite = createAgentSprite(zone, idle());
    sprite.update(working());
    sprite.update(working()); // same visual state — full early return

    const pulses = gsapToMock.mock.calls.filter(([, vars]) => (vars as { repeat?: number }).repeat === -1);
    expect(pulses).toHaveLength(1);
  });
});

describe("createAgentSprite — real-art swap (setArt)", () => {
  function fakeTexture(height = 112): { height: number } {
    return { height };
  }

  it("swaps in a Sprite anchored at the feet, scaled to display height, hiding the fallback", async () => {
    const { Sprite } = await import("pixi.js");
    const sprite = createAgentSprite(zone, idle());
    const texture = fakeTexture(112) as never;

    sprite.setArt(texture);

    const character = sprite.view.children.find((c) => c instanceof Sprite) as unknown as {
      anchor: { set: ReturnType<typeof vi.fn> };
      scale: { set: ReturnType<typeof vi.fn> };
    };
    expect(character).toBeDefined();
    expect(character.anchor.set).toHaveBeenCalledWith(0.5, 1);
    expect(character.scale.set).toHaveBeenCalledWith(56 / 112);
    expect(sprite.view.children.some((c) => c instanceof Sprite)).toBe(true);
  });

  it("hides the fallback body while art is shown and restores it on setArt(null)", async () => {
    const { Sprite } = await import("pixi.js");
    const sprite = createAgentSprite(zone, idle());

    sprite.setArt(fakeTexture() as never);
    const [, fallbackAfterArt] = sprite.view.children.filter((c) => !(c instanceof Sprite)) as [
      unknown,
      { visible: boolean },
    ];
    expect(fallbackAfterArt.visible).toBe(false);

    sprite.setArt(null);
    expect(fallbackAfterArt.visible).toBe(true);
    expect(sprite.view.children.some((c) => c instanceof Sprite)).toBe(false);
  });

  it("updates position/zIndex-independently: swap does not move the sprite or touch tweens", () => {
    const sprite = createAgentSprite(zone, idle());
    sprite.update(working()); // alpha tween + pulse in flight

    sprite.setArt(fakeTexture() as never);

    expect(sprite.view.x).toBe(100);
    expect(sprite.view.y).toBe(50);
    expect(sprite.view.zIndex).toBe(50);
  });
});

describe("directionFor", () => {
  // Today's fixed single-row ZONE_ORDER only ever produces the "right" case
  // in practice (see scene-layout.ts) — the other 3 are exercised here only,
  // as a capability the sprite component supports for a future non-linear
  // layout (specs/visual-ui-applyr-world-phase2's Edge cases).
  it("right when dx dominates and is positive", () => {
    expect(directionFor(80, 40)).toBe("right");
  });

  it("left when dx dominates and is negative", () => {
    expect(directionFor(-80, 10)).toBe("left");
  });

  it("down when dy dominates and is positive", () => {
    expect(directionFor(10, 80)).toBe("down");
  });

  it("up when dy dominates and is negative", () => {
    expect(directionFor(5, -80)).toBe("up");
  });

  it("resolves an exact tie horizontally", () => {
    expect(directionFor(50, 50)).toBe("right");
  });
});

describe("tweenPosition", () => {
  it("computes direction from the sprite's current position to the target", () => {
    const sprite = createAgentSprite(zone, idle()); // starts at (100, 50)
    const handle = tweenPosition(asTarget(sprite.view), 180, 90); // dx=80, dy=40
    expect(handle.direction).toBe("right");
  });

  it("tweens x/y over a fixed duration", () => {
    const sprite = createAgentSprite(zone, idle());
    gsapToMock.mockClear();

    tweenPosition(asTarget(sprite.view), 180, 90);

    expect(gsapToMock).toHaveBeenCalledWith(
      sprite.view,
      expect.objectContaining({ x: 180, y: 90, duration: expect.any(Number) })
    );
  });

  it("tracks zIndex to the interpolated y every frame, landing exactly on target y", () => {
    let onUpdate: (() => void) | undefined;
    let onComplete: (() => void) | undefined;
    gsapToMock.mockImplementationOnce((_target, vars) => {
      onUpdate = vars.onUpdate as (() => void) | undefined;
      onComplete = vars.onComplete as (() => void) | undefined;
      return { kill: vi.fn() };
    });

    const sprite = createAgentSprite(zone, idle());
    sprite.view.y = 120; // simulate mid-flight interpolation done by gsap
    const handle = tweenPosition(asTarget(sprite.view), 180, 90);
    onUpdate?.();
    expect(sprite.view.zIndex).toBe(120);

    sprite.view.y = 90; // gsap lands on target
    onComplete?.();
    expect(sprite.view.zIndex).toBe(90);
  });

  it("kill() delegates to the underlying gsap tween", () => {
    const tween = { kill: vi.fn() };
    gsapToMock.mockReturnValueOnce(tween);

    const sprite = createAgentSprite(zone, idle());
    const handle = tweenPosition(asTarget(sprite.view), 180, 90);
    handle.kill();

    expect(tween.kill).toHaveBeenCalledTimes(1);
  });
});
