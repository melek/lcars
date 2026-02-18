"""Drift detection with severity classification and correction strategy selection.

Connects scoring output to the corrections decision table.
Query-type-aware thresholds eliminate false positives (e.g., code responses
with naturally lower density are not flagged).
"""

import json
import os
from pathlib import Path

# Severity classification margins
HIGH_FILLER_COUNT = 3
HIGH_PREAMBLE_WORDS = 10
HIGH_DENSITY_MARGIN = 0.10  # threshold - score > this = high severity


def _plugin_root():
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent))


def _load_corrections() -> list[dict]:
    """Load correction strategies from the decision table."""
    path = _plugin_root() / "data" / "corrections.json"
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("strategies", [])
    except (OSError, json.JSONDecodeError):
        return []


def detect(score: dict, query_type: str = "ambiguous") -> dict | None:
    """Detect drift against query-type-aware thresholds.

    Args:
        score: output from score.score_response()
        query_type: classification from classify.py

    Returns:
        Drift details dict or None if no drift detected.
        Dict includes: categories (list), severity, reasons (list), correction (str).
    """
    # Import here to avoid circular dependency at module level
    from thresholds import get as get_threshold

    categories = []
    reasons = []

    # Filler check
    filler_threshold = get_threshold("filler", query_type)
    padding = score.get("padding_count", 0)
    if padding > filler_threshold:
        categories.append("filler")
        reasons.append(f"filler:{padding}")

    # Preamble check
    preamble_threshold = get_threshold("preamble", query_type)
    position = score.get("answer_position", 0)
    if position > preamble_threshold:
        categories.append("preamble")
        reasons.append(f"preamble:{position}w")

    # Density check
    density_threshold = get_threshold("density", query_type)
    density = score.get("info_density", 1.0)
    if density < density_threshold:
        categories.append("density")
        reasons.append(f"density:{density:.3f}")

    if not categories:
        return None

    # Classify severity
    severity = _classify_severity(score, categories, density_threshold)

    # Select drift type for correction lookup
    drift_type = "compound" if len(categories) > 1 else categories[0]

    # Select correction from decision table
    correction = _select_correction(drift_type, severity, query_type, score, reasons)

    return {
        "categories": categories,
        "severity": severity,
        "reasons": reasons,
        "correction": correction,
        "query_type": query_type,
        "padding_count": score.get("padding_count", 0),
        "answer_position": score.get("answer_position", 0),
        "info_density": score.get("info_density", 0),
    }


def _classify_severity(score: dict, categories: list, density_threshold: float) -> str:
    """Classify drift severity as 'low' or 'high'."""
    if len(categories) >= 2:
        return "high"

    padding = score.get("padding_count", 0)
    if padding >= HIGH_FILLER_COUNT:
        return "high"

    position = score.get("answer_position", 0)
    if position >= HIGH_PREAMBLE_WORDS:
        return "high"

    density = score.get("info_density", 1.0)
    if density_threshold - density > HIGH_DENSITY_MARGIN:
        return "high"

    return "low"


def _select_correction(drift_type: str, severity: str, query_type: str,
                       score: dict, reasons: list) -> str:
    """Select correction template from the decision table and format it."""
    strategies = _load_corrections()

    # Find best match: exact drift+severity+query > drift+severity+wildcard > drift+wildcard+wildcard
    best = None
    best_specificity = -1

    for strategy in strategies:
        if strategy.get("drift") != drift_type:
            continue

        s_severity = strategy.get("severity", "*")
        s_query = strategy.get("query", "*")

        specificity = 0
        if s_severity == severity:
            specificity += 2
        elif s_severity == "*":
            specificity += 0
        else:
            continue  # severity doesn't match

        if s_query == query_type:
            specificity += 1
        elif s_query == "*":
            specificity += 0
        else:
            continue  # query type doesn't match

        if specificity > best_specificity:
            best = strategy
            best_specificity = specificity

    if not best:
        # Fallback: generic correction
        return f"[Prior drift: {', '.join(reasons)}. Correct.]"

    template = best.get("template", "")
    if not template:
        return ""  # Intentionally no correction (e.g., code + low density)

    # Format template with available data
    return template.format(
        count=score.get("padding_count", 0),
        position=score.get("answer_position", 0),
        density=score.get("info_density", 0),
        reasons=", ".join(reasons),
        query_type=query_type,
    )
