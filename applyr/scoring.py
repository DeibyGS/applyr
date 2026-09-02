"""Scoring engine — configurable weighted compatibility calculation and evidence evaluation."""

import json

from applyr.config import load_config
from applyr.constants import DEFAULT_TOPIC_WEIGHT
from applyr.evidence import parse_evidence, is_evidenced


def calculate_score(topics: dict) -> int:
    """Calculate weighted compatibility score from topic scores.

    Args:
        topics: dict like {"tech_stack": {"score": 80, "detail": "..."}, ...}

    Returns:
        Weighted score 0-100, or 0 if no valid topics provided.
    """
    if not topics:
        return 0

    config = load_config()
    weights = config["weights"]

    weighted_sum = 0.0
    total_weight = 0.0

    for topic, values in topics.items():
        score = values.get("score", 0)
        if not isinstance(score, (int, float)) or not 0 <= score <= 100:
            continue
        weight = weights.get(topic, DEFAULT_TOPIC_WEIGHT)
        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        return 0

    return round(weighted_sum / total_weight)


# Slash-joined names that are ONE conventional term, not alternatives — splitting
# them on "/" would produce meaningless halves ("CI" + "CD", "TCP" + "IP") that risk
# false-positive evidence matches if either half happens to appear elsewhere in
# cv-master.md out of context (found via /code-review: "IP" or "CD" alone are common
# enough short tokens to collide with unrelated text).
_SLASH_COMPOUND_TERMS = frozenset({"ci/cd", "tcp/ip", "i/o", "a/b testing", "ui/ux"})


def _parse_tech_stack(raw: str) -> list[str]:
    """Parse comma-separated tech stack respecting parenthetical groupings.

    'Python, JavaScript, LLMs (agentes, prompting, function calling), REST APIs'
    → ['Python', 'JavaScript', 'LLMs (agentes, prompting, function calling)', 'REST APIs']

    Each comma segment is then split again on top-level '/' — job postings commonly
    phrase alternatives that way ('React/Vue/Next.js', 'Node.js/Python/Go'). Without
    this second split, the compound string is checked against cv-master.md verbatim,
    which never matches even when the candidate has some (or all) of the listed
    technologies individually — confirmed live: a profile with React, Next.js and
    Python was scored "missing" on all three because the offer listed them joined by
    '/', not because the evidence wasn't there. Known conventional compounds
    (_SLASH_COMPOUND_TERMS) are exempted from this second split.

    Deduplicates while preserving order.
    """
    if not raw:
        return []
    skills = []
    depth = 0
    current: list[str] = []

    def flush_comma_segment() -> None:
        segment = "".join(current).strip()
        if not segment:
            return
        # A parenthetical grouping ("low-code/no-code (n8n/Make/Zapier)") marks the
        # whole segment as one named concept with examples, not slash-separated
        # alternatives — leave it intact rather than splitting on "/".
        if "(" in segment or segment.lower() in _SLASH_COMPOUND_TERMS:
            skills.append(segment)
            return
        for part in segment.split("/"):
            token = part.strip()
            if token:
                skills.append(token)

    for char in raw:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            flush_comma_segment()
            current = []
        else:
            current.append(char)
    flush_comma_segment()
    return list(dict.fromkeys(skills))


def evaluate_evidence(
    topics: dict,
    cv_master_text: str,
    offer_tech_stack: str | None = None,
) -> tuple[dict, list]:
    """Evaluate evidence strength for each topic against cv-master.md.

    Uses the Evidence Graph (evidence.py) for deterministic claim extraction
    and verification. No LLM calls, no fuzzy matching.

    For tech_stack: uses Evidence Graph to check each skill against cv-master.md.
    For other topics: uses the numeric score as proxy (evidence graph doesn't
    evaluate holistic fit like experience quality or cultural alignment).

    Args:
        topics: dict like {"tech_stack": {"score": 80, "detail": "..."}, ...}
        cv_master_text: full text of cv-master.md
        offer_tech_stack: comma-separated tech stack from the offer

    Returns:
        Tuple of (evidence_by_topic, parsed_claims) where parsed_claims can
        be reused by the caller to avoid double-parsing.
    """
    if not topics or not cv_master_text:
        return {}, []

    claims = parse_evidence(cv_master_text)
    result = {}

    for topic, values in topics.items():
        score = values.get("score", 0)
        detail = values.get("detail", "")

        evaluation = {
            "score": score,
            "evidence_status": "missing",
            "evidence": [],
            "missing": [],
            "rationale": detail,
        }

        if topic == "tech_stack":
            if offer_tech_stack:
                skills = _parse_tech_stack(offer_tech_stack)
                for skill in skills:
                    if is_evidenced(skill, claims):
                        evaluation["evidence"].append(skill)
                    else:
                        evaluation["missing"].append(skill)

                if evaluation["evidence"] and not evaluation["missing"]:
                    evaluation["evidence_status"] = "strong"
                elif evaluation["evidence"] and evaluation["missing"]:
                    evaluation["evidence_status"] = "weak"
                else:
                    evaluation["evidence_status"] = "missing"
            else:
                # No tech stack string provided — fall back to score heuristic
                if score >= 80:
                    evaluation["evidence_status"] = "strong"
                elif score >= 50:
                    evaluation["evidence_status"] = "weak"

        elif topic in ("experience", "projects", "education", "english", "cultural_fit"):
            if score >= 80:
                evaluation["evidence_status"] = "strong"
            elif score >= 50:
                evaluation["evidence_status"] = "weak"
            else:
                evaluation["evidence_status"] = "missing"

        result[topic] = evaluation

    return result, claims


def build_tailoring_plan(
    offer: dict,
    topics: dict,
    cv_master_text: str,
) -> dict:
    """Build a CV tailoring plan from offer data and evidence evaluation.

    Args:
        offer: dict with title, company, tech_stack, seniority_level, etc.
        topics: dict of topic scores from the matcher
        cv_master_text: full text of cv-master.md

    Returns:
        CVTailoringPlan dict ready for JSON serialization.
    """
    tech_stack = offer.get("tech_stack") or ""
    evidence, claims = evaluate_evidence(topics, cv_master_text, tech_stack)

    # Build requirements list from evidence
    requirements = []
    for topic, ev in evidence.items():
        importance = "critical" if ev["score"] >= 80 else "high" if ev["score"] >= 60 else "medium"
        req_type = "technical" if topic == "tech_stack" else "experience" if topic == "experience" else "other"
        cv_action = "highlight" if ev["evidence_status"] == "strong" else "include" if ev["evidence_status"] == "weak" else "omit"
        requirements.append({
            "requirement": topic,
            "importance": importance,
            "type": req_type,
            "evidence_status": ev["evidence_status"],
            "evidence": ev["evidence"],
            "missing": ev["missing"],
            "cv_action": cv_action,
        })

    # Build evidence map from tech stack — reuse parsed claims, no double parse
    evidence_map = {}
    if tech_stack:
        skills = _parse_tech_stack(tech_stack)
        # Use evidence/missing lists from evaluate_evidence for correct classification
        tech_eval = evidence.get("tech_stack", {})
        strong_set = set(tech_eval.get("evidence", []))
        for skill in skills:
            if skill in strong_set:
                evidence_map[skill] = {
                    "evidence_status": "strong",
                    "sources": ["cv-master.md"],
                }
            else:
                evidenced = is_evidenced(skill, claims) if claims else False
                evidence_map[skill] = {
                    "evidence_status": "strong" if evidenced else "missing",
                    "sources": ["cv-master.md"] if evidenced else [],
                }

    # Build forbidden claims from missing evidence
    forbidden_claims = []
    for req in requirements:
        for missing in req.get("missing", []):
            forbidden_claims.append(f"{missing} experience")

    # Summary strategy
    strong_topics = [t for t, e in evidence.items() if e["evidence_status"] == "strong"]
    summary_strategy = {
        "positioning": f"{offer.get('seniority_level') or 'experienced'} {offer.get('role_category') or 'engineer'}",
        "must_include": strong_topics[:3],
        "avoid": ["generic soft skills", "unrelated technologies"],
    }

    # Experience strategy
    experience_strategy = []
    for req in requirements:
        if req["evidence_status"] in ("strong", "weak"):
            experience_strategy.append({
                "requirement": req["requirement"],
                "priority": "high" if req["importance"] == "critical" else "medium",
                "emphasize": req["evidence"],
                "deemphasize": req["missing"],
            })

    plan = {
        "version": "1.0",
        "target_role": offer.get("title", ""),
        "company": offer.get("company", ""),
        "requirements": requirements,
        "evidence_map": evidence_map,
        "forbidden_claims": forbidden_claims,
        "summary_strategy": summary_strategy,
        "experience_strategy": experience_strategy,
        "skills_strategy": {
            "core": [s for s, e in evidence_map.items() if e["evidence_status"] == "strong"],
            "secondary": [s for s, e in evidence_map.items() if e["evidence_status"] == "weak"],
            "omit": [s for s, e in evidence_map.items() if e["evidence_status"] == "missing"],
        },
        "quality_constraints": {
            "max_pages": 2 if (offer.get("seniority_level") or "") in ("senior", "lead", "director") else 1,
            "evidence_density_target": 0.9,
            "no_invented_claims": True,
            "no_keyword_stuffing": True,
        },
    }

    return plan


def tailoring_plan_to_json(plan: dict) -> str:
    """Serialize a tailoring plan to JSON string."""
    return json.dumps(plan, indent=2, ensure_ascii=False)


def tailoring_plan_from_json(json_str: str) -> dict | None:
    """Deserialize a tailoring plan from JSON string."""
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None
