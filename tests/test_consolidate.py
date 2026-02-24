"""Tests for lib/consolidate.py — overfit gates, segmentation, and pattern validation."""

import json
import time

import consolidate


class TestOverfitGates:
    def test_below_session_threshold(self, lcars_tmpdir, write_summaries):
        """4 sessions (below MIN_SESSIONS=5) -> pattern NOT validated."""
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
        """5 sessions across 3 calendar days -> pattern validated."""
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
        """5 sessions all on same day -> not enough calendar day spread."""
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
        # Sufficient sessions exist but only 1 unique day -> pattern not validated
        assert result["status"] == "consolidated"
        assert result["patterns_validated"] == 0

    def test_contradiction_marks_stale(self, lcars_tmpdir, write_summaries):
        """Previously validated pattern that no longer meets gates -> stale."""
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


def _write_raw_entries(path, entries):
    """Write raw JSONL entries (scores + markers) to a file."""
    with open(path, "a") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


class TestSegmentSessions:
    def test_three_markers_three_segments(self, lcars_tmpdir):
        """3 session_start markers with scores between them -> 3 segments."""
        now = time.time()
        entries = [
            {"type": "session_start", "epoch": now - 3000, "source": "startup"},
            {"epoch": now - 2900, "padding_count": 1, "info_density": 0.5, "query_type": "factual"},
            {"epoch": now - 2800, "padding_count": 0, "info_density": 0.7, "query_type": "code"},
            {"type": "session_start", "epoch": now - 2000, "source": "startup"},
            {"epoch": now - 1900, "padding_count": 0, "info_density": 0.6, "query_type": "factual"},
            {"type": "session_start", "epoch": now - 1000, "source": "startup"},
            {"epoch": now - 900, "padding_count": 2, "info_density": 0.4, "query_type": "factual"},
            {"epoch": now - 800, "padding_count": 0, "info_density": 0.8, "query_type": "code"},
        ]
        _write_raw_entries(consolidate.SCORES_FILE, entries)

        segments = consolidate.segment_sessions(consolidate.SCORES_FILE)
        assert len(segments) == 3
        assert len(segments[0]) == 2  # 2 scores in first session
        assert len(segments[1]) == 1  # 1 score in second session
        assert len(segments[2]) == 2  # 2 scores in third session

    def test_empty_segments_filtered(self, lcars_tmpdir):
        """Marker immediately followed by marker -> empty segment filtered out."""
        now = time.time()
        entries = [
            {"type": "session_start", "epoch": now - 3000, "source": "startup"},
            {"epoch": now - 2900, "padding_count": 0, "info_density": 0.5, "query_type": "factual"},
            {"type": "session_start", "epoch": now - 2000, "source": "startup"},
            # No scores here — empty segment
            {"type": "session_start", "epoch": now - 1000, "source": "startup"},
            {"epoch": now - 900, "padding_count": 0, "info_density": 0.6, "query_type": "code"},
        ]
        _write_raw_entries(consolidate.SCORES_FILE, entries)

        segments = consolidate.segment_sessions(consolidate.SCORES_FILE)
        assert len(segments) == 2  # empty segment between markers is filtered

    def test_scores_before_first_marker(self, lcars_tmpdir):
        """Scores before the first session_start marker are treated as one session."""
        now = time.time()
        entries = [
            # Scores before any marker
            {"epoch": now - 5000, "padding_count": 1, "info_density": 0.5, "query_type": "factual"},
            {"epoch": now - 4900, "padding_count": 0, "info_density": 0.7, "query_type": "code"},
            # Then a marker
            {"type": "session_start", "epoch": now - 3000, "source": "startup"},
            {"epoch": now - 2900, "padding_count": 0, "info_density": 0.6, "query_type": "factual"},
        ]
        _write_raw_entries(consolidate.SCORES_FILE, entries)

        segments = consolidate.segment_sessions(consolidate.SCORES_FILE)
        assert len(segments) == 2
        assert len(segments[0]) == 2  # pre-marker scores
        assert len(segments[1]) == 1  # post-marker scores

    def test_no_markers(self, lcars_tmpdir):
        """Scores with no markers at all -> one segment."""
        now = time.time()
        entries = [
            {"epoch": now - 100, "padding_count": 0, "info_density": 0.5, "query_type": "factual"},
            {"epoch": now - 50, "padding_count": 1, "info_density": 0.6, "query_type": "code"},
        ]
        _write_raw_entries(consolidate.SCORES_FILE, entries)

        segments = consolidate.segment_sessions(consolidate.SCORES_FILE)
        assert len(segments) == 1
        assert len(segments[0]) == 2

    def test_empty_file(self, lcars_tmpdir):
        """Empty scores file -> no segments."""
        segments = consolidate.segment_sessions(consolidate.SCORES_FILE)
        assert segments == []


class TestSummarizeSession:
    def test_summarize_basic(self):
        """Summarize a simple session segment."""
        now = time.time()
        segment = [
            {"epoch": now - 100, "padding_count": 2, "answer_position": 0, "info_density": 0.5, "query_type": "factual"},
            {"epoch": now - 50, "padding_count": 0, "answer_position": 3, "info_density": 0.7, "query_type": "code"},
        ]
        summary = consolidate.summarize_session(segment)
        assert summary["responses"] == 2
        assert "filler" in summary["drift_types"]
        assert "preamble" in summary["drift_types"]
        assert summary["avg_density"] == 0.6
        assert summary["query_types"] == {"factual": 1, "code": 1}
        assert summary["epoch"] == now - 100
        assert summary["date"]  # non-empty date string

    def test_summarize_empty(self):
        """Empty segment returns empty dict."""
        assert consolidate.summarize_session([]) == {}

    def test_summarize_no_drift(self):
        """Session with no drift -> empty drift_types."""
        now = time.time()
        segment = [
            {"epoch": now, "padding_count": 0, "answer_position": 0, "info_density": 0.8, "query_type": "code"},
        ]
        summary = consolidate.summarize_session(segment)
        assert summary["drift_types"] == []


class TestSegmentBasedConsolidation:
    def _make_session_entries(self, epoch, date_str, n_scores=3, drift="filler"):
        """Helper: create a session_start marker + n score entries."""
        entries = [{"type": "session_start", "epoch": epoch, "source": "startup"}]
        for i in range(n_scores):
            score = {
                "epoch": epoch + (i + 1) * 10,
                "padding_count": 2 if drift == "filler" else 0,
                "answer_position": 3 if drift == "preamble" else 0,
                "info_density": 0.55,
                "query_type": "factual",
            }
            entries.append(score)
        return entries

    def test_five_sessions_from_markers(self, lcars_tmpdir):
        """5+ sessions from markers across 3+ days validates patterns."""
        now = time.time()
        dates_and_offsets = [
            (now - 5 * 86400, "2026-02-18"),
            (now - 4 * 86400, "2026-02-19"),
            (now - 3 * 86400, "2026-02-20"),
            (now - 2 * 86400, "2026-02-21"),
            (now - 1 * 86400, "2026-02-22"),
        ]

        all_entries = []
        for epoch, _ in dates_and_offsets:
            all_entries.extend(self._make_session_entries(epoch, _, drift="filler"))

        _write_raw_entries(consolidate.SCORES_FILE, all_entries)

        result = consolidate.consolidate()
        assert result["status"] == "consolidated"
        assert result["sessions_analyzed"] == 5
        assert result["patterns_validated"] >= 1
        assert "filler" in result["patterns_added"]

    def test_fallback_to_cached_summaries(self, lcars_tmpdir, write_summaries):
        """When scores.jsonl is empty, falls back to cached summaries."""
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
        assert result["status"] == "consolidated"
        assert "filler" in result["patterns_added"]

    def test_insufficient_sessions_from_markers(self, lcars_tmpdir):
        """Fewer than 5 sessions from markers -> insufficient_data."""
        now = time.time()
        all_entries = []
        for i in range(3):
            epoch = now - (i + 1) * 86400
            all_entries.extend(self._make_session_entries(epoch, f"2026-02-{18+i}"))

        _write_raw_entries(consolidate.SCORES_FILE, all_entries)

        result = consolidate.consolidate()
        assert result["status"] == "insufficient_data"
        assert result["sessions"] == 3

    def test_caches_new_summaries(self, lcars_tmpdir):
        """Consolidation writes computed summaries to cache file."""
        import os

        now = time.time()
        all_entries = []
        for i in range(5):
            epoch = now - (i + 1) * 86400
            all_entries.extend(self._make_session_entries(epoch, f"2026-02-{18+i}"))

        _write_raw_entries(consolidate.SCORES_FILE, all_entries)
        consolidate.consolidate()

        # Verify summaries were cached
        assert os.path.exists(consolidate.SUMMARIES_FILE)
        cached = []
        with open(consolidate.SUMMARIES_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    cached.append(json.loads(line))
        assert len(cached) == 5
        # Each cached entry should have _marker_epoch
        assert all("_marker_epoch" in c for c in cached)
