"""JSONL score storage with drift detection.

Scores append to ~/.claude/lcars/scores.jsonl.
Drift flags written to ~/.claude/lcars/drift.json.
Weekly rotation keeps last 4 weeks.
"""

import fcntl
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

LCARS_DIR = Path.home() / ".claude" / "lcars"
SCORES_FILE = LCARS_DIR / "scores.jsonl"
DRIFT_FILE = LCARS_DIR / "drift.json"

# Drift thresholds
FILLER_THRESHOLD = 0  # any filler = drift
PREAMBLE_THRESHOLD = 0  # any preamble words = drift
DENSITY_THRESHOLD = 0.60  # below this = drift


def _ensure_dir():
    LCARS_DIR.mkdir(parents=True, exist_ok=True)


def append_score(score: dict):
    """Append a scored response to the JSONL store."""
    _ensure_dir()
    entry = {
        "ts": datetime.now().isoformat(),
        "epoch": time.time(),
        **score,
    }
    with open(SCORES_FILE, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(entry) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)


def detect_drift(score: dict) -> dict | None:
    """Check score against thresholds. Returns drift details or None."""
    reasons = []

    if score.get("padding_count", 0) > FILLER_THRESHOLD:
        reasons.append(f"filler:{score['padding_count']}")

    if score.get("answer_position", 0) > PREAMBLE_THRESHOLD:
        reasons.append(f"preamble:{score['answer_position']}w")

    density = score.get("info_density", 1.0)
    if density < DENSITY_THRESHOLD:
        reasons.append(f"density:{density:.3f}")

    if not reasons:
        return None

    return {
        "ts": datetime.now().isoformat(),
        "reasons": reasons,
        "score": score,
    }


def write_drift_flag(details: dict):
    """Write drift flag for SessionStart hook to pick up."""
    _ensure_dir()
    with open(DRIFT_FILE, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(details, f)
        fcntl.flock(f, fcntl.LOCK_UN)


def read_and_clear_drift_flag() -> dict | None:
    """Read drift flag and delete it. Returns details or None."""
    if not DRIFT_FILE.exists():
        return None
    try:
        with open(DRIFT_FILE) as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f, fcntl.LOCK_UN)
        DRIFT_FILE.unlink()
        return data
    except (json.JSONDecodeError, OSError):
        DRIFT_FILE.unlink(missing_ok=True)
        return None


def last_score_age_hours() -> float | None:
    """Hours since last score entry. None if no scores exist."""
    if not SCORES_FILE.exists():
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
    """Compute rolling stats over recent scores. Returns summary or None."""
    if not SCORES_FILE.exists():
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
                if entry.get("epoch", 0) >= cutoff:
                    scores.append(entry)
    except (json.JSONDecodeError, OSError):
        return None

    if not scores:
        return None

    n = len(scores)
    drift_count = sum(1 for s in scores if s.get("padding_count", 0) > 0 or s.get("answer_position", 0) > 0)
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
    if not SCORES_FILE.exists():
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
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write("\n".join(kept) + "\n" if kept else "")
        fcntl.flock(f, fcntl.LOCK_UN)
