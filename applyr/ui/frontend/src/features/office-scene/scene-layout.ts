import type { AgentId } from "@/features/agents/types";

export interface ZonePosition {
  agentId: AgentId;
  x: number;
  y: number;
}

/**
 * Fixed pipeline order — also the isometric depth-sort order (increasing y),
 * so zones naturally draw front-to-back in reading order. No free-roaming
 * layout: 5 zones, always in this order, per spec's hard-bounded MVP.
 */
const ZONE_ORDER: AgentId[] = ["recruiter", "matching", "cv", "ats", "application"];

const TILE_WIDTH = 160;
const TILE_HEIGHT = 80;
const ORIGIN_X = 120;
const ORIGIN_Y = 60;

/**
 * Each zone steps one isometric grid unit right of the previous one
 * (standard 2:1 projection: +x/2, +y/2 per step), so y increases
 * monotonically with pipeline order and can drive PixiJS zIndex directly.
 */
export function getZonePositions(): ZonePosition[] {
  return ZONE_ORDER.map((agentId, index) => ({
    agentId,
    x: ORIGIN_X + index * (TILE_WIDTH / 2),
    y: ORIGIN_Y + index * (TILE_HEIGHT / 2),
  }));
}
