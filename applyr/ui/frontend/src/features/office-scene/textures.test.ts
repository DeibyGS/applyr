import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("pixi.js", () => ({
  Assets: { load: vi.fn() },
}));

const { startSceneTextureLoading } = await import("./textures");
import type { AgentId } from "@/features/agents/types";

function textureStub() {
  return { label: "fake-texture" } as never;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("startSceneTextureLoading", () => {
  it("delivers each discovered texture through onAgentArt and records it", async () => {
    const onAgentArt = vi.fn();
    const store = startSceneTextureLoading(onAgentArt, {
      load: (url) => (url.includes("cv") ? Promise.resolve(textureStub()) : Promise.reject(new Error("skip"))),
      urls: { cv: "/assets/office-scene/agents/cv.webp" },
    });

    // microtask drain
    await Promise.resolve();
    await Promise.resolve();

    expect(onAgentArt).toHaveBeenCalledWith("cv", textureStub());
    expect(store.getAgent("cv")).not.toBeNull();
  });

  it("resolves null for an agent with no delivered file — no request, no warning", async () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const onAgentArt = vi.fn();

    const store = startSceneTextureLoading(onAgentArt, {
      load: vi.fn(),
      urls: {}, // glob empty = owner hasn't delivered art yet
    });
    await Promise.resolve();

    expect(onAgentArt).not.toHaveBeenCalled();
    for (const agentId of ["recruiter", "matching", "cv", "ats", "application"] as AgentId[]) {
      expect(store.getAgent(agentId)).toBeNull();
    }
    expect(warnSpy).not.toHaveBeenCalled();
    warnSpy.mockRestore();
  });

  it("a failed load degrades to placeholder (null) with exactly one warn per URL", async () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const onAgentArt = vi.fn();

    const store = startSceneTextureLoading(onAgentArt, {
      load: () => Promise.reject(new Error("decode error")),
      urls: { ats: "/assets/office-scene/agents/ats.webp" },
    });
    await new Promise((r) => setTimeout(r, 0));

    expect(store.getAgent("ats")).toBeNull();
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy.mock.calls[0][0]).toContain("/assets/office-scene/agents/ats.webp");
    warnSpy.mockRestore();
  });

  it("never rejects — a throwing loader is swallowed per agent without affecting others", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      const onAgentArt = vi.fn();
      const store = startSceneTextureLoading(onAgentArt, {
        load: (url) =>
          url.includes("matching")
            ? Promise.reject(new Error("network down"))
            : Promise.resolve(textureStub()),
        urls: { matching: "/matching.webp", recruiter: "/recruiter.webp" },
      });
      await new Promise((r) => setTimeout(r, 0));

      expect(store.getAgent("recruiter")).not.toBeNull();
      expect(store.getAgent("matching")).toBeNull();
      expect(onAgentArt).toHaveBeenCalledTimes(1);
    } finally {
      errorSpy.mockRestore();
    }
  });
});
