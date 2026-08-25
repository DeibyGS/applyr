import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentStatus } from "@/features/agents/types";
import type { ZonePosition } from "./scene-layout";

const destroyMock = vi.fn();

vi.mock("pixi.js", () => {
  class MockGraphics {
    x = 0;
    y = 0;
    zIndex = 0;
    alpha = 1;
    clear = vi.fn(function (this: MockGraphics) {
      return this;
    });
    circle = vi.fn(function (this: MockGraphics) {
      return this;
    });
    fill = vi.fn(function (this: MockGraphics) {
      return this;
    });
    destroy = destroyMock;
  }
  return { Graphics: MockGraphics };
});

const gsapToMock = vi.fn((_target: unknown, _vars: Record<string, unknown>) => ({ kill: vi.fn() }));
vi.mock("gsap", () => ({ gsap: { to: gsapToMock } }));

const { createAgentSprite, directionFor, tweenPosition } = await import("./agent-sprite");

const zone: ZonePosition = { agentId: "recruiter", x: 100, y: 50 };

function idle(): AgentStatus {
  return { agentId: "recruiter", state: "idle" };
}
function working(): AgentStatus {
  return { agentId: "recruiter", state: "working", pendingCount: 2 };
}
function notConnected(): AgentStatus {
  return { agentId: "cv", state: "not_connected" };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("createAgentSprite", () => {
  it("positions the sprite at the zone's coordinates and paints the initial state", () => {
    const sprite = createAgentSprite(zone, idle());
    expect(sprite.graphics.x).toBe(100);
    expect(sprite.graphics.y).toBe(50);
    expect(sprite.graphics.fill).toHaveBeenCalledTimes(1);
  });

  it("does not tween when the new status has the same visual state", () => {
    const sprite = createAgentSprite(zone, idle());
    sprite.update(idle());
    expect(gsapToMock).not.toHaveBeenCalled();
  });

  it("tweens alpha from a dimmed value back to 1 when state actually changes", () => {
    const sprite = createAgentSprite(zone, idle());
    sprite.update(working());

    expect(sprite.graphics.alpha).toBe(0.35);
    expect(gsapToMock).toHaveBeenCalledTimes(1);
    expect(gsapToMock).toHaveBeenCalledWith(
      sprite.graphics,
      expect.objectContaining({ alpha: 1, duration: expect.any(Number) })
    );
  });

  it("kills the in-flight tween and starts a new one if state changes again before it finishes", () => {
    const firstTween = { kill: vi.fn() };
    gsapToMock.mockReturnValueOnce(firstTween);

    const sprite = createAgentSprite(zone, idle());
    sprite.update(working());
    sprite.update(idle());

    expect(firstTween.kill).toHaveBeenCalledTimes(1);
    expect(gsapToMock).toHaveBeenCalledTimes(2);
  });

  it("does not reset alpha when interrupting a mid-flight tween — continues from the current value", () => {
    const firstTween = { kill: vi.fn() };
    gsapToMock.mockReturnValueOnce(firstTween);

    const sprite = createAgentSprite(zone, idle());
    sprite.update(working());
    expect(sprite.graphics.alpha).toBe(0.35); // fresh transition — dims first

    // Simulate the first tween having partially progressed before it's interrupted.
    sprite.graphics.alpha = 0.7;
    sprite.update(idle());

    expect(sprite.graphics.alpha).toBe(0.7); // untouched — no flash back to 0.35
  });

  it("resets alpha to a dimmed value again once a prior tween has actually completed", () => {
    let onComplete: (() => void) | undefined;
    gsapToMock.mockImplementationOnce((_target, vars) => {
      onComplete = vars.onComplete as (() => void) | undefined;
      return { kill: vi.fn() };
    });

    const sprite = createAgentSprite(zone, idle());
    sprite.update(working());
    onComplete?.(); // first tween finishes naturally
    sprite.graphics.alpha = 1;

    sprite.update(idle());

    expect(sprite.graphics.alpha).toBe(0.35); // no tween in flight — dims again as a fresh transition
  });

  it("never tweens a not_connected zone, regardless of repeated updates", () => {
    const sprite = createAgentSprite(zone, notConnected());
    sprite.update(notConnected());
    sprite.update(notConnected());
    expect(gsapToMock).not.toHaveBeenCalled();
  });

  it("destroy() kills any active tween and destroys the graphics object", () => {
    const activeTween = { kill: vi.fn() };
    gsapToMock.mockReturnValueOnce(activeTween);

    const sprite = createAgentSprite(zone, idle());
    sprite.update(working());
    sprite.destroy();

    expect(activeTween.kill).toHaveBeenCalledTimes(1);
    expect(destroyMock).toHaveBeenCalledTimes(1);
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
    const handle = tweenPosition(sprite.graphics, 180, 90); // dx=80, dy=40
    expect(handle.direction).toBe("right");
  });

  it("tweens x/y over a fixed duration", () => {
    const sprite = createAgentSprite(zone, idle());
    gsapToMock.mockClear();

    tweenPosition(sprite.graphics, 180, 90);

    expect(gsapToMock).toHaveBeenCalledWith(
      sprite.graphics,
      expect.objectContaining({ x: 180, y: 90, duration: expect.any(Number) })
    );
  });

  it("updates zIndex to the target y and resolves done() on completion", async () => {
    let onComplete: (() => void) | undefined;
    gsapToMock.mockImplementationOnce((_target, vars) => {
      onComplete = vars.onComplete as (() => void) | undefined;
      return { kill: vi.fn() };
    });

    const sprite = createAgentSprite(zone, idle());
    const handle = tweenPosition(sprite.graphics, 180, 90);
    onComplete?.();
    await handle.done;

    expect(sprite.graphics.zIndex).toBe(90);
  });

  it("kill() delegates to the underlying gsap tween", () => {
    const tween = { kill: vi.fn() };
    gsapToMock.mockReturnValueOnce(tween);

    const sprite = createAgentSprite(zone, idle());
    const handle = tweenPosition(sprite.graphics, 180, 90);
    handle.kill();

    expect(tween.kill).toHaveBeenCalledTimes(1);
  });
});
