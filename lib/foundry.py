#!/usr/bin/env python3
"""Self-contained strategy crystallization.

Observes validated patterns and correction outcomes to propose new or refined
correction strategies. Proposals are staged for human review — never auto-applied.

Inspired by OpenClaw Foundry: observe → validate → crystallize → stage → approve.

Three crystallization types:
  1. Gap filling: validated drift pattern has no query-type-specific strategy
  2. Refinement: existing strategy has low fitness for a specific query type
  3. Suppression: strategy fires frequently but corrections are ineffective
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compat import file_lock, file_unlock, lcars_memory_dir

STAGED_FILE = os.path.join(lcars_memory_dir(), "staged-strategies.json")
OUTCOMES_FILE = os.path.join(lcars_memory_dir(), "correction-outcomes.jsonl")
PATTERNS_FILE = os.path.join(lcars_memory_dir(), "patterns.json")

# Crystallization thresholds
MIN_OUTCOMES_FOR_REFINEMENT = 5
LOW_FITNESS_THRESHOLD = 0.50
HIGH_FIRE_RATE = 0.30  # if >30% of scores trigger this strategy, it may be too aggressive


def _plugin_root():
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent))


def _load_corrections() -> dict:
    path = _plugin_root() / "data" / "corrections.json"
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "strategies": []}


def _load_patterns() -> list[dict]:
    if not os.path.exists(PATTERNS_FILE):
        return []
    try:
        with open(PATTERNS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _load_outcomes(days: int = 30) -> list[dict]:
    if not os.path.exists(OUTCOMES_FILE):
        return []
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
        pass
    return outcomes


def _load_staged() -> list[dict]:
    if not os.path.exists(STAGED_FILE):
        return []
    try:
        with open(STAGED_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_staged(proposals: list[dict]):
    with open(STAGED_FILE, "w") as f:
        file_lock(f)
        json.dump(proposals, f, indent=2)
        file_unlock(f)


def _strategy_exists(strategies: list[dict], drift: str, severity: str, query: str) -> bool:
    """Check if a specific strategy already exists in corrections.json."""
    for s in strategies:
        if s.get("drift") == drift and s.get("severity") == severity and s.get("query") == query:
            return True
    return False


def analyze() -> dict:
    """Analyze patterns and outcomes to generate proposals.

    Returns a report with any new proposals staged.
    """
    corrections = _load_corrections()
    strategies = corrections.get("strategies", [])
    patterns = _load_patterns()
    outcomes = _load_outcomes()
    existing_staged = _load_staged()

    proposals = []

    # 1. Gap filling: validated patterns without query-type-specific strategies
    proposals.extend(_find_gaps(patterns, strategies, outcomes))

    # 2. Refinement: strategies with low fitness for specific query types
    proposals.extend(_find_refinements(strategies, outcomes))

    # 3. Suppression: strategies that fire often but don't help
    proposals.extend(_find_suppressions(strategies, outcomes))

    # Deduplicate against existing staged proposals
    existing_keys = {
        (p["type"], p.get("drift"), p.get("severity"), p.get("query"))
        for p in existing_staged
    }
    new_proposals = [
        p for p in proposals
        if (p["type"], p.get("drift"), p.get("severity"), p.get("query")) not in existing_keys
    ]

    if new_proposals:
        all_staged = existing_staged + new_proposals
        _save_staged(all_staged)

    return {
        "patterns_analyzed": len(patterns),
        "outcomes_analyzed": len(outcomes),
        "new_proposals": len(new_proposals),
        "total_staged": len(existing_staged) + len(new_proposals),
        "proposals": new_proposals,
    }


def _find_gaps(patterns: list, strategies: list, outcomes: list) -> list[dict]:
    """Find validated drift patterns without query-type-specific strategies."""
    proposals = []

    # Get query types that appear in outcomes
    query_drift_counts = {}
    for o in outcomes:
        qt = o.get("query_type", "ambiguous")
        for cat in o.get("categories", []):
            key = (cat, qt)
            query_drift_counts.setdefault(key, {"total": 0, "effective": 0})
            query_drift_counts[key]["total"] += 1
            if o.get("effective"):
                query_drift_counts[key]["effective"] += 1

    for pattern in patterns:
        if pattern.get("status") != "validated":
            continue
        drift_type = pattern["drift_type"]

        # Check each query type that co-occurs with this drift
        for (cat, qt), counts in query_drift_counts.items():
            if cat != drift_type:
                continue
            if counts["total"] < MIN_OUTCOMES_FOR_REFINEMENT:
                continue

            # Does a query-specific strategy exist?
            if not _strategy_exists(strategies, drift_type, "low", qt) and \
               not _strategy_exists(strategies, drift_type, "high", qt):
                fitness = counts["effective"] / counts["total"] if counts["total"] else 0
                if fitness < LOW_FITNESS_THRESHOLD:
                    proposals.append({
                        "type": "gap",
                        "drift": drift_type,
                        "severity": "*",
                        "query": qt,
                        "reason": f"Validated {drift_type} pattern with {counts['total']} outcomes "
                                  f"for {qt} queries (fitness {fitness:.2f}). No query-specific strategy exists.",
                        "suggestion": _suggest_template(drift_type, qt),
                        "evidence": counts,
                        "epoch": time.time(),
                    })

    return proposals


def _find_refinements(strategies: list, outcomes: list) -> list[dict]:
    """Find strategies with low effectiveness for specific query types."""
    proposals = []

    # Group outcomes by (drift_type, query_type)
    grouped = {}
    for o in outcomes:
        qt = o.get("query_type", "ambiguous")
        for cat in o.get("categories", []):
            key = (cat, qt)
            grouped.setdefault(key, []).append(o)

    for (drift_type, qt), group in grouped.items():
        if len(group) < MIN_OUTCOMES_FOR_REFINEMENT:
            continue

        effective = sum(1 for o in group if o.get("effective"))
        fitness = effective / len(group)

        if fitness < LOW_FITNESS_THRESHOLD:
            # Check if there's already a specific strategy for this combo
            has_specific = _strategy_exists(strategies, drift_type, "low", qt) or \
                           _strategy_exists(strategies, drift_type, "high", qt)

            if has_specific:
                proposals.append({
                    "type": "refinement",
                    "drift": drift_type,
                    "severity": "*",
                    "query": qt,
                    "reason": f"Existing {drift_type} strategy for {qt} queries has "
                              f"fitness {fitness:.2f} ({effective}/{len(group)}). Needs revision.",
                    "suggestion": _suggest_template(drift_type, qt),
                    "evidence": {"total": len(group), "effective": effective, "rate": fitness},
                    "epoch": time.time(),
                })

    return proposals


def _find_suppressions(strategies: list, outcomes: list) -> list[dict]:
    """Find strategies that fire frequently but don't help."""
    proposals = []

    if len(outcomes) < MIN_OUTCOMES_FOR_REFINEMENT:
        return proposals

    # Count how often each drift type appears and its effectiveness
    drift_counts = {}
    for o in outcomes:
        for cat in o.get("categories", []):
            drift_counts.setdefault(cat, {"total": 0, "effective": 0})
            drift_counts[cat]["total"] += 1
            if o.get("effective"):
                drift_counts[cat]["effective"] += 1

    total_outcomes = len(outcomes)

    for drift_type, counts in drift_counts.items():
        fire_rate = counts["total"] / total_outcomes
        fitness = counts["effective"] / counts["total"] if counts["total"] else 0

        if fire_rate > HIGH_FIRE_RATE and fitness < LOW_FITNESS_THRESHOLD:
            proposals.append({
                "type": "suppression",
                "drift": drift_type,
                "severity": "*",
                "query": "*",
                "reason": f"{drift_type} corrections fire in {fire_rate:.0%} of sessions "
                          f"but only {fitness:.0%} are effective. Consider relaxing thresholds "
                          f"or suppressing this correction type.",
                "suggestion": f"Raise {drift_type} threshold or add empty-template suppression.",
                "evidence": {"fire_rate": fire_rate, **counts},
                "epoch": time.time(),
            })

    return proposals


def _suggest_template(drift_type: str, query_type: str) -> str:
    """Generate a suggested correction template for a drift+query combination."""
    templates = {
        ("filler", "emotional"): "",  # Emotional queries may warrant softer framing
        ("filler", "meta"): "[Prior response to meta-query contained filler. Answer directly.]",
        ("preamble", "factual"): "[Prior factual response had preamble. Data first.]",
        ("preamble", "code"): "[Prior code response had preamble. Code first, explain after.]",
        ("density", "emotional"): "",  # Lower density may be appropriate for emotional support
        ("density", "meta"): "[Prior meta-response had low density. Be specific.]",
    }
    return templates.get((drift_type, query_type),
                         f"[Prior {query_type} response had {drift_type} drift. Correct.]")


def apply_proposals(indices: list[int]) -> dict:
    """Apply selected staged proposals to corrections.json.

    Args:
        indices: 0-based indices of proposals to apply

    Returns:
        Report of what was applied.
    """
    staged = _load_staged()
    corrections = _load_corrections()
    strategies = corrections.get("strategies", [])

    applied = []
    for i in sorted(indices, reverse=True):
        if i < 0 or i >= len(staged):
            continue
        proposal = staged[i]

        if proposal["type"] == "suppression":
            # Suppression proposals don't add strategies — they suggest threshold changes
            applied.append({"action": "threshold_suggestion", **proposal})
        else:
            # Gap or refinement: add/replace strategy
            template = proposal.get("suggestion", "")
            drift = proposal["drift"]
            query = proposal["query"]

            # Remove existing matching strategies
            strategies = [
                s for s in strategies
                if not (s["drift"] == drift and s["query"] == query)
            ]

            if template:  # Empty template = intentional suppression
                strategies.append({
                    "drift": drift,
                    "severity": "*",
                    "query": query,
                    "template": template,
                    "source": "foundry",
                })
            else:
                strategies.append({
                    "drift": drift,
                    "severity": "*",
                    "query": query,
                    "template": "",
                    "note": f"Foundry: suppressed for {query} queries.",
                    "source": "foundry",
                })

            applied.append({"action": "strategy_added", "drift": drift, "query": query})

        staged.pop(i)

    # Save updated corrections and staged list
    corrections["strategies"] = strategies
    corrections["version"] = corrections.get("version", 1) + 1

    path = _plugin_root() / "data" / "corrections.json"
    with open(path, "w") as f:
        file_lock(f)
        json.dump(corrections, f, indent=2)
        file_unlock(f)

    _save_staged(staged)

    return {
        "applied": len(applied),
        "remaining_staged": len(staged),
        "corrections_version": corrections["version"],
        "details": applied,
    }


if __name__ == "__main__":
    if "--analyze" in sys.argv:
        result = analyze()
        print(json.dumps(result, indent=2))
    elif "--apply" in sys.argv:
        # Usage: --apply 0,1,3
        idx_arg = sys.argv[sys.argv.index("--apply") + 1] if len(sys.argv) > sys.argv.index("--apply") + 1 else ""
        indices = [int(i) for i in idx_arg.split(",") if i.strip().isdigit()]
        result = apply_proposals(indices)
        print(json.dumps(result, indent=2))
    elif "--staged" in sys.argv:
        staged = _load_staged()
        print(json.dumps(staged, indent=2))
    else:
        print("Usage: foundry.py --analyze | --staged | --apply 0,1,3")
