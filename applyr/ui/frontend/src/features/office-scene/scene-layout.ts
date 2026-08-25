import type { AgentId } from "@/features/agents/types";

export interface ZonePosition {
  agentId: AgentId;
  x: number;
  y: number;
}

/**
 * Office floor plan — 3 agents in the front row, 2 in the back row,
 * with a small alternating x‑offset so each agent sits slightly left/right
 * of centre. This gives every agent "breathing room" and makes GSAP tweens
 * feel less robotic when agents move independently.
 */
const ZONE_ORDER: AgentId[] = ["recruiter", "matching", "cv", "ats", "application"];

// Office scene: 720×260px per OfficeScene.tsx; positions are screen-space
const DESK_SPACING = 120;   // horizontal gap between agents in the same row
const ROW_VERTICAL_GAP = 55; // vertical gap between front and back row
const FORROW_Y = 80;       // y‑coordinate of the front row
const BACKROW_Y = 140;     // y‑coordinate of the back row
// Offsets alternate left/right from centre so agents don't stack exactly.
const X_OFFSET = 25;       // pixels to shift left/right per agent
const FRONt_OFFSETS = [-X_OFFSET, 0, X_OFFSET]; // recruiter, matching, cv
const BACK_OFFSETS = [-X_OFFSET, X_OFFSET];       // ats, application

/**
 * Front row occupies indices 0‑2 (recruiter, matching, cv),
 * back row occupies indices 3‑4 (ats, application).
 * Front‑row agents have alternating left/right offsets;
 * back‑row agents are centred under the gap between front‑row agents.
 */
export function getZonePositions(): ZonePosition[] {
  const positions: ZonePosition[] = [];

  // Front row (3 agents): even spacing with alternating offsets
  for (let i = 0; i < 3; i += 1) {
    const agentId = ZONE_ORDER[i];
    const baseX = 180 + i * DESK_SPACING; // starts at 180, then 300, 420
    const offset = FRONt_OFFSETS[i];
    positions.push({ agentId, x: baseX + offset, y: FORROW_Y });
  }

  // Back row (2 agents): centred under the front row gap, with their own offsets
  for (let i = 3; i < 5; i += 1) {
    const agentId = ZONE_ORDER[i];
    const offset = BACK_OFFSETS[i - 3];
    // centre the back row under the front row: ats under the left gap, application under the right gap
    const baseX = 240 + (i - 3) * DESK_SPACING; // 240 for ats, 360 for application
    positions.push({ agentId, x: baseX + offset, y: BACKROW_Y });
  }

  return positions;
}
