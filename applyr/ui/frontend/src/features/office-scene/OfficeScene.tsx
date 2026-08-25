import { useCallback, useEffect, useRef, useState } from "react";
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
import { AgentStateManager } from "./agent-state-machine";
import { EventBus, connectEventSourceToBus } from "./event-bus";
import { createAgentBubble, type AgentBubbleHandle, type AgentBubbleContent } from "./agent-bubble";
import { DEFAULT_PIPELINE, VISUAL_PROPS } from "./types";
import { API_BASE } from "@/api/client";
import type { WorkArtifact, WorkArtifactSpriteHandle } from "./types";
import { createWorkArtifactSprite } from "./work-artifact-sprite";
import { MovementController } from "./movement-controller";
import { AgentInspector } from "./AgentInspector";
import { TerminalPanel } from "./TerminalPanel";
import { VISUAL, DURATION } from "./animation-tokens";

const SCENE_WIDTH = VISUAL.sceneWidth;
const SCENE_HEIGHT = VISUAL.sceneHeight;

interface OfficeSceneProps {
  statuses: AgentStatus[];
  jobs: JobSummary[];
  jobsLoaded: boolean;
}

function toPipelineOffers(jobs: JobSummary[]) {
  return jobs
    .filter((job) => job.pipeline_stage !== null)
    .map((job) => ({ offerId: job.id, stage: job.pipeline_stage! }));
}

/**
 * OfficeScene — spatial pipeline visualization (Phase 2).
 * 
 * Architecture:
 * - AgentStateManager: pure TS state machines (one per agent) driven by events
 * - EventBus: in-memory pub/sub, fed by SSE stream
 * - AgentSprites: PixiJS visual representation with 9 states + animations
 * - AgentBubbles: Clickable speech/work bubbles above each agent
 * - PipelineSprites: Per-offer sprites walking between zones (existing)
 * 
 * Event flow:
 * SSE (enriched) -> EventBus -> AgentStateManager -> AgentSprites + Bubbles
 * 
 * Legacy status polling (deriveAgentStatuses) used only for initial state
 * and as fallback when SSE is unavailable.
 */
export function OfficeScene({ statuses, jobs, jobsLoaded }: OfficeSceneProps) {
  const spritesRef = useRef<Map<AgentId, AgentSpriteHandle>>(new Map());
  const bubblesRef = useRef<Map<AgentId, AgentBubbleHandle>>(new Map());
  const pipelineRef = useRef<PipelineSpriteManager | null>(null);
  const sceneryRef = useRef<ZoneSceneryHandle | null>(null);
  const latestStatusesRef = useRef(statuses);
  const latestJobsRef = useRef(jobs);
  const jobsLoadedRef = useRef(jobsLoaded);
  const pipelineSeededRef = useRef(false);
  const disposedRef = useRef(false);
  
  // Phase 2: State machines + event bus
  const stateManagerRef = useRef<AgentStateManager>(new AgentStateManager(DEFAULT_PIPELINE));
  const eventBusRef = useRef(EventBus.getInstance());
  const eventSourceRef = useRef<EventSource | null>(null);
  const cleanupEventBusRef = useRef<(() => void) | null>(null);
  
  // Phase 4: Movement controller for handoffs
  const movementControllerRef = useRef<MovementController | null>(null);
  
  // UI state for inspector
  const [inspectorTarget, setInspectorTarget] = useState<AgentId | null>(null);
  
  // View mode: office | terminal | split
  const [viewMode, setViewMode] = useState<"office" | "terminal" | "split">("office");
  
  // Responsive viewport handling
  const [viewport, setViewport] = useState<{ width: number; height: number }>(() => ({
    width: typeof window !== "undefined" ? window.innerWidth : 1200,
    height: typeof window !== "undefined" ? window.innerHeight : 800,
  }));
  
  // Computed responsive scale
  const sceneScale = viewport.width < 768 ? 0.7 : viewport.width < 1024 ? 0.85 : 1;
  const isMobile = viewport.width < 768;
  const isTablet = viewport.width >= 768 && viewport.width < 1024;

  useEffect(() => {
    const handleResize = () => {
      setViewport({ width: window.innerWidth, height: window.innerHeight });
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

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

  // Initialize EventBus connection to SSE
  useEffect(() => {
    const eventSource = new EventSource(`${API_BASE}/api/events/enriched`);
    eventSourceRef.current = eventSource;

    cleanupEventBusRef.current = connectEventSourceToBus(eventSource, eventBusRef.current);

    eventSource.onerror = () => {
      console.warn("[OfficeScene] SSE connection error, will auto-reconnect");
    };

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (cleanupEventBusRef.current) {
        cleanupEventBusRef.current();
        cleanupEventBusRef.current = null;
      }
    };
  }, []);

  // Track artifact sprites for handoff animations
  const artifactSpritesRef = useRef<Map<string, WorkArtifactSpriteHandle>>(new Map());

  // Process events from EventBus through StateManager and update visuals
  useEffect(() => {
    const handleEvent = async (event: any) => {
      if (disposedRef.current) return;
      
      // Feed event to state machines
      const transitions = stateManagerRef.current.processEvent(event);
      
      // Handle artifact-specific events
      await handleArtifactEvent(event);
      
      // Update sprites and bubbles based on state transitions
      for (const [agentId, transition] of transitions) {
        if (transition.changed) {
          const sprite = spritesRef.current.get(agentId as AgentId);
          const bubble = bubblesRef.current.get(agentId as AgentId);
          const snapshot = stateManagerRef.current.getMachine(agentId)?.getSnapshot();
          
          if (sprite) {
            sprite.setVisualState(transition.current);
          }
          
          if (bubble && snapshot) {
            bubble.setContent({
              state: snapshot.visualState,
              task: snapshot.currentTask ?? undefined,
              command: snapshot.currentCommand ?? undefined,
              outputSummary: snapshot.outputSummary ?? undefined,
              artifact: snapshot.currentArtifact ?? undefined,
            });
            bubble.show();
          }
        }
      }
    };

    // Handle artifact/handoff events
    const handleArtifactEvent = async (event: any) => {
      if (disposedRef.current) return;

      const fromAgent = event.payload?.from_agent;
      const toAgent = event.payload?.to_agent;
      const artifactData = event.payload?.artifact;
      const agentId = event.agent_id;

      // Create artifact sprite from event data
      const getOrCreateArtifactSprite = (key: string, artifact: any) => {
        let artifactSprite = artifactSpritesRef.current.get(key);
        if (!artifactSprite && artifact) {
          artifactSprite = createWorkArtifactSprite(artifact);
          artifactSpritesRef.current.set(key, artifactSprite);
          // Add to stage if not already there
          const stage = artifactSprite.view.parent;
          if (!stage) {
            // We'll add it when needed during handoff
          }
        }
        return artifactSprite;
      };

      switch (event.type) {
        case "handoff.started": {
          if (fromAgent && toAgent && artifactData) {
            // Delegate to MovementController for full handoff orchestration
            const handoffId = `handoff-${fromAgent}-${toAgent}-${Date.now()}`;
            movementControllerRef.current?.startHandoff(handoffId, fromAgent, toAgent, artifactData);
          }
          break;
        }

        case "agent.receiving": {
          if (agentId && artifactData) {
            const receiverSprite = spritesRef.current.get(agentId);
            if (receiverSprite) {
              receiverSprite.attachArtifact(artifactData);
            }
          }
          break;
        }

        case "handoff.walking": {
          // MovementController handles the walking animation
          // This event is just for progress tracking if needed
          break;
        }

        case "handoff.completed": {
          // MovementController handles completion
          // Just ensure sender detaches if not already done
          if (fromAgent && artifactData) {
            const senderSprite = spritesRef.current.get(fromAgent);
            if (senderSprite) {
              senderSprite.detachArtifact();
            }
          }
          break;
        }

        case "agent.completed": {
          // Agent finished work - could detach artifact if it was the final stage
          const sprite = spritesRef.current.get(agentId);
          if (sprite && artifactData) {
            // Check if this is a terminal stage (application)
            if (agentId === "application") {
              sprite.detachArtifact();
            }
          }
          break;
        }
      }
    };

    const subId = eventBusRef.current.subscribe(handleEvent);
    return () => {
      eventBusRef.current.unsubscribe(subId);
    };
  }, []);

  // Fallback: update from legacy status polling (when SSE is slow/unavailable)
  useEffect(() => {
    for (const status of statuses) {
      const sprite = spritesRef.current.get(status.agentId);
      if (sprite) {
        // Only use legacy if no enriched events have been received for this agent recently
        sprite.update(status);
      }
    }
  }, [statuses]);

  const handleReady = useCallback((stage: Container) => {
    if (disposedRef.current) return;
    
    stage.sortableChildren = true;

    // Room first, then occupants — zIndex (sort-by-y) decides stacking
    sceneryRef.current = createZoneScenery();
    stage.addChild(sceneryRef.current.view);

    // Create agent sprites and bubbles for each zone
    for (const zone of getZonePositions()) {
      const status = latestStatusesRef.current.find((s) => s.agentId === zone.agentId);
      if (!status) continue;
      
      // Create sprite
      const sprite = createAgentSprite(zone, status);
      stage.addChild(sprite.view);
      spritesRef.current.set(zone.agentId, sprite);
      
      // Create bubble
      const bubble = createAgentBubble(zone.agentId, {
        state: "idle",
      });
      stage.addChild(bubble.view);
      bubblesRef.current.set(zone.agentId, bubble);
      
      // Wire bubble click -> open inspector
      bubble.view.on("bubble:click", (data: { agentId: AgentId; content: AgentBubbleContent }) => {
        setInspectorTarget(data.agentId);
      });
    }

    // Initialize MovementController with sprites
    movementControllerRef.current = new MovementController(spritesRef.current);
    movementControllerRef.current.setArtifactSprites(artifactSpritesRef.current);
    movementControllerRef.current.setHandoffCompleteCallback((handoffId, fromAgent, toAgent) => {
      console.log(`[OfficeScene] Handoff complete: ${fromAgent} -> ${toAgent}`);
    });

    // Art arrives asynchronously and per-entity
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

  // Subscribe to legacy pipeline events (for offer walking)
  useEffect(() => {
    return subscribeToPipelineEvents((event) => {
      pipelineRef.current?.applyEvent(event);
    });
  }, []);

  // Cleanup
  useEffect(() => {
    disposedRef.current = false;
    const sprites = spritesRef.current;
    const bubbles = bubblesRef.current;
    return () => {
      disposedRef.current = true;
      
      // Destroy sprites
      for (const sprite of sprites.values()) sprite.destroy();
      sprites.clear();
      
      // Destroy bubbles
      for (const bubble of bubbles.values()) bubble.destroy();
      bubbles.clear();
      
      // Destroy artifact sprites
      for (const artifactSprite of artifactSpritesRef.current.values()) {
        artifactSprite.destroy();
      }
      artifactSpritesRef.current.clear();
      
      // Destroy scenery
      sceneryRef.current?.destroy();
      sceneryRef.current = null;
      
      // Destroy pipeline
      pipelineRef.current?.destroy();
      pipelineRef.current = null;
      
      // Cleanup event source
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (cleanupEventBusRef.current) {
        cleanupEventBusRef.current();
        cleanupEventBusRef.current = null;
      }
      // Cleanup MovementController
      if (movementControllerRef.current) {
        movementControllerRef.current.destroy();
        movementControllerRef.current = null;
      }
    };
  }, []);

  // Render inspector panel if open
  const inspectorContent = inspectorTarget ? (
    <AgentInspector
      agentId={inspectorTarget}
      stateManager={stateManagerRef.current}
      eventBus={eventBusRef.current}
      onClose={() => setInspectorTarget(null)}
    />
  ) : null;

  return (
    <div className="flex flex-col h-full w-full">
      {/* View Mode Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card/95 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <h2 className="font-display font-medium text-foreground text-lg">Applyr Office</h2>
          <div className="flex items-center gap-1 bg-muted/50 rounded-lg p-1" role="group" aria-label="View mode">
            {(["office", "split", "terminal"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  viewMode === mode
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
                aria-pressed={viewMode === mode}
              >
                {mode === "office" && "🏢 Office"}
                {mode === "split" && "⟳ Split"}
                {mode === "terminal" && "💻 Terminal"}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            Live
          </span>
          <span className="px-2 py-0.5 bg-muted rounded">{statuses.filter(s => s.state === "working").length} working</span>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden relative">
        {viewMode === "office" && (
          <div className="h-full w-full flex items-center justify-center">
            <div 
              className="transition-transform duration-200 ease-out"
              style={{ transform: `scale(${sceneScale})` }}
            >
              <PixiStage width={SCENE_WIDTH} height={SCENE_HEIGHT} onReady={handleReady} />
            </div>
          </div>
        )}

        {viewMode === "terminal" && (
          <div className="h-full w-full">
            <TerminalPanel eventBus={eventBusRef.current} />
          </div>
        )}

        {viewMode === "split" && (
          <div className="h-full w-full flex">
            <div className={`flex-1 min-w-0 ${isMobile ? "w-full" : ""}`}>
              <div 
                className="transition-transform duration-200 ease-out"
                style={{ transform: `scale(${sceneScale})` }}
              >
                <PixiStage width={SCENE_WIDTH} height={SCENE_HEIGHT} onReady={handleReady} />
              </div>
            </div>
            {!isMobile && (
              <div className="w-96 border-l border-border flex-shrink-0">
                <TerminalPanel eventBus={eventBusRef.current} />
              </div>
            )}
          </div>
        )}

        {inspectorContent}
      </div>
    </div>
  );
}