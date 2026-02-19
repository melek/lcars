"""Tests for lib/inject.py — context assembly."""

import json

import inject
import store


class TestContextAssembly:
    def test_clean_start_anchor_only(self, lcars_tmpdir):
        """No drift, no stats → output is anchor text only."""
        anchor = inject.load_anchor()
        correction = inject.load_correction()
        stats = inject.load_stats("startup")

        assert anchor != ""
        assert correction == ""
        assert stats == ""

    def test_with_drift_correction(self, lcars_tmpdir):
        """drift.json exists → correction included in output."""
        drift_details = {
            "categories": ["filler"],
            "severity": "high",
            "correction": "[Prior: 3 filler phrases. Cognitive load without information. Omit all.]",
            "query_type": "factual",
            "padding_count": 3,
            "answer_position": 0,
            "info_density": 0.65,
        }
        store.write_drift_flag(drift_details)

        correction = inject.load_correction()
        assert "filler" in correction.lower() or "Omit" in correction

    def test_drift_flag_consumed(self, lcars_tmpdir):
        """After load_correction reads drift.json, the file should be deleted."""
        drift_details = {
            "categories": ["filler"],
            "severity": "low",
            "correction": "[Prior response contained filler. Omit.]",
            "query_type": "factual",
            "padding_count": 1,
            "answer_position": 0,
            "info_density": 0.65,
        }
        store.write_drift_flag(drift_details)

        inject.load_correction()

        # Drift flag should be consumed
        second = store.read_and_clear_drift_flag()
        assert second is None

    def test_stats_on_resume(self, lcars_tmpdir, write_scores):
        """Resume with >4h gap and rolling data → stats line included."""
        import time
        scores = [
            {
                "epoch": time.time() - 3600,  # 1h ago (within window)
                "word_count": 50,
                "answer_position": 0,
                "padding_count": 0,
                "info_density": 0.65,
            }
        ]
        write_scores(scores)

        stats = inject.load_stats("resume")
        assert stats != ""
        assert "7d:" in stats

    def test_no_stats_on_fresh_startup(self, lcars_tmpdir):
        """Fresh startup with no prior scores → no stats."""
        stats = inject.load_stats("startup")
        assert stats == ""
