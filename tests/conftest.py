"""Shared fixtures for LCARS tests.

All tests use tmp_path for runtime data — no real ~/.claude/lcars/ interaction.
Adds lib/ to sys.path so imports work as they do in hook mode.
"""

import json
import os
import sys
import time

import pytest

# Add lib/ to path so tests can import score, classify, drift, etc.
LIB_DIR = os.path.join(os.path.dirname(__file__), "..", "lib")
sys.path.insert(0, LIB_DIR)

# Plugin root for data/ files (anchor.txt, corrections.json, thresholds.json)
PLUGIN_ROOT = os.path.join(os.path.dirname(__file__), "..")


@pytest.fixture(autouse=True)
def plugin_root_env(monkeypatch):
    """Set CLAUDE_PLUGIN_ROOT so drift.py / thresholds.py find data/ files."""
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", PLUGIN_ROOT)


@pytest.fixture
def lcars_tmpdir(tmp_path, monkeypatch):
    """Create a temporary LCARS runtime directory and patch compat paths."""
    lcars_dir = tmp_path / ".claude" / "lcars"
    lcars_dir.mkdir(parents=True)
    memory_dir = lcars_dir / "memory"
    memory_dir.mkdir()

    # Patch compat.lcars_dir and lcars_memory_dir to use tmp
    import compat
    monkeypatch.setattr(compat, "lcars_dir", lambda: str(lcars_dir))
    monkeypatch.setattr(compat, "lcars_memory_dir", lambda: str(memory_dir))

    # Patch module-level path constants that were computed at import time
    import store
    monkeypatch.setattr(store, "SCORES_FILE", str(lcars_dir / "scores.jsonl"))
    monkeypatch.setattr(store, "DRIFT_FILE", str(lcars_dir / "drift.json"))

    import fitness
    monkeypatch.setattr(fitness, "PENDING_FILE", str(lcars_dir / "pending-correction.json"))
    monkeypatch.setattr(fitness, "OUTCOMES_FILE", str(memory_dir / "correction-outcomes.jsonl"))

    import consolidate
    monkeypatch.setattr(consolidate, "SUMMARIES_FILE", str(memory_dir / "session-summaries.jsonl"))
    monkeypatch.setattr(consolidate, "PATTERNS_FILE", str(memory_dir / "patterns.json"))

    import foundry
    monkeypatch.setattr(foundry, "STAGED_FILE", str(memory_dir / "staged-strategies.json"))
    monkeypatch.setattr(foundry, "OUTCOMES_FILE", str(memory_dir / "correction-outcomes.jsonl"))
    monkeypatch.setattr(foundry, "PATTERNS_FILE", str(memory_dir / "patterns.json"))

    return lcars_dir


@pytest.fixture
def sample_score_clean():
    """A clean response score — no filler, no preamble, good density."""
    return {
        "word_count": 12,
        "answer_position": 0,
        "padding_count": 0,
        "filler_phrases": [],
        "info_density": 0.667,
    }


@pytest.fixture
def sample_score_sycophantic():
    """A sycophantic response score — filler, preamble, low density."""
    return {
        "word_count": 45,
        "answer_position": 8,
        "padding_count": 3,
        "filler_phrases": ["Great question", "I'd be happy to", "Let me know if"],
        "info_density": 0.450,
    }


@pytest.fixture
def write_scores(lcars_tmpdir):
    """Helper to write score entries to the JSONL ledger."""
    import store

    def _write(scores: list[dict]):
        for s in scores:
            entry = {"epoch": s.get("epoch", time.time()), **s}
            store.append_score(entry)

    return _write


@pytest.fixture
def write_summaries(lcars_tmpdir):
    """Helper to write session summaries."""
    import consolidate

    def _write(summaries: list[dict]):
        for s in summaries:
            consolidate.append_summary(s)

    return _write


@pytest.fixture
def write_outcomes(lcars_tmpdir):
    """Helper to write correction outcomes."""
    def _write(outcomes: list[dict]):
        import fitness
        path = fitness.OUTCOMES_FILE
        with open(path, "a") as f:
            for o in outcomes:
                f.write(json.dumps(o) + "\n")

    return _write
