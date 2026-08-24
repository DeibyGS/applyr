import { useEffect, useRef } from "react";
import type { Container } from "pixi.js";
import { mountPixiStage } from "./pixi-lifecycle";

interface PixiStageProps {
  width: number;
  height: number;
  onReady: (stage: Container) => void;
}

/**
 * Thin lifecycle shell — all Pixi setup/teardown logic lives in
 * pixi-lifecycle.ts (unit tested there). This component only wires it to
 * React's mount/unmount, guarding against React StrictMode's double-invoked
 * effect firing destroy() on a handle that hasn't resolved yet.
 */
export function PixiStage({ width, height, onReady }: PixiStageProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    let cancelled = false;
    let destroy: (() => void) | undefined;

    mountPixiStage({ width, height, host })
      .then((handle) => {
        if (cancelled) {
          handle.destroy();
          return;
        }
        destroy = handle.destroy;
        onReady(handle.stage);
      })
      .catch((error: unknown) => {
        // No WebGL context (disabled hardware acceleration, exhausted
        // context budget, etc.) leaves the scene blank rather than
        // crashing — logged so it's diagnosable instead of a silent
        // unhandled rejection.
        console.error("Office scene: failed to initialize the Pixi canvas", error);
      });

    return () => {
      cancelled = true;
      destroy?.();
    };
  }, [width, height, onReady]);

  return <div ref={hostRef} />;
}
