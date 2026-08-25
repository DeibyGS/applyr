import { Assets } from "pixi.js";
import type { Texture } from "pixi.js";
import type { AgentId } from "@/features/agents/types";

/**
 * The one place the office scene touches PixiJS asset loading
 * (specs/visual-ui-applyr-world-real-art — texture infrastructure ACs).
 *
 * Art files are owner-delivered and may not exist at all yet, so URLs are
 * discovered with Vite's eager globs instead of static imports: an empty
 * directory yields an empty map (no build error) and dropping a correctly
 * named file in is enough for it to show up on the next build/dev reload.
 */

const AGENT_URLS: Record<string, string> = import.meta.glob<string>(
  "../../../assets/office-scene/agents/*.webp",
  { eager: true, query: "?url", import: "default" }
);

const DESK_URLS: Record<string, string> = import.meta.glob<string>(
  "../../../assets/office-scene/scenery/desk-*.webp",
  { eager: true, query: "?url", import: "default" }
);

const AGENT_IDS = ["recruiter", "matching", "cv", "ats", "application"] as const;

function urlEndingIn(urls: Record<string, string>, fileName: string): string | null {
  return Object.values(urls).find((url) => url.endsWith(`/${fileName}`)) ?? null;
}

export interface SceneTextureStore {
  /** Synchronously returns a loaded texture, or null while pending/failed. */
  getAgent: (agentId: AgentId) => Texture | null;
  getDesk: (agentId: AgentId) => Texture | null;
}

export interface SceneTextureHandlers {
  onAgentArt?: (agentId: AgentId, texture: Texture) => void;
  onDeskArt?: (agentId: AgentId, texture: Texture) => void;
}

export interface SceneTextureDeps {
  load: (url: string) => Promise<Texture>;
  /** Test seam — overrides the glob-discovered URLs per entity kind. */
  urls?: {
    agent?: Partial<Record<AgentId, string>>;
    desk?: Partial<Record<AgentId, string>>;
  };
}

const defaultDeps: SceneTextureDeps = { load: (url) => Assets.load(url) };

/**
 * Fire-and-forget loader: kicks off one request per discovered file and never
 * rejects (a missing/corrupt asset degrades that entity to its placeholder,
 * it never crashes or blocks the scene). Handler callbacks fire once per
 * arriving texture so callers can swap art into existing sprites in place —
 * scene init is never awaited on any of this.
 */
export function startSceneTextureLoading(
  handlers: SceneTextureHandlers,
  deps: SceneTextureDeps = defaultDeps
): SceneTextureStore {
  const agents = new Map<AgentId, Texture>();
  const desks = new Map<AgentId, Texture>();
  const warned = new Set<string>();

  const attempt = (
    agentId: AgentId,
    url: string | null,
    deliver: (texture: Texture) => void
  ): void => {
    if (!url) return;
    deps
      .load(url)
      .then(deliver)
      .catch(() => {
        // Absent files are the normal pre-delivery state (globs skip them);
        // reaching here means the file exists but failed to fetch or decode.
        if (!warned.has(url)) {
          warned.add(url);
          console.warn(`Office scene: failed to load "${url}" — using placeholder`);
        }
      });
  };

  for (const agentId of AGENT_IDS) {
    const agentUrl = deps.urls?.agent?.[agentId] ?? urlEndingIn(AGENT_URLS, `${agentId}.webp`);
    attempt(agentId, agentUrl, (texture) => {
      agents.set(agentId, texture);
      handlers.onAgentArt?.(agentId, texture);
    });

    const deskUrl =
      deps.urls?.desk?.[agentId] ?? urlEndingIn(DESK_URLS, `desk-${agentId}.webp`);
    attempt(agentId, deskUrl, (texture) => {
      desks.set(agentId, texture);
      handlers.onDeskArt?.(agentId, texture);
    });
  }

  return {
    getAgent: (agentId) => agents.get(agentId) ?? null,
    getDesk: (agentId) => desks.get(agentId) ?? null,
  };
}
