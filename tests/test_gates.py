"""Plan artifact validation — the barrier in front of `cv generate` (ADR-018).

`cv generate` refuses to run without a Step 5.7 plan, so these tests pin every
way a plan can fail: absent, for another offer, empty of forbidden claims, or
not text at all. They are filesystem-only — no database is opened.
"""

import pytest

from applyr.gates import (
    PlanStatus,
    check_plan,
    declared_offer_id,
    forbidden_claims,
    plan_hint,
    plan_path_for,
    validate_plan,
)

VALID_PLAN = """---
offer_id: 1
company: "Fusuma"
---

## Forbidden claims

- Do not present RAG or LangChain as professional experience.
- Do not claim AWS — the profile has OCI only.

## Positioning
Senior fullstack, evidence only.
"""


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestValidatePlan:
    def test_valid_plan_passes(self, tmp_path):
        assert validate_plan(_write(tmp_path / "cv-a-plan.md", VALID_PLAN), 1) is PlanStatus.VALID

    def test_missing_file_is_missing(self, tmp_path):
        assert validate_plan(tmp_path / "nope.md", 1) is PlanStatus.MISSING

    def test_plan_for_another_offer_is_wrong_offer(self, tmp_path):
        """The plan is per-offer: a colleague's plan must not unlock this one."""
        assert validate_plan(_write(tmp_path / "cv-a-plan.md", VALID_PLAN), 2) \
            is PlanStatus.WRONG_OFFER

    def test_plan_without_frontmatter_is_wrong_offer(self, tmp_path):
        text = "## Forbidden claims\n- Do not invent a title.\n"
        assert validate_plan(_write(tmp_path / "cv-a-plan.md", text), 1) \
            is PlanStatus.WRONG_OFFER

    def test_no_forbidden_claims_section_is_empty(self, tmp_path):
        text = "---\noffer_id: 1\n---\n\n## Positioning\nBe honest.\n"
        assert validate_plan(_write(tmp_path / "cv-a-plan.md", text), 1) is PlanStatus.EMPTY

    def test_heading_without_bullets_is_empty(self, tmp_path):
        """A plan that forbids nothing forbids nothing — same as no plan (AC-03)."""
        text = "---\noffer_id: 1\n---\n\n## Forbidden claims\n\nWrite something honest.\n"
        assert validate_plan(_write(tmp_path / "cv-a-plan.md", text), 1) is PlanStatus.EMPTY

    def test_binary_file_is_unreadable(self, tmp_path):
        path = tmp_path / "cv-a-plan.md"
        path.write_bytes(b"\xff\xfe\x00 not utf-8")
        assert validate_plan(path, 1) is PlanStatus.UNREADABLE

    @pytest.mark.parametrize("heading", [
        "## Forbidden claims",
        "## forbidden claims",
        "### Claims prohibidas",
        "## PROHIBITED CLAIMS",
        "## Restricciones",
    ])
    def test_bilingual_headings_are_accepted(self, tmp_path, heading):
        """Instructions ship in Spanish; a Spanish plan must pass the same gate."""
        text = f'---\noffer_id: 1\n---\n\n{heading}\n- No inflar el seniority.\n'
        assert validate_plan(_write(tmp_path / "cv-a-plan.md", text), 1) is PlanStatus.VALID


class TestForbiddenClaims:
    def test_reads_every_bullet_under_the_heading(self):
        assert forbidden_claims(VALID_PLAN) == [
            "Do not present RAG or LangChain as professional experience.",
            "Do not claim AWS — the profile has OCI only.",
        ]

    def test_stops_at_the_next_heading(self):
        text = ("## Forbidden claims\n- Real claim.\n\n"
                "## Positioning\n- This bullet belongs to positioning.\n")
        assert forbidden_claims(text) == ["Real claim."]

    def test_bullets_before_the_heading_do_not_count(self):
        text = ("A stray bullet\n- not under any heading.\n\n"
                "## Forbidden claims\n- The one that counts.\n")
        assert forbidden_claims(text) == ["The one that counts."]

    def test_declared_offer_id_reads_frontmatter_only(self):
        assert declared_offer_id(VALID_PLAN) == 1
        assert declared_offer_id("offer_id: 1\n") is None


class TestCheckPlan:
    def test_reads_the_canonical_filename(self, tmp_applyr):
        plan_path_for("Fusuma").parent.mkdir(parents=True, exist_ok=True)
        _write(plan_path_for("Fusuma"), VALID_PLAN)
        status, path = check_plan("Fusuma", 1)
        assert status is PlanStatus.VALID
        assert path == plan_path_for("Fusuma")

    def test_accepts_a_hand_named_file_with_the_right_offer_id(self, tmp_applyr):
        """`cv-<company>-plan.md` from AGENT_INSTRUCTIONS vs the slug name: the
        offer id is the contract, the filename is a convention."""
        output_dir = plan_path_for("Fusuma").parent
        _write(output_dir / "cv-Fusuma (Spain)-plan.md", VALID_PLAN)
        status, _path = check_plan("Fusuma", 1)
        assert status is PlanStatus.VALID

    def test_prefers_the_valid_plan_over_a_stale_one(self, tmp_applyr):
        """Two offers at one company: the other offer's plan must not shadow
        this offer's valid one, whatever the directory order is."""
        output_dir = plan_path_for("Fusuma").parent
        stale = VALID_PLAN.replace("offer_id: 1", "offer_id: 7")
        _write(output_dir / "cv-a-plan.md", stale)  # sorts first, must not win
        _write(output_dir / "cv-z-plan.md", VALID_PLAN)
        status, path = check_plan("Fusuma", 1)
        assert status is PlanStatus.VALID
        assert path.name == "cv-z-plan.md"

    def test_reports_wrong_offer_when_only_another_offers_plan_exists(self, tmp_applyr):
        output_dir = plan_path_for("Fusuma").parent
        _write(output_dir / "cv-fusuma-plan.md", VALID_PLAN.replace("offer_id: 1", "offer_id: 7"))
        status, _path = check_plan("Fusuma", 1)
        assert status is PlanStatus.WRONG_OFFER

    def test_reports_missing_and_points_at_the_canonical_path(self, tmp_applyr):
        status, path = check_plan("Fusuma", 1)
        assert status is PlanStatus.MISSING
        assert path == plan_path_for("Fusuma")


class TestStatusContract:
    @pytest.mark.parametrize("status,code", [
        (PlanStatus.MISSING, "plan_required"),
        (PlanStatus.WRONG_OFFER, "plan_invalid"),
        (PlanStatus.EMPTY, "plan_invalid"),
        (PlanStatus.UNREADABLE, "plan_invalid"),
    ])
    def test_error_codes_are_stable(self, status, code):
        """Agents branch on the code, not on English prose (ADR-007)."""
        assert status.error_code == code

    def test_valid_plan_has_no_error_code(self):
        assert PlanStatus.VALID.error_code == ""

    @pytest.mark.parametrize("status", [s for s in PlanStatus if s is not PlanStatus.VALID])
    def test_every_failure_explains_itself(self, status):
        assert plan_hint(status)
