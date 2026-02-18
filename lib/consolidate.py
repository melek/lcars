#!/usr/bin/env python3
"""Session summary extraction and pattern consolidation.

Two modes:
  --hook    PreCompact hook: extract session summary before context loss
  --consolidate  Manual: consolidate session summaries into patterns

Overfit gates (OpenClaw Foundry-inspired):
  - Pattern must appear in 5+ sessions
  - Pattern must span 3+ distinct calendar days
  - Contradictions with existing patterns mark old as stale
"""

import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compat import file_lock, file_unlock, lcars_memory_dir

SUMMARIES_FILE = os.path.join(lcars_memory_dir(), "session-summaries.jsonl")
PATTERNS_FILE = os.path.join(lcars_memory_dir(), "patterns.json")

# Overfit gates
MIN_SESSIONS = 5
MIN_CALENDAR_DAYS = 3
SUMMARY_RETENTION_DAYS = 30


def extract_session_summary(scores_file: str) -> dict | None:
    """Extract a summary from the current session's scores.

    Called by PreCompact hook before context is compressed.
    Reads recent scores (last 2 hours) and summarizes drift patterns.
    """
    if not os.path.exists(scores_file):
        return None

    cutoff = time.time() - 7200  # last 2 hours = approximate session
    session_scores = []

    try:
        with open(scores_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("epoch", 0) >= cutoff:
                    session_scores.append(entry)
    except (json.JSONDecodeError, OSError):
        return None

    if not session_scores:
        return None

    n = len(session_scores)
    drift_types = []
    query_types = Counter()

    for s in session_scores:
        if s.get("padding_count", 0) > 0:
            drift_types.append("filler")
        if s.get("answer_position", 0) > 0:
            drift_types.append("preamble")
        qt = s.get("query_type", "ambiguous")
        query_types[qt] += 1

    avg_density = sum(s.get("info_density", 0) for s in session_scores) / n

    return {
        "epoch": time.time(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "responses": n,
        "avg_density": round(avg_density, 3),
        "drift_types": list(set(drift_types)),
        "query_types": dict(query_types),
    }


def append_summary(summary: dict):
    """Append a session summary to the summaries ledger."""
    with open(SUMMARIES_FILE, "a") as f:
        file_lock(f)
        f.write(json.dumps(summary) + "\n")
        file_unlock(f)


def load_summaries(days: int = SUMMARY_RETENTION_DAYS) -> list[dict]:
    """Load recent session summaries."""
    if not os.path.exists(SUMMARIES_FILE):
        return []

    cutoff = time.time() - (days * 86400)
    summaries = []

    try:
        with open(SUMMARIES_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("epoch", 0) >= cutoff:
                    summaries.append(entry)
    except (json.JSONDecodeError, OSError):
        return []

    return summaries


def consolidate() -> dict:
    """Consolidate session summaries into validated patterns.

    Returns a report of what changed.
    """
    summaries = load_summaries()
    if len(summaries) < MIN_SESSIONS:
        return {"status": "insufficient_data", "sessions": len(summaries), "required": MIN_SESSIONS}

    # Count drift type occurrences across sessions and calendar days
    drift_sessions = {}  # drift_type → list of dates
    for s in summaries:
        date = s.get("date", "")
        for dt in s.get("drift_types", []):
            drift_sessions.setdefault(dt, []).append(date)

    # Apply overfit gates
    new_patterns = []
    for drift_type, dates in drift_sessions.items():
        session_count = len(dates)
        unique_days = len(set(dates))

        if session_count >= MIN_SESSIONS and unique_days >= MIN_CALENDAR_DAYS:
            new_patterns.append({
                "drift_type": drift_type,
                "sessions": session_count,
                "unique_days": unique_days,
                "first_seen": min(dates),
                "last_seen": max(dates),
                "status": "validated",
            })

    # Load existing patterns
    existing = _load_patterns()
    existing_types = {p["drift_type"] for p in existing if p.get("status") == "validated"}

    # Contradiction check: if a previously validated pattern no longer meets gates, mark stale
    stale = []
    for p in existing:
        if p.get("status") == "validated" and p["drift_type"] not in {np["drift_type"] for np in new_patterns}:
            p["status"] = "stale"
            stale.append(p["drift_type"])

    # Merge: new patterns replace existing ones of same type
    merged = {p["drift_type"]: p for p in existing}
    for np in new_patterns:
        merged[np["drift_type"]] = np

    _save_patterns(list(merged.values()))

    added = [p["drift_type"] for p in new_patterns if p["drift_type"] not in existing_types]

    return {
        "status": "consolidated",
        "sessions_analyzed": len(summaries),
        "patterns_validated": len(new_patterns),
        "patterns_added": added,
        "patterns_stale": stale,
    }


def _load_patterns() -> list[dict]:
    if not os.path.exists(PATTERNS_FILE):
        return []
    try:
        with open(PATTERNS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_patterns(patterns: list[dict]):
    with open(PATTERNS_FILE, "w") as f:
        file_lock(f)
        json.dump(patterns, f, indent=2)
        file_unlock(f)


def rotate_summaries():
    """Remove summaries older than retention period."""
    if not os.path.exists(SUMMARIES_FILE):
        return

    cutoff = time.time() - (SUMMARY_RETENTION_DAYS * 86400)
    kept = []

    try:
        with open(SUMMARIES_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("epoch", 0) >= cutoff:
                    kept.append(line)
    except (json.JSONDecodeError, OSError):
        return

    with open(SUMMARIES_FILE, "w") as f:
        file_lock(f)
        f.write("\n".join(kept) + "\n" if kept else "")
        file_unlock(f)


def hook_main():
    """PreCompact hook: extract session summary before context loss."""
    from compat import lcars_dir
    scores_file = os.path.join(lcars_dir(), "scores.jsonl")

    summary = extract_session_summary(scores_file)
    if summary:
        append_summary(summary)

    # Amortized rotation + consolidation + foundry (~10% of compactions)
    import random
    if random.random() < 0.1:
        rotate_summaries()
        result = consolidate()
        # If consolidation produced validated patterns, run foundry analysis
        if result.get("status") == "consolidated" and result.get("patterns_validated", 0) > 0:
            from foundry import analyze
            analyze()


if __name__ == "__main__":
    if "--hook" in sys.argv:
        hook_main()
    elif "--consolidate" in sys.argv:
        result = consolidate()
        print(json.dumps(result, indent=2))
    else:
        print("Usage: consolidate.py --hook | --consolidate")
