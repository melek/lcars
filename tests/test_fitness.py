"""Tests for lib/fitness.py — correction effectiveness tracking."""

import json
import time

import fitness


class TestRecordAndEvaluate:
    def test_effective_correction(self, lcars_tmpdir):
        """Correction that improves filler count → effective."""
        drift_details = {
            "categories": ["filler"],
            "severity": "high",
            "query_type": "factual",
            "padding_count": 3,
            "answer_position": 0,
            "info_density": 0.65,
        }
        fitness.record_correction(drift_details)

        # Simulate improved post-correction score
        post_score = {
            "padding_count": 0,
            "answer_position": 0,
            "info_density": 0.70,
        }
        outcome = fitness.evaluate_correction(post_score)

        assert outcome is not None
        assert outcome["effective"] is True
        assert outcome["details"]["filler"] is True

    def test_ineffective_correction(self, lcars_tmpdir):
        """Correction that doesn't improve → ineffective."""
        drift_details = {
            "categories": ["filler"],
            "severity": "low",
            "query_type": "factual",
            "padding_count": 2,
            "answer_position": 0,
            "info_density": 0.65,
        }
        fitness.record_correction(drift_details)

        post_score = {
            "padding_count": 3,  # Worse than before
            "answer_position": 0,
            "info_density": 0.60,
        }
        outcome = fitness.evaluate_correction(post_score)

        assert outcome is not None
        assert outcome["effective"] is False

    def test_stale_pending_ignored(self, lcars_tmpdir):
        """Pending correction older than 24h should be discarded."""
        drift_details = {
            "categories": ["filler"],
            "severity": "low",
            "query_type": "factual",
            "padding_count": 2,
            "answer_position": 0,
            "info_density": 0.65,
        }
        fitness.record_correction(drift_details)

        # Manually backdate the pending file
        with open(fitness.PENDING_FILE) as f:
            data = json.load(f)
        data["epoch"] = time.time() - 90000  # >24h ago
        with open(fitness.PENDING_FILE, "w") as f:
            json.dump(data, f)

        post_score = {"padding_count": 0, "answer_position": 0, "info_density": 0.70}
        outcome = fitness.evaluate_correction(post_score)

        assert outcome is None

    def test_no_pending_returns_none(self, lcars_tmpdir):
        post_score = {"padding_count": 0, "answer_position": 0, "info_density": 0.70}
        outcome = fitness.evaluate_correction(post_score)
        assert outcome is None


class TestFitnessRate:
    def test_rate_calculation(self, lcars_tmpdir, write_outcomes):
        outcomes = [
            {"epoch": time.time(), "categories": ["filler"], "effective": True},
            {"epoch": time.time(), "categories": ["filler"], "effective": True},
            {"epoch": time.time(), "categories": ["filler"], "effective": False},
        ]
        write_outcomes(outcomes)

        rate = fitness.fitness_rate(days=30)
        assert rate is not None
        assert rate["total"] == 3
        assert rate["effective"] == 2
        assert abs(rate["rate"] - 0.667) < 0.01

    def test_no_outcomes_returns_none(self, lcars_tmpdir):
        rate = fitness.fitness_rate()
        assert rate is None
