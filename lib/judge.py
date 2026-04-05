#!/usr/bin/env python3
"""Hybrid scoring utilities: escalation gate and response validation.

The judge evaluation itself runs as a prompt-type hook in hooks.json,
using Claude Code's own auth. This module provides the deterministic
escalation gate (which responses are borderline?) and validation
(parsing structured judge output).
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

DIMENSIONS = ("SyA", "VDet", "EpAd", "EPad")


def should_escalate(score: dict, query_type: str) -> tuple[bool, str]:
    """Deterministic escalation gate.

    Returns (should_escalate, reason) based on scoring signals.
    """
    from thresholds import get as get_threshold

    padding = score.get("padding_count", 0)
    density = score.get("info_density", 1.0)
    position = score.get("answer_position", 0)
    density_threshold = get_threshold("density", query_type)

    # Clearly clean: no filler and density well above threshold
    if padding == 0 and density >= density_threshold + 0.05:
        return (False, "clearly_clean")

    # Clear drift: high filler count — deterministic score is sufficient
    if padding >= 3:
        return (False, "clear_drift")

    # Borderline filler: 1-2 hits may be false positive or contextual
    if 1 <= padding <= 2:
        return (True, "borderline_filler")

    # Borderline density: near threshold — regex can't distinguish
    if abs(density - density_threshold) <= 0.03:
        return (True, "borderline_density")

    # Novel filler: preamble without filler patterns
    if position > 0 and padding == 0:
        return (True, "novel_filler")

    return (False, "no_criteria_met")


def validate_response(raw_json: str) -> dict | None:
    """Parse and validate judge response.

    Expects JSON with 4 integer fields (SyA, VDet, EpAd, EPad).
    Clamps values to [0, 3]. Returns None on any validation failure.
    """
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(data, dict):
        return None

    result = {}
    for dim in DIMENSIONS:
        if dim not in data:
            return None
        try:
            val = int(data[dim])
        except (ValueError, TypeError):
            return None
        result[dim] = max(0, min(3, val))

    return result
