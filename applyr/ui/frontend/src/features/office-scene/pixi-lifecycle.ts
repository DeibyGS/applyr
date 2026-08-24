import { Application } from "pixi.js";
import type { Container } from "pixi.js";

export interface PixiLifecycleOptions {
  width: number;
  height: number;
  host: HTMLElement;
}

export interface PixiLifecycleHandle {
  app: Application;
  stage: Container;
  destroy: () => void;
}

/**
 * Creates, initializes, mounts and starts a PixiJS Application against `host`.
 * The one place this project constructs `PIXI.Application` (ADR-012) — every
 * other file reaches Pixi only through the handle this returns.
 * `autoStart: false` + explicit `app.start()`/`app.stop()` makes ticker
 * lifecycle observable and testable, instead of relying on Pixi's implicit
 * auto-start behavior.
 */
export async function mountPixiStage(
  options: PixiLifecycleOptions
): Promise<PixiLifecycleHandle> {
  const { width, height, host } = options;
  const app = new Application();

  await app.init({
    width,
    height,
    backgroundAlpha: 0,
    antialias: true,
    autoStart: false,
    preference: "webgl", // skip the WebGPU probe — this scene has no WebGPU-only needs, and the probe logs a console warning on every mount when it fails
  });

  host.appendChild(app.canvas);
  app.start();

  let destroyed = false;
  const destroy = () => {
    if (destroyed) return;
    destroyed = true;
    app.stop();
    app.destroy(true, { children: true, texture: true });
  };

  return { app, stage: app.stage, destroy };
}
