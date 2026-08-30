/**
 * React hook for subscribing to Applyr enriched event stream (SSE).
 * Provides unified access to agent lifecycle events, handoffs, and pipeline stages.
 *
 * SSE connection is a singleton — multiple hook instances share one EventSource
 * and one EventBus, avoiding duplicate events in the history store.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { API_BASE } from "@/api/client";
import type { ApplyrEvent, AgentId } from "@/lib/applyr-events";
import { EventBus, connectEventSourceToBus } from "@/lib/event-bus";

// ---------------------------------------------------------------------------
// Singleton SSE connection — shared across all hook instances
// ---------------------------------------------------------------------------

const ENRICHED_ENDPOINT = "/api/events/enriched";

let sharedEventSource: EventSource | null = null;
let sharedCleanup: (() => void) | null = null;
let sharedRefCount = 0;
let sharedConnected = false;
const sharedListeners = new Set<() => void>();

function notifySharedListeners() {
  for (const fn of sharedListeners) fn();
}

function ensureSharedConnection(): () => void {
  if (sharedEventSource) return () => {};

  const url = `${API_BASE}${ENRICHED_ENDPOINT}`;
  const es = new EventSource(url);
  sharedEventSource = es;

  es.onopen = () => {
    sharedConnected = true;
    notifySharedListeners();
  };

  es.onerror = () => {
    sharedConnected = false;
    notifySharedListeners();
  };

  const bus = EventBus.getInstance();
  sharedCleanup = connectEventSourceToBus(es, bus);
  sharedRefCount = 1;

  return () => {};
}

function refSharedConnection() {
  if (sharedEventSource) {
    sharedRefCount++;
    return;
  }
  ensureSharedConnection();
}

function unrefSharedConnection() {
  sharedRefCount--;
  if (sharedRefCount <= 0 && sharedEventSource) {
    sharedEventSource.close();
    sharedEventSource = null;
    if (sharedCleanup) {
      sharedCleanup();
      sharedCleanup = null;
    }
    sharedConnected = false;
    sharedRefCount = 0;
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

interface UseApplyrEventsOptions {
  eventTypes?: string[];
  agentIds?: AgentId[];
  autoConnect?: boolean;
  endpoint?: string;
}

interface UseApplyrEventsReturn {
  events: ApplyrEvent[];
  getAgentEvents: (agentId: AgentId) => ApplyrEvent[];
  getCorrelationEvents: (correlationId: string) => ApplyrEvent[];
  subscribe: (handler: (event: ApplyrEvent) => void, filter?: (event: ApplyrEvent) => boolean) => string;
  unsubscribe: (id: string) => void;
  clear: () => void;
  connected: boolean;
  connect: () => void;
  disconnect: () => void;
}

export function useApplyrEvents(options: UseApplyrEventsOptions = {}): UseApplyrEventsReturn {
  const { eventTypes, agentIds, autoConnect = true } = options;

  const bus = EventBus.getInstance();
  const subscriptionsRef = useRef<Map<string, () => void>>(new Map());
  const [events, setEvents] = useState<ApplyrEvent[]>([]);
  const [connected, setConnected] = useState(sharedConnected);

  const filterRef = useRef<(event: ApplyrEvent) => boolean>((event) => {
    if (eventTypes && eventTypes.length > 0 && !eventTypes.includes(event.type)) return false;
    if (agentIds && agentIds.length > 0 && !agentIds.includes(event.agent_id)) return false;
    return true;
  });

  useEffect(() => {
    filterRef.current = (event) => {
      if (eventTypes && eventTypes.length > 0 && !eventTypes.includes(event.type)) return false;
      if (agentIds && agentIds.length > 0 && !agentIds.includes(event.agent_id)) return false;
      return true;
    };
  }, [eventTypes, agentIds]);

  const handleEvent = useCallback((event: ApplyrEvent) => {
    if (!filterRef.current(event)) return;
    setEvents((prev) => [event, ...prev].slice(0, 500));
  }, []);

  const connect = useCallback(() => {
    refSharedConnection();

    const subId = bus.subscribe(handleEvent, filterRef.current);
    subscriptionsRef.current.set("main", () => bus.unsubscribe(subId));

    setConnected(sharedConnected);

    const listenerId = crypto.randomUUID();
    const listener = () => setConnected(sharedConnected);
    sharedListeners.add(listener);

    subscriptionsRef.current.set("_shared_listener", () => {
      sharedListeners.delete(listener);
    });
    void listenerId;
  }, [bus, handleEvent]);

  const disconnect = useCallback(() => {
    for (const cleanup of subscriptionsRef.current.values()) {
      cleanup();
    }
    subscriptionsRef.current.clear();
    unrefSharedConnection();
    setConnected(false);
  }, []);

  useEffect(() => {
    if (autoConnect) connect();
    return () => disconnect();
  }, [autoConnect, connect, disconnect]);

  const subscribe = useCallback(
    (handler: (event: ApplyrEvent) => void, filter?: (event: ApplyrEvent) => boolean) => {
      const id = bus.subscribe(handler, filter);
      subscriptionsRef.current.set(id, () => bus.unsubscribe(id));
      return id;
    },
    [bus],
  );

  const unsubscribe = useCallback(
    (id: string) => {
      const cleanup = subscriptionsRef.current.get(id);
      if (cleanup) {
        cleanup();
        subscriptionsRef.current.delete(id);
      } else {
        bus.unsubscribe(id);
      }
    },
    [bus],
  );

  const clear = useCallback(() => {
    setEvents([]);
    bus.clearHistory();
  }, [bus]);

  const getAgentEvents = useCallback((agentId: AgentId) => bus.getAgentHistory(agentId), [bus]);
  const getCorrelationEvents = useCallback(
    (correlationId: string) => bus.getEventsByCorrelation(correlationId),
    [bus],
  );

  return {
    events,
    getAgentEvents,
    getCorrelationEvents,
    subscribe,
    unsubscribe,
    clear,
    connected,
    connect,
    disconnect,
  };
}

export function useAgentEvents(agentId: AgentId) {
  return useApplyrEvents({ agentIds: [agentId] });
}

export function useHandoffEvents() {
  return useApplyrEvents({
    eventTypes: ["handoff.started", "handoff.walking", "handoff.completed"],
  });
}

export function usePipelineEvents() {
  return useApplyrEvents({
    eventTypes: ["pipeline.stage"],
  });
}
