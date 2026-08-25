/**
 * In-memory Event Bus — single source of truth for all Applyr events.
 * Supports multiple subscribers, event history per agent, and replay.
 * Framework-agnostic (no React, no Pixi).
 */

import type { ApplyrEvent, AgentId } from "./types";

type EventHandler = (event: ApplyrEvent) => void;

interface Subscription {
  id: string;
  handler: EventHandler;
  filter?: (event: ApplyrEvent) => boolean;
}

const MAX_HISTORY_PER_AGENT = 200;
const MAX_GLOBAL_HISTORY = 1000;

/**
 * EventBus — in-memory pub/sub with history.
 * Single instance per app (singleton pattern via getInstance()).
 */
export class EventBus {
  private static instance: EventBus | null = null;
  private subscriptions: Map<string, Subscription> = new Map();
  private agentHistory: Map<AgentId, ApplyrEvent[]> = new Map();
  private globalHistory: ApplyrEvent[] = [];

  private constructor() {}

  static getInstance(): EventBus {
    if (!EventBus.instance) {
      EventBus.instance = new EventBus();
    }
    return EventBus.instance;
  }

  /** Subscribe to all events (optionally filtered) */
  subscribe(handler: EventHandler, filter?: (event: ApplyrEvent) => boolean): string {
    const id = crypto.randomUUID();
    this.subscriptions.set(id, { id, handler, filter });
    return id;
  }

  /** Subscribe to events for a specific agent */
  subscribeToAgent(agentId: AgentId, handler: EventHandler): string {
    return this.subscribe(handler, (event) => event.agent_id === agentId);
  }

  /** Subscribe to events of a specific type */
  subscribeToType(type: string, handler: EventHandler): string {
    return this.subscribe(handler, (event) => event.type === type);
  }

  /** Unsubscribe */
  unsubscribe(id: string): boolean {
    return this.subscriptions.delete(id);
  }

  /** Emit an event to all matching subscribers */
  emit(event: ApplyrEvent): void {
    // Add to global history
    this.globalHistory.push(event);
    if (this.globalHistory.length > MAX_GLOBAL_HISTORY) {
      this.globalHistory.shift();
    }

    // Add to agent-specific history
    const agentHistory = this.agentHistory.get(event.agent_id) ?? [];
    agentHistory.push(event);
    if (agentHistory.length > MAX_HISTORY_PER_AGENT) {
      agentHistory.shift();
    }
    this.agentHistory.set(event.agent_id, agentHistory);

    // Deliver to subscribers
    for (const sub of this.subscriptions.values()) {
      if (!sub.filter || sub.filter(event)) {
        try {
          sub.handler(event);
        } catch (error) {
          console.error(`[EventBus] Subscriber ${sub.id} error:`, error);
        }
      }
    }
  }

  /** Get event history for a specific agent */
  getAgentHistory(agentId: AgentId): ApplyrEvent[] {
    return [...(this.agentHistory.get(agentId) ?? [])];
  }

  /** Get global event history (most recent first) */
  getGlobalHistory(limit?: number): ApplyrEvent[] {
    const history = [...this.globalHistory].reverse();
    return limit ? history.slice(0, limit) : history;
  }

  /** Get events by type across all agents */
  getEventsByType(type: string, limit?: number): ApplyrEvent[] {
    const filtered = this.globalHistory.filter((e) => e.type === type);
    return limit ? filtered.slice(-limit) : filtered;
  }

  /** Get events by correlation ID (handoff chain, etc.) */
  getEventsByCorrelation(correlationId: string): ApplyrEvent[] {
    return this.globalHistory.filter((e) => e.correlation_id === correlationId);
  }

  /** Clear all history */
  clearHistory(): void {
    this.agentHistory.clear();
    this.globalHistory = [];
  }

  /** Get subscriber count (for debugging) */
  getSubscriberCount(): number {
    return this.subscriptions.size;
  }
}

/**
 * React-friendly hook for subscribing to EventBus.
 * Usage in components:
 *   const events = useEventBus((e) => e.type === "agent.started");
 *   useEffect(() => bus.subscribeToAgent("recruiter", handleEvent), []);
 */
export function createEventBusHook() {
  const bus = EventBus.getInstance();

  return {
    subscribe: (handler: EventHandler, filter?: (event: ApplyrEvent) => boolean) =>
      bus.subscribe(handler, filter),
    subscribeToAgent: (agentId: AgentId, handler: EventHandler) =>
      bus.subscribeToAgent(agentId, handler),
    subscribeToType: (type: string, handler: EventHandler) =>
      bus.subscribeToType(type, handler),
    unsubscribe: (id: string) => bus.unsubscribe(id),
    emit: (event: ApplyrEvent) => bus.emit(event),
    getAgentHistory: (agentId: AgentId) => bus.getAgentHistory(agentId),
    getGlobalHistory: (limit?: number) => bus.getGlobalHistory(limit),
    getEventsByType: (type: string, limit?: number) => bus.getEventsByType(type, limit),
    getEventsByCorrelation: (correlationId: string) => bus.getEventsByCorrelation(correlationId),
  };
}

/**
 * SSE Event Parser — converts SSE message data to ApplyrEvent
 */
export function parseSSEEvent(data: string): ApplyrEvent | null {
  try {
    return JSON.parse(data) as ApplyrEvent;
  } catch {
    return null;
  }
}

/**
 * Connects an EventSource to the EventBus
 */
export function connectEventSourceToBus(
  eventSource: EventSource,
  bus: EventBus = EventBus.getInstance()
): () => void {
  eventSource.onmessage = (message) => {
    const event = parseSSEEvent(message.data);
    if (event) {
      bus.emit(event);
    }
  };

  eventSource.onerror = (error) => {
    console.warn("[EventBus] SSE connection error:", error);
  };

  return () => {
    eventSource.close();
  };
}