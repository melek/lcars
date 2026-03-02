"""Tests for lib/inject.py — context assembly."""

import json

import inject
import store


class TestContextAssembly:
    def test_clean_start_anchor_only(self, lcars_tmpdir):
        """No drift, no stats → output is anchor text only."""
        anchor = inject.load_anchor()
        stats = inject.load_stats("startup")

        assert anchor != ""
        assert stats == ""

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
