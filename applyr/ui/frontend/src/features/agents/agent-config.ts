import recruiterImg from "@/assets/agents/recruiter.webp";
import matchingImg from "@/assets/agents/matching.webp";
import cvImg from "@/assets/agents/cv.webp";
import atsImg from "@/assets/agents/ats.webp";
import applicationImg from "@/assets/agents/application.webp";
import type { AgentId } from "./types";

type AgentConfig = {
  name: string;
  role: string;
  illustration: string;
};

export const AGENT_CONFIG: Record<AgentId, AgentConfig> = {
  recruiter: { name: "Recruiter", role: "Reads and normalizes offers", illustration: recruiterImg },
  matching: { name: "Matching", role: "Scores compatibility", illustration: matchingImg },
  cv: { name: "CV", role: "Tailors your CV", illustration: cvImg },
  ats: { name: "ATS", role: "Checks ATS compatibility", illustration: atsImg },
  application: { name: "Application", role: "Prepares your application", illustration: applicationImg },
};
