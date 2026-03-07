#!/usr/bin/env python3
"""SessionStart hook: assemble LCARS context for injection.

Two named context layers:
- anchor: behavioral anchor (always, ~50 tokens)
- stats: rolling session stats (if resuming after gap > 4h, ~30 tokens)

Correction injection moved to classify.py (UserPromptSubmit hook) so corrections
fire on the next user message within the same session.

Source-aware: adapts injection based on session source (startup/resume/clear/compact).
Outputs JSON with hookSpecificOutput.additionalContext.
"""

import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent))
DATA_DIR = PLUGIN_ROOT / "data"

sys.path.insert(0, str(Path(__file__).parent))
from store import last_score_age_hours, rolling_stats, append_session_marker


def _plugin_version() -> str | None:
    """Read version from plugin.json."""
    path = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(path.read_text()).get("version")
    except (OSError, json.JSONDecodeError):
        return None


def load_anchor() -> str:
    """Behavioral anchor. Always injected."""
    path = DATA_DIR / "anchor.txt"
    if path.exists():
        return path.read_text().strip()
    return ""


def load_stats(source: str = "startup") -> str:
    """Rolling stats on resume or post-compaction (gap > 4h)."""
    # Only inject stats on resume or compact — not on fresh startup
    if source not in ("resume", "compact"):
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
    # Read hook input for source detection
    source = "startup"
    try:
        hook_input = json.load(sys.stdin)
        source = hook_input.get("source", "startup")
    except (json.JSONDecodeError, EOFError):
        pass

    # Log session boundary with version
    append_session_marker(source, version=_plugin_version())

    parts = []

    anchor = load_anchor()
    if anchor:
        parts.append(anchor)

    stats = load_stats(source)
    if stats:
        parts.append(stats)

    # Environment tools line for promoted discovered tools
    try:
        import registry
        import discover
        env_tools = [t for t in registry.list_by_provenance("discovered")
                     if t.get("status") == "active" and t.get("tier") == "promoted"]
        if env_tools:
            env_line = discover.format_injection(env_tools)
            if env_line:
                parts.append(env_line)
    except Exception:
        pass  # Non-critical — don't block session start

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
