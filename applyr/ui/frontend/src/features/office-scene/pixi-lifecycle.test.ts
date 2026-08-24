import { beforeEach, describe, expect, it, vi } from "vitest";
import { mountPixiStage } from "./pixi-lifecycle";

const initMock = vi.fn().mockResolvedValue(undefined);
const startMock = vi.fn();
const stopMock = vi.fn();
const destroyMock = vi.fn();

vi.mock("pixi.js", () => {
  class MockApplication {
    canvas = {};
    stage = {};
    init = initMock;
    start = startMock;
    stop = stopMock;
    destroy = destroyMock;
  }
  return { Application: MockApplication };
});

function fakeHost() {
  return { appendChild: vi.fn() } as unknown as HTMLElement;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("mountPixiStage", () => {
  it("initializes with the given dimensions, mounts the canvas, then starts the ticker", async () => {
    const host = fakeHost();
    const handle = await mountPixiStage({ width: 800, height: 400, host });

    expect(initMock).toHaveBeenCalledWith(
      expect.objectContaining({ width: 800, height: 400, autoStart: false })
    );
    expect(host.appendChild).toHaveBeenCalledWith(handle.app.canvas);
    expect(startMock).toHaveBeenCalledTimes(1);
    expect((host.appendChild as ReturnType<typeof vi.fn>).mock.invocationCallOrder[0]).toBeLessThan(
      startMock.mock.invocationCallOrder[0]
    );
  });

  it("destroy() stops the ticker before destroying the application, with children and textures", async () => {
    const handle = await mountPixiStage({ width: 800, height: 400, host: fakeHost() });

    handle.destroy();

    expect(stopMock).toHaveBeenCalledTimes(1);
    expect(destroyMock).toHaveBeenCalledWith(true, { children: true, texture: true });
    expect(stopMock.mock.invocationCallOrder[0]).toBeLessThan(
      destroyMock.mock.invocationCallOrder[0]
    );
  });

  it("destroy() is idempotent — calling it twice only tears down once", async () => {
    const handle = await mountPixiStage({ width: 800, height: 400, host: fakeHost() });

    handle.destroy();
    handle.destroy();

    expect(stopMock).toHaveBeenCalledTimes(1);
    expect(destroyMock).toHaveBeenCalledTimes(1);
  });

  it("repeated mount/destroy cycles create and tear down one Application each time, no leak", async () => {
    for (let i = 0; i < 3; i++) {
      const handle = await mountPixiStage({ width: 800, height: 400, host: fakeHost() });
      handle.destroy();
    }

    expect(initMock).toHaveBeenCalledTimes(3);
    expect(startMock).toHaveBeenCalledTimes(3);
    expect(stopMock).toHaveBeenCalledTimes(3);
    expect(destroyMock).toHaveBeenCalledTimes(3);
  });
});
