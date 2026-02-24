"""Tests for lib/setup.py diagnostic checks."""

import json
import os
import time

import pytest

import setup


@pytest.fixture
def setup_env(tmp_path, monkeypatch):
    """Provide a temp LCARS directory and patch setup module paths."""
    lcars_dir = tmp_path / ".claude" / "lcars"
    lcars_dir.mkdir(parents=True)
    monkeypatch.setattr(
        setup, "DATA_DIR", tmp_path / "data"
    )
    (tmp_path / "data").mkdir()
    return lcars_dir, tmp_path / "data"


class TestCheckPython:
    def test_finds_executable(self):
        result = setup.check_python()
        assert result["name"] == "python"
        assert result["status"] == "pass"
        assert "3." in result["detail"]


class TestCheckDirs:
    def test_writable_dir(self, tmp_path, monkeypatch):
        lcars = tmp_path / ".claude" / "lcars"
        lcars.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(tmp_path))
        # Also patch USERPROFILE for Windows compat
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        result = setup.check_dirs()
        assert result["status"] == "pass"

    def test_missing_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        result = setup.check_dirs()
        assert result["status"] == "fail"
        assert "does not exist" in result["detail"]


class TestCheckScores:
    def test_present_and_recent(self, tmp_path, monkeypatch):
        lcars = tmp_path / ".claude" / "lcars"
        lcars.mkdir(parents=True)
        scores_file = lcars / "scores.jsonl"
        entry = {"epoch": time.time(), "word_count": 10}
        scores_file.write_text(json.dumps(entry) + "\n")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        result = setup.check_scores()
        assert result["status"] == "pass"

    def test_absent(self, tmp_path, monkeypatch):
        lcars = tmp_path / ".claude" / "lcars"
        lcars.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        result = setup.check_scores()
        assert result["status"] == "warn"

    def test_stale(self, tmp_path, monkeypatch):
        lcars = tmp_path / ".claude" / "lcars"
        lcars.mkdir(parents=True)
        scores_file = lcars / "scores.jsonl"
        old_epoch = time.time() - (48 * 3600)  # 48h ago
        entry = {"epoch": old_epoch, "word_count": 10}
        scores_file.write_text(json.dumps(entry) + "\n")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        result = setup.check_scores()
        assert result["status"] == "warn"
        assert "> 24h" in result["detail"]


class TestCheckThresholds:
    def test_valid(self, setup_env):
        _, data_dir = setup_env
        thresholds = {"version": 1, "global": {"filler": 0}, "by_query_type": {}}
        (data_dir / "thresholds.json").write_text(json.dumps(thresholds))
        result = setup.check_thresholds()
        assert result["status"] == "pass"
        assert "v1" in result["detail"]

    def test_missing(self, setup_env):
        result = setup.check_thresholds()
        assert result["status"] == "fail"
        assert "not found" in result["detail"]

    def test_invalid_json(self, setup_env):
        _, data_dir = setup_env
        (data_dir / "thresholds.json").write_text("{not valid json")
        result = setup.check_thresholds()
        assert result["status"] == "fail"
        assert "Invalid JSON" in result["detail"]


class TestCheckImports:
    def test_succeeds(self):
        result = setup.check_imports()
        assert result["status"] == "pass"
        assert "score" in result["detail"]


class TestCheckScoring:
    def test_detects_filler(self):
        result = setup.check_scoring()
        assert result["status"] == "pass"
        assert "padding" in result["detail"]


class TestRunAllChecks:
    def test_returns_proper_format(self):
        results = setup.run_all_checks()
        assert isinstance(results, list)
        assert len(results) == 6
        for r in results:
            assert "name" in r
            assert r["status"] in ("pass", "fail", "warn")
            assert "detail" in r
