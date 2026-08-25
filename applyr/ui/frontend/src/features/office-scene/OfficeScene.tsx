import { useCallback, useEffect, useRef } from "react";
import type { Container } from "pixi.js";
import type { AgentStatus, AgentId } from "@/features/agents/types";
import type { JobSummary } from "@/api/jobs";
import { subscribeToPipelineEvents } from "@/api/events";
import { PixiStage } from "./PixiStage";
import { getZonePositions } from "./scene-layout";
import { createAgentSprite, type AgentSpriteHandle } from "./agent-sprite";
import { createPipelineSpriteManager, type PipelineSpriteManager } from "./pipeline-sprites";
import { startSceneTextureLoading } from "./textures";
import { createZoneScenery, type ZoneSceneryHandle } from "./scene-scenery";

const SCENE_WIDTH = 720;
const SCENE_HEIGHT = 260;

interface OfficeSceneProps {
  statuses: AgentStatus[];
  jobs: JobSummary[];
  /** True once the first real GET /api/jobs response has landed — distinct
   * from `jobs.length > 0`, which is also true (and stays 0 forever) for a
   * fresh install with zero offers. See seedPipelineIfReady below. */
  jobsLoaded: boolean;
}

function toPipelineOffers(jobs: JobSummary[]) {
  return jobs
    .filter((job) => job.pipeline_stage !== null)
    .map((job) => ({ offerId: job.id, stage: job.pipeline_stage! }));
}

/**
 * Thin composition: wires deriveAgentStatuses' output into 5 Pixi sprites,
 * one per zone, plus one per-offer sprite per in-flight job (ADR-013).
 * Sprites live outside React's tree (plain Pixi objects), so they're created
 * once in onReady and updated imperatively afterwards — `handleReady` must
 * stay referentially stable or PixiStage would tear down and recreate the
 * whole canvas on every poll.
 *
 * `jobs` only ever seeds the pipeline sprites once — every transition after
 * that comes exclusively from the live SSE stream, never from a later
 * `jobs` poll (spec's "no retroactive replay" rule). Seeding is gated on
 * BOTH the canvas being ready AND `jobsLoaded`, whichever arrives last:
 * Pixi's async WebGL init (PixiStage.tsx) and the first `GET /api/jobs`
 * fetch race independently with no ordering guarantee. Seeding from
 * `handleReady` unconditionally used to lose that race silently — if Pixi
 * finished first, it seeded from whatever `jobs` happened to be at that
 * instant (usually still `[]`), and no offer already in-flight before page
 * load ever got a sprite until a live SSE transition for that exact offer
 * happened to arrive (code-review finding).
 */
export function OfficeScene({ statuses, jobs, jobsLoaded }: OfficeSceneProps) {
  const spritesRef = useRef<Map<AgentId, AgentSpriteHandle>>(new Map());
  const pipelineRef = useRef<PipelineSpriteManager | null>(null);
  const sceneryRef = useRef<ZoneSceneryHandle | null>(null);
  const latestStatusesRef = useRef(statuses);
  const latestJobsRef = useRef(jobs);
  const jobsLoadedRef = useRef(jobsLoaded);
  const pipelineSeededRef = useRef(false);
  const disposedRef = useRef(false);

  useEffect(() => {
    latestStatusesRef.current = statuses;
  }, [statuses]);

  const seedPipelineIfReady = useCallback(() => {
    if (pipelineSeededRef.current || !pipelineRef.current || !jobsLoadedRef.current) return;
    pipelineRef.current.setInitial(toPipelineOffers(latestJobsRef.current));
    pipelineSeededRef.current = true;
  }, []);

  useEffect(() => {
    latestJobsRef.current = jobs;
    seedPipelineIfReady();
  }, [jobs, seedPipelineIfReady]);

  useEffect(() => {
    jobsLoadedRef.current = jobsLoaded;
    seedPipelineIfReady();
  }, [jobsLoaded, seedPipelineIfReady]);

  const handleReady = useCallback((stage: Container) => {
    stage.sortableChildren = true;

    // Room first, then occupants — zIndex (sort-by-y) decides stacking, not
    // insertion order.
    sceneryRef.current = createZoneScenery();
    stage.addChild(sceneryRef.current.view);

    for (const zone of getZonePositions()) {
      const status = latestStatusesRef.current.find((s) => s.agentId === zone.agentId);
      if (!status) continue;
      const sprite = createAgentSprite(zone, status);
      stage.addChild(sprite.view);
      spritesRef.current.set(zone.agentId, sprite);
    }

    // Art arrives asynchronously and per-entity (may be absent entirely) —
    // each texture swaps into its existing sprite/desk in place. Guarded
    // against post-unmount arrivals: a late-resolving load must not touch
    // destroyed objects.
    startSceneTextureLoading({
      onAgentArt: (agentId, texture) => {
        if (!disposedRef.current) spritesRef.current.get(agentId)?.setArt(texture);
      },
      onDeskArt: (agentId, texture) => {
        if (!disposedRef.current) sceneryRef.current?.setDesk(agentId, texture);
      },
    });

    pipelineRef.current = createPipelineSpriteManager(stage);
    seedPipelineIfReady();
  }, [seedPipelineIfReady]);

  useEffect(() => {
    for (const status of statuses) {
      spritesRef.current.get(status.agentId)?.update(status);
    }
  }, [statuses]);

  useEffect(() => {
    return subscribeToPipelineEvents((event) => {
      pipelineRef.current?.applyEvent(event);
    });
  }, []);

  useEffect(() => {
    disposedRef.current = false;
    const sprites = spritesRef.current;
    return () => {
      disposedRef.current = true;
      for (const sprite of sprites.values()) sprite.destroy();
      sprites.clear();
      sceneryRef.current?.destroy();
      sceneryRef.current = null;
      pipelineRef.current?.destroy();
      pipelineRef.current = null;
    };
  }, []);

  return <PixiStage width={SCENE_WIDTH} height={SCENE_HEIGHT} onReady={handleReady} />;
}
