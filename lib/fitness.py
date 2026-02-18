"""Correction effectiveness tracking.

Measures whether drift corrections actually improve the targeted dimension.
Flow:
  1. inject.py calls record_correction() when injecting a correction
  2. score.py calls evaluate_correction() after scoring the next response
  3. Outcomes append to correction-outcomes.jsonl in memory/

Fitness rate = effective corrections / total corrections
  >= 0.70  corrections working
  0.50-0.70  some strategies ineffective
  < 0.50  corrections are noise — reduce frequency
"""

import json
import os
import time

from compat import file_lock, file_unlock, lcars_dir, lcars_memory_dir

PENDING_FILE = os.path.join(lcars_dir(), "pending-correction.json")
OUTCOMES_FILE = os.path.join(lcars_memory_dir(), "correction-outcomes.jsonl")


def record_correction(drift_details: dict):
    """Called by inject.py when a correction is injected.

    Saves the drift details so the next score.py run can evaluate effectiveness.
    """
    pending = {
        "epoch": time.time(),
        "categories": drift_details.get("categories", []),
        "severity": drift_details.get("severity", ""),
        "query_type": drift_details.get("query_type", "ambiguous"),
        "pre_scores": {
            # These come from the drift flag's source score
            "padding_count": drift_details.get("padding_count", 0),
            "answer_position": drift_details.get("answer_position", 0),
            "info_density": drift_details.get("info_density", 0),
        },
    }
    with open(PENDING_FILE, "w") as f:
        file_lock(f)
        json.dump(pending, f)
        file_unlock(f)


def evaluate_correction(post_score: dict) -> dict | None:
    """Called by score.py after scoring. Checks pending correction and evaluates.

    Returns outcome dict if there was a pending correction, None otherwise.
    Clears the pending file after evaluation.
    """
    if not os.path.exists(PENDING_FILE):
        return None

    try:
        with open(PENDING_FILE) as f:
            file_lock(f, exclusive=False)
            pending = json.load(f)
            file_unlock(f)
        os.unlink(PENDING_FILE)
    except (json.JSONDecodeError, OSError):
        try:
            os.unlink(PENDING_FILE)
        except OSError:
            pass
        return None

    # Stale pending corrections (> 24h) are discarded
    if time.time() - pending.get("epoch", 0) > 86400:
        return None

    pre = pending.get("pre_scores", {})
    categories = pending.get("categories", [])

    # Evaluate each targeted dimension
    improvements = []
    for cat in categories:
        if cat == "filler":
            improved = post_score.get("padding_count", 0) < pre.get("padding_count", 1)
        elif cat == "preamble":
            improved = post_score.get("answer_position", 0) < pre.get("answer_position", 1)
        elif cat == "density":
            improved = post_score.get("info_density", 0) > pre.get("info_density", 0)
        else:
            improved = False
        improvements.append(improved)

    effective = all(improvements) if improvements else False

    outcome = {
        "epoch": time.time(),
        "categories": categories,
        "severity": pending.get("severity", ""),
        "query_type": pending.get("query_type", "ambiguous"),
        "effective": effective,
        "details": {cat: imp for cat, imp in zip(categories, improvements)},
    }

    # Append outcome
    with open(OUTCOMES_FILE, "a") as f:
        file_lock(f)
        f.write(json.dumps(outcome) + "\n")
        file_unlock(f)

    return outcome


def fitness_rate(days: int = 30) -> dict | None:
    """Compute correction fitness rate over recent outcomes."""
    if not os.path.exists(OUTCOMES_FILE):
        return None

    cutoff = time.time() - (days * 86400)
    outcomes = []

    try:
        with open(OUTCOMES_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("epoch", 0) >= cutoff:
                    outcomes.append(entry)
    except (json.JSONDecodeError, OSError):
        return None

    if not outcomes:
        return None

    total = len(outcomes)
    effective = sum(1 for o in outcomes if o.get("effective"))

    return {
        "total": total,
        "effective": effective,
        "rate": round(effective / total, 3) if total else 0,
    }
