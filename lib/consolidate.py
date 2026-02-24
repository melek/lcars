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
from compat import file_lock, file_unlock, lcars_dir, lcars_memory_dir

SUMMARIES_FILE = os.path.join(lcars_memory_dir(), "session-summaries.jsonl")
PATTERNS_FILE = os.path.join(lcars_memory_dir(), "patterns.json")
SCORES_FILE = os.path.join(lcars_dir(), "scores.jsonl")

# Overfit gates
MIN_SESSIONS = 5
MIN_CALENDAR_DAYS = 3
SUMMARY_RETENTION_DAYS = 30


def segment_sessions(scores_path: str) -> list[list[dict]]:
    """Split scores.jsonl entries at session_start markers.

    Returns a list of session segments, each segment being a list of
    score entries between consecutive markers. Scores before the first
    marker are treated as one session. Empty segments (marker immediately
    followed by marker, or trailing marker with no scores) are filtered out.
    """
    if not os.path.exists(scores_path):
        return []

    entries = []
    try:
        with open(scores_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entries.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        return []

    segments = []
    current = []

    for entry in entries:
        if entry.get("type") == "session_start":
            if current:
                segments.append(current)
            current = []
            # Store marker epoch on the segment for cache keying
            current.append({"_marker_epoch": entry.get("epoch", 0)})
            current.pop()  # Don't include the pseudo-entry; just note we started fresh
            # We need the marker epoch accessible — store it differently
        else:
            current.append(entry)

    # Flush the last segment
    if current:
        segments.append(current)

    # Filter out empty segments
    return [s for s in segments if s]


def _segment_sessions_with_keys(scores_path: str) -> list[tuple[float, list[dict]]]:
    """Like segment_sessions but returns (marker_epoch, segment) tuples.

    The marker_epoch is used as a cache key for session-summaries.jsonl.
    Segments before the first marker use epoch 0 as their key.
    """
    if not os.path.exists(scores_path):
        return []

    entries = []
    try:
        with open(scores_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entries.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        return []

    result = []
    current_key = 0.0  # scores before first marker
    current_scores = []

    for entry in entries:
        if entry.get("type") == "session_start":
            if current_scores:
                result.append((current_key, current_scores))
            current_key = entry.get("epoch", 0.0)
            current_scores = []
        else:
            current_scores.append(entry)

    if current_scores:
        result.append((current_key, current_scores))

    return result


def summarize_session(segment: list[dict]) -> dict:
    """Summarize a session segment into the same format as extract_session_summary.

    Takes a list of score entries (one session) and produces a summary dict.
    """
    if not segment:
        return {}

    # Filter out non-score entries (e.g. session markers that leaked through)
    scores = [s for s in segment if s.get("type") != "session_start"]
    if not scores:
        return {}

    n = len(scores)
    drift_types = []
    query_types = Counter()

    for s in scores:
        if s.get("padding_count", 0) > 0:
            drift_types.append("filler")
        if s.get("answer_position", 0) > 0:
            drift_types.append("preamble")
        qt = s.get("query_type", "ambiguous")
        query_types[qt] += 1

    avg_density = sum(s.get("info_density", 0) for s in scores) / n

    # Use the first score's epoch/date for the session timestamp
    first_epoch = scores[0].get("epoch", 0)
    date = datetime.fromtimestamp(first_epoch).strftime("%Y-%m-%d") if first_epoch else ""

    return {
        "epoch": first_epoch,
        "date": date,
        "responses": n,
        "avg_density": round(avg_density, 3),
        "drift_types": list(set(drift_types)),
        "query_types": dict(query_types),
    }


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


def _load_cached_epochs() -> set[float]:
    """Load marker epochs already cached in session-summaries.jsonl."""
    if not os.path.exists(SUMMARIES_FILE):
        return set()
    epochs = set()
    try:
        with open(SUMMARIES_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if "_marker_epoch" in entry:
                    epochs.add(entry["_marker_epoch"])
    except (json.JSONDecodeError, OSError):
        pass
    return epochs


def consolidate(scores_path: str | None = None) -> dict:
    """Consolidate session data into validated patterns.

    Primary data source: scores.jsonl (segmented by session_start markers).
    Falls back to session-summaries.jsonl cache for already-computed summaries.
    Writes new summaries to the cache for future runs.

    Returns a report of what changed.
    """
    if scores_path is None:
        scores_path = SCORES_FILE

    # Build summaries from scores.jsonl segments
    keyed_segments = _segment_sessions_with_keys(scores_path)

    # Load cached summaries (keyed by marker epoch) to avoid recomputation
    cached_epochs = _load_cached_epochs()

    summaries = []
    retention_cutoff = time.time() - (SUMMARY_RETENTION_DAYS * 86400)

    for marker_epoch, segment in keyed_segments:
        # Skip segments older than retention window
        first_epoch = segment[0].get("epoch", 0) if segment else 0
        if first_epoch and first_epoch < retention_cutoff:
            continue

        summary = summarize_session(segment)
        if not summary or not summary.get("responses"):
            continue

        # Cache new summaries for future runs
        if marker_epoch not in cached_epochs and marker_epoch > 0:
            cache_entry = {**summary, "_marker_epoch": marker_epoch}
            append_summary(cache_entry)

        summaries.append(summary)

    # If no segments found in scores.jsonl, fall back to cached summaries
    if not summaries:
        summaries = load_summaries()

    if len(summaries) < MIN_SESSIONS:
        return {"status": "insufficient_data", "sessions": len(summaries), "required": MIN_SESSIONS}

    # Count drift type occurrences across sessions and calendar days
    drift_sessions = {}  # drift_type -> list of dates
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
    scores_file = SCORES_FILE

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
