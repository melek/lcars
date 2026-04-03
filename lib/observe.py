#!/usr/bin/env python3
"""PostToolUse observer. Logs tool usage patterns silently.

Async hook — no blocking, no injection. Appends one JSONL line per tool call.
Data accumulates for Phase 2 pattern analysis (correlating tool usage with drift).
"""

import json
import os
import re
import sys
import time


def _tool_log_path():
    lcars_dir = os.path.join(os.path.expanduser("~"), ".claude", "lcars")
    os.makedirs(lcars_dir, exist_ok=True)
    return os.path.join(lcars_dir, "tool-usage.jsonl")


def _extract_executables(command: str) -> list[str]:
    """Extract executable names from a shell command string.

    Splits on shell operators (&&, ||, |, ;) and extracts the first
    token of each sub-command, stripping path prefixes and env var
    assignments. Returns deduplicated list of executable basenames.
    """

    # Split on shell operators
    parts = re.split(r'\s*(?:&&|\|\||[|;])\s*', command)

    executables = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Skip leading env var assignments (FOO=bar cmd)
        tokens = part.split()
        for token in tokens:
            if '=' in token and not token.startswith('-'):
                continue
            # Strip path prefix (/usr/bin/gh -> gh)
            exe = os.path.basename(token)
            if exe:
                executables.append(exe)
            break

    # Deduplicate while preserving order
    seen = set()
    result = []
    for exe in executables:
        if exe not in seen:
            seen.add(exe)
            result.append(exe)
    return result


def hook_main():
    """PostToolUse hook entry point."""
    hook_input = json.load(sys.stdin)

    tool_name = hook_input.get("tool_name", "unknown")
    tool_input = hook_input.get("tool_input", {})
    tool_response = hook_input.get("tool_response", {})

    # Minimal logging: name, timestamp, success indicator
    entry = {
        "ts": time.time(),
        "tool": tool_name,
        "ok": not isinstance(tool_response, dict) or not tool_response.get("is_error", False),
    }

    with open(_tool_log_path(), "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Update registry usage counters if tool is tracked
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        import registry
        ok = entry["ok"]

        if tool_name == "Bash" and isinstance(tool_input, dict):
            # Bash calls: attribute to CLI executables inside the command string
            command = tool_input.get("command", "")
            if command:
                for exe in _extract_executables(command):
                    reg_entry = registry.get(f"disc:{exe}")
                    if reg_entry:
                        registry.record_usage(reg_entry["id"], success=ok)
        else:
            # Non-Bash tool: direct match against registry
            reg_entry = registry.get(f"tf:{tool_name}") or registry.get(f"disc:{tool_name}")
            if reg_entry:
                registry.record_usage(reg_entry["id"], success=ok)
    except Exception:
        pass  # Non-critical — don't block hook


def subagent_main():
    """SubagentStart hook entry point. Observation only — no injection."""
    hook_input = json.load(sys.stdin)

    entry = {
        "ts": time.time(),
        "type": "subagent_start",
        "agent_type": hook_input.get("agent_type", "unknown"),
    }

    with open(_tool_log_path(), "a") as f:
        f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    if "--subagent" in sys.argv:
        subagent_main()
    else:
        hook_main()
