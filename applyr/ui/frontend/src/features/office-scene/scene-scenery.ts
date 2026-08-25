import { Container, Graphics, Sprite } from "pixi.js";
import type { Texture } from "pixi.js";
import type { AgentId } from "@/features/agents/types";
import { getZonePositions } from "./scene-layout";

/** Fallback when a zone's desk art is missing — a subtle neutral pad keeping
 * the zone visually anchored without competing with agent status rings. */
const PAD_WIDTH = 56;
const PAD_HEIGHT = 28;
const PAD_COLOR = 0x6b7280;
const PAD_ALPHA = 0.5;

/** Real-art desks render at this display width regardless of source size
 * (art brief ships them at 256×160). */
const DESK_DISPLAY_WIDTH = 120;

export interface ZoneSceneryHandle {
  view: Container;
  /** Swaps a zone's furniture between real desk art and the fallback pad,
   * in place. Null restores the pad. */
  setDesk: (agentId: AgentId, texture: Texture | null) => void;
  destroy: () => void;
}

interface DeskEntity {
  holder: Container;
  pad: Graphics;
  desk: Sprite | null;
}

/**
 * One desk per pipeline zone, drawn at that zone's point and stacked just
 * behind the agent character standing there (spec SCN-1/SCN-2): zIndex is
 * zone.y - 1, so the sort-by-y stage renders
 * desk(i) < agent(i) < desk(i+1) for every consecutive pair of zones, and
 * walking offers layer against desks via their interpolated-y tracking.
 */
export function createZoneScenery(): ZoneSceneryHandle {
  const view = new Container();
  const entities = new Map<AgentId, DeskEntity>();

  for (const zone of getZonePositions()) {
    const holder = new Container();
    holder.x = zone.x;
    holder.y = zone.y;
    holder.zIndex = zone.y - 1;

    const pad = new Graphics();
    pad.ellipse(0, 0, PAD_WIDTH, PAD_HEIGHT).fill({ color: PAD_COLOR, alpha: PAD_ALPHA });

    holder.addChild(pad);
    view.addChild(holder);
    entities.set(zone.agentId, { holder, pad, desk: null });
  }

  const setDesk = (agentId: AgentId, texture: Texture | null) => {
    const entity = entities.get(agentId);
    if (!entity) return;

    if (!texture) {
      if (entity.desk) {
        entity.holder.removeChild(entity.desk);
        entity.desk.destroy();
        entity.desk = null;
      }
      entity.pad.visible = true;
      return;
    }

    if (!entity.desk) {
      entity.desk = new Sprite(texture);
      entity.desk.anchor.set(0.5, 1);
      entity.holder.addChild(entity.desk);
    } else {
      entity.desk.texture = texture;
    }
    entity.desk.scale.set(DESK_DISPLAY_WIDTH / texture.width);
    entity.pad.visible = false;
  };

  const destroy = () => {
    view.destroy({ children: true });
  };

  return { view, setDesk, destroy };
}
