import { Assets } from "pixi.js";
import type { Texture } from "pixi.js";
import type { AgentId } from "@/features/agents/types";

/**
 * The one place the office scene touches PixiJS asset loading
 * (specs/visual-ui-applyr-world-real-art — texture infrastructure ACs).
 *
 * Art files are owner-delivered and may not exist at all yet, so URLs are
 * discovered with Vite's eager glob instead of static imports: an empty
 * directory yields an empty map (no build error) and dropping a correctly
 * named file in is enough for it to show up on the next build/dev reload.
 */

const AGENT_URLS: Record<string, string> = import.meta.glob<string>(
  "../../../assets/office-scene/agents/*.webp",
  { eager: true, query: "?url", import: "default" }
);

function urlForAgent(agentId: AgentId): string | null {
  const entry = Object.entries(AGENT_URLS).find(([path]) =>
    path.endsWith(`/${agentId}.webp`)
  );
  return entry?.[1] ?? null;
}

export interface SceneTextureStore {
  /** Synchronously returns the loaded texture, or null while pending/failed. */
  getAgent: (agentId: AgentId) => Texture | null;
}

export interface SceneTextureDeps {
  load: (url: string) => Promise<Texture>;
  /** Test seam — overrides the glob-discovered URLs per agent. */
  urls?: Partial<Record<AgentId, string>>;
}

const defaultDeps: SceneTextureDeps = { load: (url) => Assets.load(url) };

/**
 * Fire-and-forget loader: kicks off one request per discovered file and never
 * rejects (a missing/corrupt asset degrades that entity to its placeholder,
 * it never crashes or blocks the scene). `onAgentArt` fires once per agent
 * whose texture arrives, so callers can swap art into an existing sprite in
 * place — scene init is never awaited on any of this.
 */
export function startSceneTextureLoading(
  onAgentArt: (agentId: AgentId, texture: Texture) => void,
  deps: SceneTextureDeps = defaultDeps
): SceneTextureStore {
  const loaded = new Map<AgentId, Texture>();
  const warned = new Set<string>();

  for (const agentId of ["recruiter", "matching", "cv", "ats", "application"] as const) {
    const url = deps.urls?.[agentId] ?? urlForAgent(agentId);
    if (!url) continue;

    deps
      .load(url)
      .then((texture) => {
        loaded.set(agentId, texture);
        onAgentArt(agentId, texture);
      })
      .catch(() => {
        // Absent files are the normal pre-delivery state (glob skips them);
        // reaching here means the file exists but failed to fetch or decode.
        if (!warned.has(url)) {
          warned.add(url);
          console.warn(`Office scene: failed to load "${url}" — using placeholder`);
        }
      });
  }

  return {
    getAgent: (agentId) => loaded.get(agentId) ?? null,
  };
}
