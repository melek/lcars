#!/usr/bin/env python3
"""SessionStart hook: assemble LCARS context for injection.

Tier 1: micro-c1.txt behavioral anchor (always)
Tier 2: targeted drift correction (if drift.json exists)
Tier 3: rolling session stats (if resuming after gap > 4h)

Outputs JSON with hookSpecificOutput.additionalContext.
"""

import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent))
DATA_DIR = PLUGIN_ROOT / "data"

sys.path.insert(0, str(Path(__file__).parent))
from store import read_and_clear_drift_flag, last_score_age_hours, rolling_stats


def load_tier1() -> str:
    """Tier 1: micro-c1 behavioral anchor. Always injected."""
    micro = DATA_DIR / "micro-c1.txt"
    if micro.exists():
        return micro.read_text().strip()
    return ""


def load_tier2() -> str:
    """Tier 2: drift correction. Only if drift was detected."""
    drift = read_and_clear_drift_flag()
    if not drift:
        return ""

    reasons = drift.get("reasons", [])
    parts = []
    for r in reasons:
        if r.startswith("filler:"):
            parts.append("filler detected")
        elif r.startswith("preamble:"):
            parts.append("preamble detected")
        elif r.startswith("density:"):
            parts.append("low info density")

    if not parts:
        return ""

    return f"[Prior drift: {', '.join(parts)}. Correct.]"


def load_tier3() -> str:
    """Tier 3: rolling stats on resume (gap > 4h)."""
    age = last_score_age_hours()
    if age is None or age < 4:
        return ""

    stats = rolling_stats(days=7)
    if not stats:
        return ""

    return (
        f"[7d: {stats['responses']} responses, "
        f"drift {stats['drift_rate']}, "
        f"density {stats['avg_density']}, "
        f"avg {stats['avg_words']}w]"
    )


def main():
    parts = []

    t1 = load_tier1()
    if t1:
        parts.append(t1)

    t2 = load_tier2()
    if t2:
        parts.append(t2)

    t3 = load_tier3()
    if t3:
        parts.append(t3)

    if not parts:
        return

    context = "\n".join(parts)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
