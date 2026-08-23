// Mirrors applyr/config.py's TOPIC_LABELS — duplicated here as a small static
// constant rather than added to GET /api/settings' response, since these are
// fixed English display strings with no reason to round-trip over the wire.
export const TOPIC_LABELS: Record<string, string> = {
  tech_stack: "Tech Stack",
  education: "Education",
  english: "English",
  experience: "Experience",
  projects: "Own Projects",
  cultural_fit: "Cultural Fit",
};
