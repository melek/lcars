"""JSONL score ledger with drift flag management.

Scores append to ~/.claude/lcars/scores.jsonl.
Drift flags written to ~/.claude/lcars/drift.json.
Weekly rotation keeps last 4 weeks.

Drift *detection* logic lives in drift.py. This module handles storage only.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

from compat import file_lock, file_unlock, lcars_dir

SCORES_FILE = os.path.join(lcars_dir(), "scores.jsonl")
DRIFT_FILE = os.path.join(lcars_dir(), "drift.json")
DRIFT_LOG = os.path.join(lcars_dir(), "drift-events.jsonl")


def append_score(score: dict):
    """Append a scored response to the JSONL ledger."""
    entry = {
        "ts": datetime.now().isoformat(),
        "epoch": time.time(),
        **score,
    }
    with open(SCORES_FILE, "a") as f:
        file_lock(f)
        f.write(json.dumps(entry) + "\n")
        file_unlock(f)


def append_session_marker(source: str = "startup"):
    """Log a session boundary marker to scores.jsonl."""
    entry = {
        "ts": datetime.now().isoformat(),
        "epoch": time.time(),
        "type": "session_start",
        "source": source,
    }
    with open(SCORES_FILE, "a") as f:
        file_lock(f)
        f.write(json.dumps(entry) + "\n")
        file_unlock(f)


def write_drift_flag(details: dict):
    """Write drift flag for SessionStart hook to pick up."""
    with open(DRIFT_FILE, "w") as f:
        file_lock(f)
        json.dump(details, f)
        file_unlock(f)


def append_drift_event(details: dict):
    """Append drift event to persistent log (drift-events.jsonl)."""
    entry = {
        "ts": datetime.now().isoformat(),
        "epoch": time.time(),
        **{k: v for k, v in details.items() if k not in ("ts", "epoch")},
    }
    with open(DRIFT_LOG, "a") as f:
        file_lock(f)
        f.write(json.dumps(entry) + "\n")
        file_unlock(f)


def read_and_clear_drift_flag() -> dict | None:
    """Read drift flag and delete it. Returns details or None."""
    if not os.path.exists(DRIFT_FILE):
        return None
    try:
        with open(DRIFT_FILE) as f:
            file_lock(f, exclusive=False)
            data = json.load(f)
            file_unlock(f)
        os.unlink(DRIFT_FILE)
        return data
    except (json.JSONDecodeError, OSError):
        try:
            os.unlink(DRIFT_FILE)
        except OSError:
            pass
        return None


def last_score_age_hours() -> float | None:
    """Hours since last score entry. None if no scores exist."""
    if not os.path.exists(SCORES_FILE):
        return None
    try:
        with open(SCORES_FILE, "rb") as f:
            f.seek(0, 2)
            if f.tell() == 0:
                return None
            f.seek(max(f.tell() - 4096, 0))
            lines = f.read().decode().strip().split("\n")
        last = json.loads(lines[-1])
        elapsed = time.time() - last.get("epoch", 0)
        return elapsed / 3600
    except (json.JSONDecodeError, OSError, IndexError):
        return None


def rolling_stats(days: int = 7) -> dict | None:
    """Compute rolling stats over recent scores."""
    if not os.path.exists(SCORES_FILE):
        return None

    cutoff = time.time() - (days * 86400)
    scores = []

    try:
        with open(SCORES_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("type") == "session_start":
                    continue
                if entry.get("epoch", 0) >= cutoff:
                    scores.append(entry)
    except (json.JSONDecodeError, OSError):
        return None

    if not scores:
        return None

    n = len(scores)
    drift_count = sum(
        1 for s in scores
        if s.get("padding_count", 0) > 0 or s.get("answer_position", 0) > 0
    )
    avg_density = sum(s.get("info_density", 0) for s in scores) / n
    avg_words = sum(s.get("word_count", 0) for s in scores) / n

    return {
        "responses": n,
        "drift_rate": f"{drift_count}/{n}",
        "avg_density": round(avg_density, 3),
        "avg_words": round(avg_words, 1),
    }


def rotate_store(keep_weeks: int = 4):
    """Remove scores older than keep_weeks."""
    if not os.path.exists(SCORES_FILE):
        return

    cutoff = time.time() - (keep_weeks * 7 * 86400)
    kept = []

    try:
        with open(SCORES_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("epoch", 0) >= cutoff:
                    kept.append(line)
    except (json.JSONDecodeError, OSError):
        return

    with open(SCORES_FILE, "w") as f:
        file_lock(f)
        f.write("\n".join(kept) + "\n" if kept else "")
        file_unlock(f)
