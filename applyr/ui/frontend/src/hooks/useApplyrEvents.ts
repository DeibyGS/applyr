/**
 * React hook for subscribing to Applyr enriched event stream (SSE).
 * Provides unified access to agent lifecycle events, handoffs, and pipeline stages.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { API_BASE } from "@/api/client";
import type { ApplyrEvent, AgentId } from "@/features/office-scene/types";
import { EventBus, connectEventSourceToBus } from "@/features/office-scene/event-bus";

interface UseApplyrEventsOptions {
  /** Event types to subscribe to (default: all) */
  eventTypes?: string[];
  /** Agent IDs to subscribe to (default: all) */
  agentIds?: AgentId[];
  /** Whether to auto-connect on mount (default: true) */
  autoConnect?: boolean;
  /** SSE endpoint (default: /api/events/enriched) */
  endpoint?: string;
}

interface UseApplyrEventsReturn {
  /** Latest events (global, most recent first) */
  events: ApplyrEvent[];
  /** Events for a specific agent */
  getAgentEvents: (agentId: AgentId) => ApplyrEvent[];
  /** Events by correlation ID (handoff chains) */
  getCorrelationEvents: (correlationId: string) => ApplyrEvent[];
  /** Subscribe to events with a callback */
  subscribe: (handler: (event: ApplyrEvent) => void, filter?: (event: ApplyrEvent) => boolean) => string;
  /** Unsubscribe */
  unsubscribe: (id: string) => void;
  /** Clear local event buffer */
  clear: () => void;
  /** Connection status */
  connected: boolean;
  /** Manually connect */
  connect: () => void;
  /** Manually disconnect */
  disconnect: () => void;
}

/**
 * Hook for consuming Applyr enriched events via SSE + EventBus.
 * The EventBus is a singleton — multiple components share the same event stream.
 */
export function useApplyrEvents(options: UseApplyrEventsOptions = {}): UseApplyrEventsReturn {
  const {
    eventTypes,
    agentIds,
    autoConnect = true,
    endpoint = "/api/events/enriched",
  } = options;

  const bus = EventBus.getInstance();
  const eventSourceRef = useRef<EventSource | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const subscriptionsRef = useRef<Map<string, () => void>>(new Map());

  const [events, setEvents] = useState<ApplyrEvent[]>([]);
  const [connected, setConnected] = useState(false);

  // Build filter function
  const filterRef = useRef<(event: ApplyrEvent) => boolean>((event) => {
    if (eventTypes && eventTypes.length > 0 && !eventTypes.includes(event.type)) {
      return false;
    }
    if (agentIds && agentIds.length > 0 && !agentIds.includes(event.agent_id)) {
      return false;
    }
    return true;
  });

  // Update filter when options change
  useEffect(() => {
    filterRef.current = (event) => {
      if (eventTypes && eventTypes.length > 0 && !eventTypes.includes(event.type)) {
        return false;
      }
      if (agentIds && agentIds.length > 0 && !agentIds.includes(event.agent_id)) {
        return false;
      }
      return true;
    };
  }, [eventTypes, agentIds]);

  // Handle new events from EventBus
  const handleEvent = useCallback((event: ApplyrEvent) => {
    if (!filterRef.current(event)) return;

    setEvents((prev) => {
      // Keep most recent first, limit to 500
      const next = [event, ...prev].slice(0, 500);
      return next;
    });
  }, []);

  // Connect to SSE
  const connect = useCallback(() => {
    if (eventSourceRef.current) return; // Already connected

    const url = `${API_BASE}${endpoint}`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setConnected(true);
    };

    eventSource.onerror = () => {
      setConnected(false);
      // EventSource auto-reconnects; we don't need to manually reconnect
    };

    // Pipe events into EventBus
    cleanupRef.current = connectEventSourceToBus(eventSource, bus);

    // Also subscribe to EventBus for filtered events
    const subId = bus.subscribe(handleEvent, filterRef.current);
    subscriptionsRef.current.set("main", () => bus.unsubscribe(subId));
  }, [bus, endpoint, handleEvent]);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (cleanupRef.current) {
      cleanupRef.current();
      cleanupRef.current = null;
    }
    for (const cleanup of subscriptionsRef.current.values()) {
      cleanup();
    }
    subscriptionsRef.current.clear();
    setConnected(false);
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  // Subscribe/unsubscribe helpers for components
  const subscribe = useCallback(
    (handler: (event: ApplyrEvent) => void, filter?: (event: ApplyrEvent) => boolean) => {
      const id = bus.subscribe(handler, filter);
      subscriptionsRef.current.set(id, () => bus.unsubscribe(id));
      return id;
    },
    [bus]
  );

  const unsubscribe = useCallback((id: string) => {
    const cleanup = subscriptionsRef.current.get(id);
    if (cleanup) {
      cleanup();
      subscriptionsRef.current.delete(id);
    } else {
      bus.unsubscribe(id);
    }
  }, [bus]);

  const clear = useCallback(() => {
    setEvents([]);
    bus.clearHistory();
  }, [bus]);

  const getAgentEvents = useCallback(
    (agentId: AgentId) => {
      return bus.getAgentHistory(agentId);
    },
    [bus]
  );

  const getCorrelationEvents = useCallback(
    (correlationId: string) => {
      return bus.getEventsByCorrelation(correlationId);
    },
    [bus]
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

/**
 * Hook for a specific agent's events — convenience wrapper
 */
export function useAgentEvents(agentId: AgentId) {
  return useApplyrEvents({ agentIds: [agentId] });
}

/**
 * Hook for handoff events — convenience wrapper
 */
export function useHandoffEvents() {
  return useApplyrEvents({
    eventTypes: ["handoff.started", "handoff.walking", "handoff.completed"],
  });
}

/**
 * Hook for pipeline stage events — convenience wrapper
 */
export function usePipelineEvents() {
  return useApplyrEvents({
    eventTypes: ["pipeline.stage"],
  });
}