import { useEffect, useRef, useState } from "react";
import { AgentCard } from "./AgentCard";
import { useHandoffEvents } from "@/hooks/useApplyrEvents";
import type { AgentId, AgentStatus } from "./types";

type AgentFlowDiagramProps = {
  statuses: AgentStatus[];
};

type Anchor = { x: number; y: number };
type Anchors = Partial<Record<AgentId, Anchor>>;

/** The real pipeline order — the only pairs a connecting line (and a pulse) can exist for. */
const SEGMENTS: Array<[AgentId, AgentId]> = [
  ["recruiter", "matching"],
  ["matching", "cv"],
  ["cv", "ats"],
  ["ats", "application"],
];

function segmentKey(from: AgentId, to: AgentId): string {
  return `${from}-${to}`;
}

const PULSE_DURATION_MS = 900;

type Pulse = { id: string; from: AgentId; to: AgentId };

export function AgentFlowDiagram({ statuses }: AgentFlowDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<Partial<Record<AgentId, HTMLDivElement | null>>>({});
  const [anchors, setAnchors] = useState<Anchors>({});
  const [pulses, setPulses] = useState<Pulse[]>([]);

  const statusByAgent = Object.fromEntries(statuses.map((s) => [s.agentId, s])) as Record<
    AgentId,
    AgentStatus
  >;

  useEffect(() => {
    function recalc() {
      const container = containerRef.current;
      if (!container) return;
      const containerRect = container.getBoundingClientRect();
      const next: Anchors = {};
      for (const [agentId, el] of Object.entries(cardRefs.current)) {
        if (!el) continue;
        const rect = el.getBoundingClientRect();
        next[agentId as AgentId] = {
          x: rect.left + rect.width / 2 - containerRect.left,
          y: rect.top + rect.height / 2 - containerRect.top,
        };
      }
      setAnchors(next);
    }

    recalc();
    const observer = new ResizeObserver(recalc);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const { subscribe, unsubscribe } = useHandoffEvents();
  useEffect(() => {
    const id = subscribe((event) => {
      if (event.type !== "handoff.started" && event.type !== "handoff.completed") return;
      const { from_agent, to_agent } = event.payload;
      const isRealSegment = SEGMENTS.some(([f, t]) => f === from_agent && t === to_agent);
      if (!isRealSegment) return;

      const pulseId = `${event.correlation_id}-${event.type}`;
      setPulses((prev) => [...prev, { id: pulseId, from: from_agent, to: to_agent }]);
      setTimeout(() => {
        setPulses((prev) => prev.filter((p) => p.id !== pulseId));
      }, PULSE_DURATION_MS);
    });
    return () => unsubscribe(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function assignRef(agentId: AgentId) {
    return (el: HTMLDivElement | null) => {
      cardRefs.current[agentId] = el;
    };
  }

  return (
    <div ref={containerRef} className="relative grid grid-cols-[1fr_1fr_auto] grid-rows-2 items-center gap-x-16 gap-y-10 p-8">
      <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
        {SEGMENTS.map(([from, to]) => {
          const a = anchors[from];
          const b = anchors[to];
          if (!a || !b) return null;
          return (
            <line
              key={segmentKey(from, to)}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="var(--ring)"
              strokeOpacity={0.45}
              strokeWidth={2.5}
              strokeDasharray="6 6"
            />
          );
        })}
        {pulses.map((pulse) => {
          const a = anchors[pulse.from];
          const b = anchors[pulse.to];
          if (!a || !b) return null;
          return (
            <circle key={pulse.id} r={5} fill="var(--success)">
              <animateMotion
                dur={`${PULSE_DURATION_MS}ms`}
                repeatCount="1"
                fill="freeze"
                path={`M${a.x},${a.y} L${b.x},${b.y}`}
              />
            </circle>
          );
        })}
      </svg>

      <div ref={assignRef("recruiter")} className="col-start-1 row-start-1 justify-self-center">
        <AgentCard status={statusByAgent.recruiter} variant="detailed" />
      </div>
      <div ref={assignRef("matching")} className="col-start-2 row-start-1 justify-self-center">
        <AgentCard status={statusByAgent.matching} variant="detailed" />
      </div>
      <div ref={assignRef("cv")} className="col-start-1 row-start-2 justify-self-center">
        <AgentCard status={statusByAgent.cv} variant="detailed" />
      </div>
      <div ref={assignRef("ats")} className="col-start-2 row-start-2 justify-self-center">
        <AgentCard status={statusByAgent.ats} variant="detailed" />
      </div>
      <div ref={assignRef("application")} className="col-start-3 row-span-2 row-start-1 justify-self-center self-center">
        <AgentCard status={statusByAgent.application} variant="detailed" />
      </div>
    </div>
  );
}
