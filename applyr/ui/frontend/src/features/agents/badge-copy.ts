import type { AgentId } from "./types";

/**
 * Playful, sim-game-flavored status copy — replaces the literal "Idle"/
 * "Working" words. The detail line below the badge (taskText() in
 * AgentCard.tsx) still carries the specific fact ("Acme Corp — 91% match");
 * this is just the short state pill.
 */
export const BADGE_COPY: Record<AgentId, { idle: string; working: string }> = {
  recruiter: { idle: "Grabbing a coffee ☕", working: "Reading a new offer" },
  matching: { idle: "Waiting for offers", working: "Crunching the numbers" },
  cv: { idle: "Sharpening pencils ✏️", working: "Tailoring your CV" },
  ats: { idle: "On standby", working: "Running the checks" },
  application: { idle: "Ready when you are", working: "Sealing the envelope ✉️" },
};
