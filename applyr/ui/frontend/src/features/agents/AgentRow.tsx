import { motion, useReducedMotion } from "framer-motion";
import { AgentCard } from "./AgentCard";
import type { AgentStatus } from "./types";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0 },
};

export function AgentRow({ statuses }: { statuses: AgentStatus[] }) {
  const prefersReducedMotion = useReducedMotion();

  return (
    <motion.div
      className="flex flex-wrap justify-center gap-4"
      variants={prefersReducedMotion ? undefined : container}
      initial={prefersReducedMotion ? undefined : "hidden"}
      animate={prefersReducedMotion ? undefined : "show"}
    >
      {statuses.map((status) => (
        <motion.div key={status.agentId} variants={prefersReducedMotion ? undefined : item}>
          <AgentCard status={status} />
        </motion.div>
      ))}
    </motion.div>
  );
}
