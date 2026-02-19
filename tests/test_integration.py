"""Integration tests — end-to-end correction loop and graceful degradation."""

import json
import os

import score as score_mod
import store
import drift as drift_mod
import inject


class TestCorrectionLoop:
    def test_full_loop(self, lcars_tmpdir):
        """Score sycophantic → drift.json created → inject reads it → correction in output → consumed."""
        # Step 1: Score a sycophantic response
        text = "Great question! I'd be happy to help you with that. The answer is 42. Let me know if you need anything else."
        result = score_mod.score_response(text)
        assert result["padding_count"] >= 3

        # Step 2: Detect drift
        drift_result = drift_mod.detect(result, "factual")
        assert drift_result is not None
        assert drift_result["severity"] == "high"

        # Step 3: Write drift flag
        store.write_drift_flag(drift_result)
        assert os.path.exists(store.DRIFT_FILE)

        # Step 4: Inject reads drift flag → correction appears
        correction = inject.load_correction()
        assert correction != ""

        # Step 5: Drift flag consumed
        assert not os.path.exists(store.DRIFT_FILE)

    def test_clean_response_no_drift(self, lcars_tmpdir):
        """Clean response → no drift.json → inject returns anchor only."""
        text = "Line 42 has a TypeError. Change `str` to `int`."
        result = score_mod.score_response(text)
        assert result["padding_count"] == 0

        drift_result = drift_mod.detect(result, "code")
        assert drift_result is None

        # No drift flag written
        assert not os.path.exists(store.DRIFT_FILE)

        # Inject returns only anchor
        correction = inject.load_correction()
        assert correction == ""
        anchor = inject.load_anchor()
        assert anchor != ""


class TestGracefulDegradation:
    def test_missing_runtime_dir_scores(self, tmp_path, monkeypatch):
        """First run with nonexistent runtime dir → lcars_dir() creates it."""
        import compat
        new_dir = tmp_path / "fresh" / ".claude" / "lcars"

        # Restore the real lcars_dir implementation but pointed at our tmp path
        def _make_dir():
            os.makedirs(str(new_dir), exist_ok=True)
            return str(new_dir)

        monkeypatch.setattr(compat, "lcars_dir", _make_dir)
        monkeypatch.setattr(store, "SCORES_FILE", str(new_dir / "scores.jsonl"))
        monkeypatch.setattr(store, "DRIFT_FILE", str(new_dir / "drift.json"))

        # lcars_dir() creates the directory
        compat.lcars_dir()
        assert new_dir.exists()

        store.append_score({"word_count": 10, "padding_count": 0, "info_density": 0.70})
        assert os.path.exists(store.SCORES_FILE)

    def test_missing_anchor_file(self, monkeypatch):
        """Missing anchor.txt → load_anchor returns empty string."""
        from pathlib import Path
        monkeypatch.setattr(inject, "DATA_DIR", Path("/nonexistent"))
        anchor = inject.load_anchor()
        assert anchor == ""

    def test_corrupt_drift_json(self, lcars_tmpdir):
        """Corrupt drift.json → read_and_clear returns None, file cleaned up."""
        with open(store.DRIFT_FILE, "w") as f:
            f.write("not valid json{{{")

        result = store.read_and_clear_drift_flag()
        assert result is None
        assert not os.path.exists(store.DRIFT_FILE)
