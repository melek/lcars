#!/usr/bin/env python3
"""LCARS installation diagnostic checks.

Validates Python environment, data directories, scoring pipeline, and module
imports. Used by the /lcars:setup skill to surface actionable remediation.
"""

import json
import os
import sys
import time
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent))
LIB_DIR = PLUGIN_ROOT / "lib"
DATA_DIR = PLUGIN_ROOT / "data"


def check_python() -> dict:
    """Verify Python executable and version >= 3.10."""
    v = sys.version_info
    if v >= (3, 10):
        return {
            "name": "python",
            "status": "pass",
            "detail": f"{sys.executable} ({v.major}.{v.minor}.{v.micro})",
        }
    return {
        "name": "python",
        "status": "fail",
        "detail": f"Python {v.major}.{v.minor}.{v.micro} < 3.10 required",
    }


def check_dirs() -> dict:
    """Verify ~/.claude/lcars/ exists and is writable."""
    lcars = os.path.join(os.path.expanduser("~"), ".claude", "lcars")
    if not os.path.isdir(lcars):
        return {
            "name": "dirs",
            "status": "fail",
            "detail": f"{lcars} does not exist",
        }
    if not os.access(lcars, os.W_OK):
        return {
            "name": "dirs",
            "status": "fail",
            "detail": f"{lcars} is not writable",
        }
    return {
        "name": "dirs",
        "status": "pass",
        "detail": lcars,
    }


def check_scores() -> dict:
    """Verify scores.jsonl exists with recent entries (< 24h)."""
    scores = os.path.join(os.path.expanduser("~"), ".claude", "lcars", "scores.jsonl")
    if not os.path.isfile(scores):
        return {
            "name": "scores",
            "status": "warn",
            "detail": "scores.jsonl not found (no scoring data yet)",
        }
    try:
        with open(scores, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                return {
                    "name": "scores",
                    "status": "warn",
                    "detail": "scores.jsonl is empty",
                }
            f.seek(max(size - 4096, 0))
            lines = f.read().decode().strip().split("\n")
        last = json.loads(lines[-1])
        age_h = (time.time() - last.get("epoch", 0)) / 3600
        if age_h > 24:
            return {
                "name": "scores",
                "status": "warn",
                "detail": f"Last entry {age_h:.1f}h ago (> 24h)",
            }
        return {
            "name": "scores",
            "status": "pass",
            "detail": f"Last entry {age_h:.1f}h ago",
        }
    except (json.JSONDecodeError, OSError, IndexError) as e:
        return {
            "name": "scores",
            "status": "fail",
            "detail": f"Error reading scores.jsonl: {e}",
        }


def check_thresholds() -> dict:
    """Verify thresholds.json is present and valid JSON."""
    path = DATA_DIR / "thresholds.json"
    if not path.is_file():
        return {
            "name": "thresholds",
            "status": "fail",
            "detail": f"{path} not found",
        }
    try:
        data = json.loads(path.read_text())
        if "global" not in data:
            return {
                "name": "thresholds",
                "status": "warn",
                "detail": "thresholds.json missing 'global' key",
            }
        return {
            "name": "thresholds",
            "status": "pass",
            "detail": f"v{data.get('version', '?')}, {len(data.get('by_query_type', {}))} overrides",
        }
    except (json.JSONDecodeError, OSError) as e:
        return {
            "name": "thresholds",
            "status": "fail",
            "detail": f"Invalid JSON: {e}",
        }


def check_imports() -> dict:
    """Verify core lib modules are importable."""
    sys.path.insert(0, str(LIB_DIR))
    missing = []
    for mod_name in ("score", "inject", "classify"):
        try:
            __import__(mod_name)
        except ImportError as e:
            missing.append(f"{mod_name} ({e})")
    if missing:
        return {
            "name": "imports",
            "status": "fail",
            "detail": f"Cannot import: {', '.join(missing)}",
        }
    return {
        "name": "imports",
        "status": "pass",
        "detail": "score, inject, classify OK",
    }


def check_scoring() -> dict:
    """Score a known test string and verify expected output."""
    sys.path.insert(0, str(LIB_DIR))
    try:
        from score import score_response

        result = score_response("Great question! I'd be happy to help you with that.")
        if not isinstance(result, dict):
            return {
                "name": "scoring",
                "status": "fail",
                "detail": f"score_response returned {type(result).__name__}, expected dict",
            }
        if result.get("padding_count", 0) < 1:
            return {
                "name": "scoring",
                "status": "warn",
                "detail": f"Expected filler detection; got padding_count={result.get('padding_count')}",
            }
        return {
            "name": "scoring",
            "status": "pass",
            "detail": f"padding={result['padding_count']}, density={result['info_density']}",
        }
    except Exception as e:
        return {
            "name": "scoring",
            "status": "fail",
            "detail": str(e),
        }


def run_all_checks() -> list[dict]:
    """Run all diagnostic checks and return results."""
    return [
        check_python(),
        check_dirs(),
        check_scores(),
        check_thresholds(),
        check_imports(),
        check_scoring(),
    ]


STATUS_SYMBOLS = {"pass": "+", "fail": "X", "warn": "!"}


if __name__ == "__main__":
    results = run_all_checks()
    max_name = max(len(r["name"]) for r in results)
    for r in results:
        sym = STATUS_SYMBOLS.get(r["status"], "?")
        print(f"  [{sym}] {r['name']:<{max_name}}  {r['detail']}")
    failures = sum(1 for r in results if r["status"] == "fail")
    if failures:
        print(f"\n{failures} check(s) failed.")
        sys.exit(1)
    else:
        print("\nAll checks passed.")
