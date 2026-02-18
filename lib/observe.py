#!/usr/bin/env python3
"""PostToolUse observer. Logs tool usage patterns silently.

Async hook — no blocking, no injection. Appends one JSONL line per tool call.
Data accumulates for Phase 2 pattern analysis (correlating tool usage with drift).
"""

import json
import os
import sys
import time


def _tool_log_path():
    lcars_dir = os.path.join(os.path.expanduser("~"), ".claude", "lcars")
    os.makedirs(lcars_dir, exist_ok=True)
    return os.path.join(lcars_dir, "tool-usage.jsonl")


def hook_main():
    """PostToolUse hook entry point."""
    hook_input = json.load(sys.stdin)

    tool_name = hook_input.get("tool_name", "unknown")
    tool_response = hook_input.get("tool_response", {})

    # Minimal logging: name, timestamp, success indicator
    entry = {
        "ts": time.time(),
        "tool": tool_name,
        "ok": not isinstance(tool_response, dict) or not tool_response.get("is_error", False),
    }

    with open(_tool_log_path(), "a") as f:
        f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    hook_main()
