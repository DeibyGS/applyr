import { useEffect, useRef, useState, useCallback } from "react";
import { EventBus } from "./event-bus";
import { AgentStateManager, type AgentStateSnapshot } from "./agent-state-machine";
import type { AgentId, ApplyrEvent, WorkArtifact } from "./types";
import { VISUAL_PROPS, ARTIFACT_ICONS, ARTIFACT_LABELS } from "./types";

interface AgentInspectorProps {
  agentId: AgentId;
  stateManager: AgentStateManager;
  eventBus: EventBus;
  onClose: () => void;
}

type InspectorTab = "overview" | "events" | "artifact" | "output";

const TABS: { id: InspectorTab; label: string; icon: string }[] = [
  { id: "overview", label: "Overview", icon: "📋" },
  { id: "events", label: "Events", icon: "📜" },
  { id: "artifact", label: "Artifact", icon: "📦" },
  { id: "output", label: "Output", icon: "📄" },
];

/** Persisted tab state key */
const INSPECTOR_TAB_KEY = "applyr-inspector-tabs";

function getPersistedTabs(): Record<AgentId, InspectorTab> {
  try {
    const stored = localStorage.getItem(INSPECTOR_TAB_KEY);
    if (stored) return JSON.parse(stored);
  } catch {}
  return {} as Record<AgentId, InspectorTab>;
}

function setPersistedTab(agentId: AgentId, tab: InspectorTab): void {
  try {
    const tabs = getPersistedTabs();
    tabs[agentId] = tab;
    localStorage.setItem(INSPECTOR_TAB_KEY, JSON.stringify(tabs));
  } catch {}
}

/**
 * Agent Inspector — side panel with detailed agent context.
 * 
 * Features:
 * - Tabbed view: Overview | Events | Artifact | Output
 * - Keyboard navigation: ESC to close, ←/→ for tabs
 * - Tab persistence per agent (localStorage)
 * - Real-time event updates while open
 * - Smooth slide-in animation
 */
export function AgentInspector({
  agentId,
  stateManager,
  eventBus,
  onClose,
}: AgentInspectorProps) {
  const snapshotRef = useRef<AgentStateSnapshot | null>(null);
  const [activeTab, setActiveTab] = useState<InspectorTab>(() => 
    getPersistedTabs()[agentId] || "overview"
  );
  const [events, setEvents] = useState<ApplyrEvent[]>([]);
  const [isAnimating, setIsAnimating] = useState(true);

  // Load initial data
  useEffect(() => {
    const snapshot = stateManager.getMachine(agentId)?.getSnapshot();
    if (snapshot) {
      snapshotRef.current = snapshot;
    }
    const history = eventBus.getAgentHistory(agentId);
    setEvents(history.slice().reverse().slice(0, 50));
    setIsAnimating(false);
  }, [agentId, stateManager, eventBus]);

  // Subscribe to real-time events for this agent
  useEffect(() => {
    const subId = eventBus.subscribeToAgent(agentId, (event) => {
      setEvents((prev) => [event, ...prev].slice(0, 50));
      // Update snapshot from state manager
      const snapshot = stateManager.getMachine(agentId)?.getSnapshot();
      if (snapshot) snapshotRef.current = snapshot;
    });
    return () => {
      eventBus.unsubscribe(subId);
    };
  }, [agentId, eventBus, stateManager]);

  // Persist active tab
  useEffect(() => {
    setPersistedTab(agentId, activeTab);
  }, [agentId, activeTab]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
      return;
    }
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      const currentIndex = TABS.findIndex((t) => t.id === activeTab);
      const nextIndex = e.key === "ArrowLeft" 
        ? (currentIndex - 1 + TABS.length) % TABS.length
        : (currentIndex + 1) % TABS.length;
      setActiveTab(TABS[nextIndex].id);
    }
  }, [activeTab, onClose]);

  // React-specific handler for onKeyDown prop
  const handleKeyDownReact = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    handleKeyDown(e.nativeEvent);
  }, [activeTab, onClose]);

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Focus trap for accessibility
  const panelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    panelRef.current?.focus();
  }, []);

  const snapshot = snapshotRef.current;

  if (isAnimating) return null;

  return (
    <div
      ref={panelRef}
      className="fixed right-0 top-0 h-full w-96 bg-card border-l border-border z-50 flex flex-col shadow-xl animate-in slide-in-from-right duration-200"
      role="dialog"
      aria-labelledby="inspector-title"
      tabIndex={-1}
      onKeyDown={handleKeyDownReact}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-card/95 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <span className="text-2xl" aria-hidden="true">
            {snapshot ? VISUAL_PROPS[snapshot.visualState].icon : "🤖"}
          </span>
          <div>
            <h3 id="inspector-title" className="font-display font-medium text-foreground">
              {agentId.charAt(0).toUpperCase() + agentId.slice(1)}
            </h3>
            {snapshot && (
              <span className="text-xs text-muted-foreground capitalize">
                {snapshot.visualState}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-accent rounded-md transition-colors text-muted-foreground hover:text-foreground"
          aria-label="Close inspector"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Tab Bar */}
      <div className="flex border-b border-border bg-muted/30">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 text-sm font-medium transition-all relative ${
              activeTab === tab.id
                ? "text-primary bg-background border-b-2 border-primary"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
            role="tab"
            aria-selected={activeTab === tab.id}
          >
            <span aria-hidden="true">{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4" role="tabpanel">
        {activeTab === "overview" && snapshot && <OverviewTab snapshot={snapshot} />}
        {activeTab === "events" && <EventsTab events={events} />}
        {activeTab === "artifact" && snapshot && <ArtifactTab artifact={snapshot.currentArtifact} />}
        {activeTab === "output" && snapshot && <OutputTab output={snapshot.outputSummary} />}
      </div>

      {/* Keyboard hint */}
      <div className="px-4 py-2 border-t border-border text-[11px] text-muted-foreground/60">
        <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">Esc</kbd> Close &nbsp;
        <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">←</kbd><kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">→</kbd> Tabs
      </div>
    </div>
  );
}

/** Overview Tab — Current state, task, command, timestamps */
function OverviewTab({ snapshot }: { snapshot: AgentStateSnapshot }) {
  const props = VISUAL_PROPS[snapshot.visualState];

  return (
    <div className="space-y-4">
      {/* State Badge */}
      <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
        <span className="text-3xl" aria-hidden="true">{props.icon}</span>
        <div>
          <p className="font-medium text-foreground capitalize">{snapshot.visualState}</p>
          <p className="text-xs text-muted-foreground">{props.bubblePrefix}</p>
        </div>
      </div>

      {/* Current Task */}
      {snapshot.currentTask && (
        <div className="space-y-1.5">
          <h4 className="font-medium text-sm text-muted-foreground">Current Task</h4>
          <p className="text-sm text-foreground">{snapshot.currentTask}</p>
        </div>
      )}

      {/* Current Command */}
      {snapshot.currentCommand && (
        <div className="space-y-1.5">
          <h4 className="font-medium text-sm text-muted-foreground">Command</h4>
          <code className="text-xs bg-muted p-2 rounded block font-mono break-all">
            {snapshot.currentCommand}
          </code>
        </div>
      )}

      {/* Timestamps */}
      <div className="space-y-1.5 pt-2 border-t border-border">
        <h4 className="font-medium text-sm text-muted-foreground">Timestamps</h4>
        <dl className="text-xs text-muted-foreground space-y-1 grid grid-cols-2 gap-x-4">
          {snapshot.timestamps.startedAt && (
            <>
              <dt>Started</dt>
              <dd className="font-mono">{formatTime(snapshot.timestamps.startedAt)}</dd>
            </>
          )}
          {snapshot.timestamps.completedAt && (
            <>
              <dt>Completed</dt>
              <dd className="font-mono">{formatTime(snapshot.timestamps.completedAt)}</dd>
            </>
          )}
          {snapshot.timestamps.lastTransitionAt && (
            <>
              <dt>Last Transition</dt>
              <dd className="font-mono">{formatTime(snapshot.timestamps.lastTransitionAt)}</dd>
            </>
          )}
        </dl>
      </div>
    </div>
  );
}

/** Events Tab — Chronological event history */
function EventsTab({ events }: { events: ApplyrEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
        No events yet
      </div>
    );
  }

  return (
    <div className="max-h-96 overflow-auto space-y-1">
      {events.map((event, idx) => (
        <EventRow key={idx} event={event} index={idx} />
      ))}
    </div>
  );
}

function EventRow({ event, index }: { event: ApplyrEvent; index: number }) {
  const isAgentEvent = event.type.startsWith("agent.");
  const isHandoffEvent = event.type.startsWith("handoff.");
  const colorClass = isHandoffEvent 
    ? "text-amber-400" 
    : isAgentEvent 
      ? "text-primary" 
      : "text-muted-foreground";

  return (
    <div className="text-[11px] font-mono text-muted-foreground flex gap-2 items-start px-2 py-1 hover:bg-muted/50 rounded">
      <span className="opacity-50 w-16 shrink-0">
        {formatTime(event.timestamp)}
      </span>
      <span className={`${colorClass} shrink-0`}>{event.type}</span>
      <span className="flex-1 min-w-0 truncate">
        {event.payload ? formatPayload(event.payload) : ""}
      </span>
    </div>
  );
}

function formatPayload(payload: any): string {
  if (!payload) return "";
  if (typeof payload === "string") return payload;
  try {
    return JSON.stringify(payload).slice(0, 120);
  } catch {
    return String(payload).slice(0, 120);
  }
}

/** Artifact Tab — Current artifact details */
function ArtifactTab({ artifact }: { artifact: WorkArtifact | null }) {
  if (!artifact) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
        No artifact currently held
      </div>
    );
  }

  const icon = ARTIFACT_ICONS[artifact.type];
  const label = ARTIFACT_LABELS[artifact.type];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
        <span className="text-3xl" aria-hidden="true">{icon}</span>
        <div>
          <p className="font-medium text-foreground">{label}</p>
          <p className="text-xs text-muted-foreground">Type: {artifact.type}</p>
        </div>
      </div>

      <div className="bg-muted p-3 rounded text-xs font-mono max-h-64 overflow-auto">
        {JSON.stringify(artifact, null, 2)}
      </div>
    </div>
  );
}

/** Output Tab — Recent command output */
function OutputTab({ output }: { output: string | null }) {
  if (!output) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground text-sm">
        No recent output
      </div>
    );
  }

  return (
    <div className="bg-muted p-3 rounded max-h-96 overflow-auto">
      <code className="text-xs font-mono block whitespace-pre-wrap">{output}</code>
    </div>
  );
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return iso;
  }
}