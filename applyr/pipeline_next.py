"""`applyr next` state machine and the `--record` review history (ADR-015).

The pipeline order used to live only in AGENT_INSTRUCTIONS prose. `derive_next`
turns it into one deterministic answer per offer, derived from what applyr
already stores on every call — it never persists a stage of its own (and never
touches `pipeline_stage`, which belongs to the Visual UI branch, ADR-013).

The two steps an agent executes itself (`cv review-blind`, `cv review`) leave a
trace only through `--record`, appended to `offers.cv_iteration_history`.
"""

import json
from collections.abc import Callable
from datetime import datetime, timezone

from applyr.constants import CV_REVIEW_MAX_ITERATIONS, CV_REVIEW_MINOR_MIN, CV_REVIEW_READY_MIN
from applyr.errors import die
from applyr.eligibility import block_reason, load_stored
from applyr.scoring import recommendation_for

# Statuses past the point where there is a next pipeline step to take.
DONE_STATUSES = frozenset({"applied", "waiting", "in_process", "offer", "rejected", "discarded"})

_BLIND_VERDICTS = {"apply": "STRONG_MATCH", "maybe": "CLOSE_MATCH", "low_match": "NO_MATCH"}
READY_TO_SEND = "READY TO SEND"


def read_history(raw: str | None, offer_id: int) -> list[dict]:
    """Parse `cv_iteration_history`; NULL is an empty history.

    Anything else that is not a JSON list of record objects is corruption,
    reported as a structured error — never silently treated as empty, since
    the next append would then overwrite whatever was there, and never let
    through half-checked, where a stray `1` in the list would crash `next`.
    """
    if not raw:
        return []
    try:
        history = json.loads(raw)
    except json.JSONDecodeError:
        history = None
    if not isinstance(history, list) or not all(
            isinstance(e, dict) and isinstance(e.get("step"), str) and isinstance(e.get("at"), str)
            for e in history):
        die(f"Error: offer #{offer_id} has a corrupt cv_iteration_history — not a list of records.",
            code="history_corrupt", details={"offer_id": offer_id})
    return history


def review_verdict(step: str, score: int, config: dict) -> str:
    """Derive the verdict for a recorded score — never taken from the agent."""
    if step == "review_blind":
        return _BLIND_VERDICTS[recommendation_for(score, config)]
    if score >= CV_REVIEW_READY_MIN:
        return READY_TO_SEND
    if score >= CV_REVIEW_MINOR_MIN:
        return "NEEDS MINOR EDITS"
    return "NEEDS MAJOR REVISION"


def parse_record_score(raw: str) -> int:
    """Validate a `--record` value before anything is read or written."""
    try:
        score = int(raw)
    except (TypeError, ValueError):
        score = -1
    if not 0 <= score <= 100:
        die(f"Error: --record must be an integer 0-100, got: {raw}",
            code="invalid_value", details={"field": "--record", "value": raw})
    return score


def record_review(offer_id: int, step: str, score: int, config: dict) -> dict:
    """Append one review record to the offer's history and return it."""
    from applyr.db import get_conn

    conn = get_conn()
    try:
        # Take the write lock before reading: a plain read-modify-write let two
        # concurrent --record calls (a retry racing the first attempt) each append
        # to the same stale list, silently losing one entry while both reported
        # success. sqlite3's default 5 s timeout makes the second caller wait.
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT cv_iteration_history FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if not row:
            die(f"Error: offer #{offer_id} not found.", code="not_found", details={"offer_id": offer_id})
        history = read_history(row["cv_iteration_history"], offer_id)
        entry = {
            "step": step,
            "score": score,
            "verdict": review_verdict(step, score, config),
            "at": datetime.now(timezone.utc).isoformat(),  # sub-second: compared to file mtimes
        }
        history.append(entry)
        conn.execute(
            "UPDATE offers SET cv_iteration_history = ?, "
            "cv_iteration = COALESCE(cv_iteration, 0) + ? WHERE id = ?",
            (json.dumps(history), 1 if step == "cv_review" else 0, offer_id),
        )
        conn.commit()
    finally:
        conn.close()
    return entry


def _recorded_at(entry: dict) -> float:
    return datetime.fromisoformat(entry["at"]).timestamp()


def _step(state: str, command: str | None, reason: str, **extra) -> dict:
    return {"state": state, "command": command, "reason": reason,
            "needs_user_confirmation": False, "warnings": [], **extra}


def derive_next(
    offer: dict,
    topic_count: int,
    history: list[dict],
    cv_path: str | None,
    cv_mtime: float | None,
    pdf_mtime: float | None,
    verify: Callable[[], dict],
    config: dict,
) -> dict:
    """Return the next pipeline step for one offer. No I/O of its own.

    `verify` is called only once every earlier step is satisfied, so the
    common early states never pay for a verify run. Freshness is by time:
    a review or PDF older than the CV's last edit does not count (ADR-015).
    """
    offer_id = offer["id"]

    if offer["status"] in DONE_STATUSES:
        return _step("done", None, f"Status is '{offer['status']}' — nothing left in the pipeline.")

    if topic_count == 0 and not offer["compatibility_pct"]:
        return _step("score", "applyr role matcher",
                     "Offer has no score. Scores come from 'topics' at registration — re-register it "
                     "with topics following the Matcher role.")

    if not any(e.get("step") == "review_blind" for e in history):
        step = _step("decide", f"applyr cv review-blind {offer_id} --record <score>",
                     "Ask the user whether to apply. If yes, run 'applyr cv review-blind "
                     f"{offer_id}', execute its prompt, then record the score.",
                     needs_user_confirmation=True)
        eligibility = load_stored(offer.get("eligibility_result"))
        if recommendation_for(offer["compatibility_pct"] or 0, config, eligibility) == "low_match":
            # ADR-017: a knocked-out offer names the requirement it failed.
            reason = block_reason(eligibility)
            label = f"LOW MATCH (failed requirement: {reason})" if reason else "LOW MATCH"
            notes = "Failed eligibility requirement" if reason else "Below threshold"
            step["warnings"].append(
                f"{label} — suggest archiving: applyr update {offer_id} discarded --notes \"{notes}\"")
        return step

    if cv_path is None or cv_mtime is None:
        return _step("generate", f"applyr cv generate {offer_id}",
                     "Blind review recorded; no CV file exists for this offer yet.")

    reviews = [e for e in history if e.get("step") == "cv_review"]
    fresh = [e for e in reviews if _recorded_at(e) >= cv_mtime]
    review_cmd = f"applyr cv review {cv_path} --record <score>"
    if not fresh:
        return _step("cv_review", review_cmd,
                     f"No review recorded since the CV was last edited. Run 'applyr cv review {cv_path}', "
                     "execute its prompt, then record the score.")
    latest = fresh[-1]
    warnings = []
    if latest["verdict"] != READY_TO_SEND:
        if len(reviews) < CV_REVIEW_MAX_ITERATIONS:
            return _step("cv_review", review_cmd,
                         f"Last review: {latest['verdict']} ({latest['score']}). Edit the file applying its "
                         "fixes, then review again — re-reviewing an unedited file changes nothing.")
        warnings.append(f"Review limit reached ({CV_REVIEW_MAX_ITERATIONS}) with verdict "
                        f"{latest['verdict']} — moving on to verify.")

    result = verify()
    if not result.get("passed"):
        failing = [f"[{r['category']}] {r['claim']}" for r in result.get("unsupported", [])]
        return _step("verify", f"applyr cv verify {cv_path}",
                     "CV does not pass verify: remove or ground each listed claim, then re-run it.",
                     warnings=warnings, failing=failing or [result.get("unverifiable", "unverifiable")])

    if pdf_mtime is None or pdf_mtime < cv_mtime:
        return _step("pdf", f"applyr cv pdf {cv_path}",
                     "CV verified; no PDF newer than the CV next to it yet (a PDF written elsewhere "
                     "with --output is not seen).",
                     warnings=warnings)

    return _step("apply", f"applyr update {offer_id} applied --canal <channel>",
                 "PDF ready. Once the user confirms the application was sent, record it.",
                 needs_user_confirmation=True, warnings=warnings)
