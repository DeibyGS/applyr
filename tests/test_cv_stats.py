"""Tests for CV A/B tracking — rate maths and grouping by cv_used."""

from applyr.cv_stats import build_report, summarize_cv


def offer(status, cv=None):
    """Minimal offer record — only the fields cv_stats reads."""
    return {"status": status, "cv_used": cv}


class TestSummarizeCv:
    def test_empty_input_yields_zero_rates_without_dividing_by_zero(self):
        s = summarize_cv([])
        assert s["sent"] == 0
        assert s["response_rate"] == 0.0
        assert s["interview_rate"] == 0.0

    def test_pending_offers_are_not_counted_as_sent(self):
        # A pending offer says nothing about the CV — it was never sent
        s = summarize_cv([offer("pending"), offer("pending")])
        assert s["total"] == 2
        assert s["sent"] == 0
        assert s["response_rate"] == 0.0

    def test_discarded_offers_are_not_counted_as_sent(self):
        # Dropped by the candidate, not by the employer
        assert summarize_cv([offer("discarded")])["sent"] == 0

    def test_rejection_counts_as_a_response(self):
        # Being rejected means you were read — that is signal about the CV
        s = summarize_cv([offer("rejected")])
        assert s["sent"] == 1
        assert s["responded"] == 1
        assert s["response_rate"] == 100.0

    def test_rejection_is_not_an_interview(self):
        assert summarize_cv([offer("rejected")])["interview_rate"] == 0.0

    def test_applied_with_no_reply_is_sent_but_not_responded(self):
        s = summarize_cv([offer("applied")])
        assert s["sent"] == 1
        assert s["responded"] == 0
        assert s["response_rate"] == 0.0

    def test_in_process_counts_as_interview_and_response(self):
        s = summarize_cv([offer("in_process")])
        assert s["response_rate"] == 100.0
        assert s["interview_rate"] == 100.0

    def test_offer_counts_everywhere(self):
        s = summarize_cv([offer("offer")])
        assert s["responded"] == 1
        assert s["interviews"] == 1
        assert s["offers"] == 1

    def test_mixed_statuses_compute_independent_rates(self):
        # 4 sent: 1 applied (silence), 1 rejected, 1 in_process, 1 offer
        rows = [offer("applied"), offer("rejected"), offer("in_process"), offer("offer")]
        s = summarize_cv(rows)
        assert s["sent"] == 4
        assert s["responded"] == 3          # all but the silent one
        assert s["response_rate"] == 75.0
        assert s["interviews"] == 2         # in_process + offer
        assert s["interview_rate"] == 50.0

    def test_pending_does_not_dilute_rates(self):
        """Adding offers you have not applied to must not lower your rates."""
        base = summarize_cv([offer("offer")])
        with_pending = summarize_cv([offer("offer"), offer("pending"), offer("pending")])
        assert base["interview_rate"] == with_pending["interview_rate"] == 100.0
        assert with_pending["total"] == 3
        assert with_pending["sent"] == 1


class TestBuildReport:
    def test_groups_by_cv_name(self):
        rows = [offer("offer", "a.html"), offer("rejected", "b.html"), offer("applied", "a.html")]
        report = build_report(rows)
        assert {c["cv"] for c in report["cvs"]} == {"a.html", "b.html"}
        assert next(c for c in report["cvs"] if c["cv"] == "a.html")["sent"] == 2

    def test_counts_untracked_offers_separately(self):
        rows = [offer("applied"), offer("applied", ""), offer("applied", "   "), offer("offer", "a.html")]
        report = build_report(rows)
        assert report["untracked"] == 3
        assert report["tracked_offers"] == 1
        assert report["total_offers"] == 4

    def test_sorts_by_interview_rate_descending(self):
        rows = [offer("rejected", "weak.html"), offer("offer", "strong.html")]
        report = build_report(rows)
        assert report["cvs"][0]["cv"] == "strong.html"

    def test_sample_size_breaks_ties_on_equal_rate(self):
        """100% from 3 applications must outrank 100% from 1."""
        rows = [offer("offer", "small.html")] + [offer("offer", "big.html")] * 3
        report = build_report(rows)
        assert report["cvs"][0]["cv"] == "big.html"

    def test_flags_samples_below_minimum(self):
        rows = [offer("offer", "tiny.html")] + [offer("offer", "solid.html")] * 5
        report = build_report(rows, min_sample=3)
        by_name = {c["cv"]: c for c in report["cvs"]}
        assert by_name["tiny.html"]["below_min_sample"] is True
        assert by_name["solid.html"]["below_min_sample"] is False

    def test_empty_database_returns_empty_report(self):
        report = build_report([])
        assert report["cvs"] == []
        assert report["untracked"] == 0
        assert report["total_offers"] == 0

    def test_all_untracked_reports_no_cvs(self):
        report = build_report([offer("offer"), offer("applied")])
        assert report["cvs"] == []
        assert report["untracked"] == 2
