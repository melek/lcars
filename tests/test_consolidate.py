"""Tests for lib/consolidate.py — overfit gates and pattern validation."""

import time

import consolidate


class TestOverfitGates:
    def test_below_session_threshold(self, lcars_tmpdir, write_summaries):
        """4 sessions (below MIN_SESSIONS=5) → pattern NOT validated."""
        summaries = [
            {
                "epoch": time.time() - i * 3600,
                "date": "2026-02-18",
                "responses": 5,
                "avg_density": 0.65,
                "drift_types": ["filler"],
                "query_types": {"factual": 3, "code": 2},
            }
            for i in range(4)
        ]
        write_summaries(summaries)

        result = consolidate.consolidate()
        assert result["status"] == "insufficient_data"

    def test_meets_all_gates(self, lcars_tmpdir, write_summaries):
        """5 sessions across 3 calendar days → pattern validated."""
        dates = ["2026-02-15", "2026-02-16", "2026-02-16", "2026-02-17", "2026-02-18"]
        summaries = [
            {
                "epoch": time.time() - i * 86400,
                "date": dates[i],
                "responses": 5,
                "avg_density": 0.55,
                "drift_types": ["filler"],
                "query_types": {"factual": 5},
            }
            for i in range(5)
        ]
        write_summaries(summaries)

        result = consolidate.consolidate()
        assert result["status"] == "consolidated"
        assert result["patterns_validated"] >= 1
        assert "filler" in result["patterns_added"]

    def test_same_day_insufficient(self, lcars_tmpdir, write_summaries):
        """5 sessions all on same day → not enough calendar day spread."""
        summaries = [
            {
                "epoch": time.time() - i * 3600,
                "date": "2026-02-18",  # All same day
                "responses": 5,
                "avg_density": 0.55,
                "drift_types": ["filler"],
                "query_types": {"factual": 5},
            }
            for i in range(5)
        ]
        write_summaries(summaries)

        result = consolidate.consolidate()
        # Sufficient sessions exist but only 1 unique day → pattern not validated
        assert result["status"] == "consolidated"
        assert result["patterns_validated"] == 0

    def test_contradiction_marks_stale(self, lcars_tmpdir, write_summaries):
        """Previously validated pattern that no longer meets gates → stale."""
        import json

        # Write an existing validated pattern for "preamble"
        patterns = [
            {
                "drift_type": "preamble",
                "sessions": 6,
                "unique_days": 4,
                "first_seen": "2026-01-01",
                "last_seen": "2026-01-15",
                "status": "validated",
            }
        ]
        with open(consolidate.PATTERNS_FILE, "w") as f:
            json.dump(patterns, f)

        # Write summaries with only "filler" drift — no "preamble" at all
        dates = ["2026-02-14", "2026-02-15", "2026-02-16", "2026-02-17", "2026-02-18"]
        summaries = [
            {
                "epoch": time.time() - i * 86400,
                "date": dates[i],
                "responses": 5,
                "avg_density": 0.55,
                "drift_types": ["filler"],
                "query_types": {"factual": 5},
            }
            for i in range(5)
        ]
        write_summaries(summaries)

        result = consolidate.consolidate()
        assert "preamble" in result["patterns_stale"]


class TestSessionSummaryExtraction:
    def test_extract_from_scores(self, lcars_tmpdir, write_scores):
        """Extract session summary from recent scores."""
        scores = [
            {
                "epoch": time.time() - 60,
                "word_count": 50,
                "answer_position": 0,
                "padding_count": 2,
                "info_density": 0.60,
                "query_type": "factual",
            },
            {
                "epoch": time.time() - 30,
                "word_count": 30,
                "answer_position": 0,
                "padding_count": 0,
                "info_density": 0.70,
                "query_type": "code",
            },
        ]
        write_scores(scores)

        import store
        summary = consolidate.extract_session_summary(store.SCORES_FILE)
        assert summary is not None
        assert summary["responses"] == 2
        assert "filler" in summary["drift_types"]
