import { useCallback, useEffect, useRef } from "react";
import type { Container } from "pixi.js";
import type { AgentStatus, AgentId } from "@/features/agents/types";
import { PixiStage } from "./PixiStage";
import { getZonePositions } from "./scene-layout";
import { createAgentSprite, type AgentSpriteHandle } from "./agent-sprite";

const SCENE_WIDTH = 720;
const SCENE_HEIGHT = 260;

interface OfficeSceneProps {
  statuses: AgentStatus[];
}

/**
 * Thin composition: wires deriveAgentStatuses' output into 5 Pixi sprites,
 * one per zone. Sprites live outside React's tree (plain Pixi objects), so
 * they're created once in onReady and updated imperatively afterwards —
 * `handleReady` must stay referentially stable or PixiStage would tear down
 * and recreate the whole canvas on every poll.
 */
export function OfficeScene({ statuses }: OfficeSceneProps) {
  const spritesRef = useRef<Map<AgentId, AgentSpriteHandle>>(new Map());
  const latestStatusesRef = useRef(statuses);

  useEffect(() => {
    latestStatusesRef.current = statuses;
  }, [statuses]);

  const handleReady = useCallback((stage: Container) => {
    stage.sortableChildren = true;
    for (const zone of getZonePositions()) {
      const status = latestStatusesRef.current.find((s) => s.agentId === zone.agentId);
      if (!status) continue;
      const sprite = createAgentSprite(zone, status);
      stage.addChild(sprite.graphics);
      spritesRef.current.set(zone.agentId, sprite);
    }
  }, []);

  useEffect(() => {
    for (const status of statuses) {
      spritesRef.current.get(status.agentId)?.update(status);
    }
  }, [statuses]);

  useEffect(() => {
    const sprites = spritesRef.current;
    return () => {
      for (const sprite of sprites.values()) sprite.destroy();
      sprites.clear();
    };
  }, []);

  return <PixiStage width={SCENE_WIDTH} height={SCENE_HEIGHT} onReady={handleReady} />;
}
