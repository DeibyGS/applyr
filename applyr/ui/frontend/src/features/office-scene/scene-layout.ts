import type { AgentId } from "@/features/agents/types";

export interface ZonePosition {
  agentId: AgentId;
  x: number;
  y: number;
}

/**
 * Office floor plan — 3 agents in the front row, 2 in the back row,
 * slightly staggered left/right so the arrangement reads like an office
 * seating pattern rather than a raw isometric grid.
 */
const ZONE_ORDER: AgentId[] = ["recruiter", "matching", "cv", "ats", "application"];

// Office scene: 720×260px per OfficeScene.tsx; positions are screen-space
const DESK_SPACING = 120;   // horizontal gap between agents in the same row
const ROW_VERTICAL_GAP = 55; // vertical gap between front and back row
const FORROW_Y = 80;       // y‑coordinate of the front row
const BACKROW_Y = 140;     // y‑coordinate of the back row

/**
 * Front row occupies indices 0‑2 (recruiter, matching, cv),
 * back row occupies indices 3‑4 (ats, application).
 * Front‑row agents are spaced evenly; back‑row agents are centred under
 * the gap between the front‑row agents.
 */
export function getZonePositions(): ZonePosition[] {
  const positions: ZonePosition[] = [];

  // Front row (3 agents): even spacing across the 720px wide scene
  for (let i = 0; i < 3; i += 1) {
    const agentId = ZONE_ORDER[i];
    const x = 180 + i * DESK_SPACING; // starts at 180, then 300, 420
    positions.push({ agentId, x, y: FORROW_Y });
  }

  // Back row (2 agents): centred under the front row gap
  for (let i = 3; i < 5; i += 1) {
    const agentId = ZONE_ORDER[i];
    // at i=3 (ats) we place under the space between recruiter (i=0) and matching (i=1)
    // at i=4 (application) we place under the space between matching (i=1) and cv (i=2)
    const frontLeft = ZONE_ORDER[i - 3];
    const frontRight = ZONE_ORDER[i - 2];
    const x =
      240 + (i - 3) * DESK_SPACING; // 240 for ats, 360 for application
    positions.push({ agentId, x, y: BACKROW_Y });
  }

  return positions;
}
