"""Threshold management with query-type-aware lookup.

Reads thresholds from ~/.claude/lcars/thresholds.json (runtime, evolves via /calibrate).
Falls back to data/thresholds.json (shipped defaults) on first run.
"""

import json
import os
import shutil
from pathlib import Path


def _plugin_root():
    """Resolve plugin root from env or relative to this file."""
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent))


def _runtime_path():
    return os.path.join(os.path.expanduser("~"), ".claude", "lcars", "thresholds.json")


def _default_path():
    return _plugin_root() / "data" / "thresholds.json"


def _ensure_runtime():
    """Copy default thresholds to runtime location on first run."""
    runtime = _runtime_path()
    if not os.path.exists(runtime):
        default = _default_path()
        if default.exists():
            os.makedirs(os.path.dirname(runtime), exist_ok=True)
            shutil.copy2(str(default), runtime)


def load() -> dict:
    """Load current thresholds. Returns the full thresholds dict."""
    _ensure_runtime()
    runtime = _runtime_path()
    try:
        with open(runtime) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        # Fall back to defaults
        try:
            with open(_default_path()) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {"global": {"filler": 0, "preamble": 0, "density": 0.60}}


def get(metric: str, query_type: str = "ambiguous") -> int | float:
    """Get threshold for a metric, with query-type override if available.

    Args:
        metric: 'filler', 'preamble', or 'density'
        query_type: query classification from classify.py
    """
    data = load()

    # Check query-type-specific override first
    override = data.get("by_query_type", {}).get(query_type, {}).get(metric)
    if override is not None:
        return override

    # Fall back to global
    return data.get("global", {}).get(metric, 0)


def save(data: dict):
    """Write updated thresholds to runtime location."""
    runtime = _runtime_path()
    os.makedirs(os.path.dirname(runtime), exist_ok=True)
    with open(runtime, "w") as f:
        json.dump(data, f, indent=2)
