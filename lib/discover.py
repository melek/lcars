"""Environment tool discovery.

Scans PATH for non-standard CLI tools against a curated allowlist shipped
as data/discoverable.json. Writes discovered tools to the unified registry.

Invariants:
  scan() never creates MCP tools — only registry entries with provenance="discovered"
  format_injection() output <= 50 tokens (hard cap)
  Only tools physically present at source.path remain active
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import registry
from compat import lcars_memory_dir

ENV_SCAN_FILE = os.path.join(lcars_memory_dir(), "env-scan.json")


def _plugin_root():
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent))


def load_allowlist() -> dict:
    """Read data/discoverable.json."""
    path = _plugin_root() / "data" / "discoverable.json"
    try:
        with open(path) as f:
            return json.load(f).get("tools", {})
    except (OSError, json.JSONDecodeError):
        return {}


def _resolve_tool(name: str) -> dict | None:
    """Find a tool on PATH and get its version."""
    path = shutil.which(name)
    if not path:
        return None

    version = ""
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True, text=True, timeout=5
        )
        out = result.stdout.strip() or result.stderr.strip()
        # Take first line, truncate
        if out:
            version = out.split("\n")[0][:80]
    except (subprocess.TimeoutExpired, OSError):
        pass

    return {"path": path, "version": version}


def scan() -> dict:
    """Full environment scan.

    Returns {found: int, new: int, removed: int}.
    Creates/updates registry entries for discovered tools.
    Marks missing tools as dormant.
    """
    allowlist = load_allowlist()
    if not allowlist:
        return {"found": 0, "new": 0, "removed": 0}

    found = 0
    new = 0
    removed = 0
    now = time.time()

    existing_discovered = {t["name"]: t for t in registry.list_by_provenance("discovered")}

    for name, info in allowlist.items():
        resolved = _resolve_tool(name)
        tool_id = f"disc:{name}"

        if resolved:
            found += 1
            if name not in existing_discovered:
                # New discovery
                entry = {
                    "id": tool_id,
                    "provenance": "discovered",
                    "name": name,
                    "description": info.get("description", ""),
                    "source": {
                        "path": resolved["path"],
                        "version": resolved["version"],
                        "discovered_epoch": now,
                    },
                    "status": "active",
                    "tier": "candidate",
                    "created_epoch": now,
                    "last_used_epoch": 0,
                    "lifetime_invocations": 0,
                    "lifetime_successes": 0,
                }
                registry.upsert(entry)
                new += 1
            else:
                # Update path/version if changed
                existing = existing_discovered[name]
                source = existing.get("source", {})
                if source.get("path") != resolved["path"] or source.get("version") != resolved["version"]:
                    existing["source"] = {
                        "path": resolved["path"],
                        "version": resolved["version"],
                        "discovered_epoch": source.get("discovered_epoch", now),
                    }
                if existing.get("status") == "dormant":
                    existing["status"] = "active"
                registry.upsert(existing)
        else:
            # Tool no longer on PATH
            if name in existing_discovered and existing_discovered[name].get("status") == "active":
                registry.mark_status(tool_id, "dormant")
                removed += 1

    # Save scan timestamp
    scan_cache = {"last_scan_epoch": now, "found": found, "new": new, "removed": removed}
    with open(ENV_SCAN_FILE, "w") as f:
        json.dump(scan_cache, f)

    return {"found": found, "new": new, "removed": removed}


def format_injection(tools: list) -> str:
    """Compact context line for promoted discovered tools.

    Post: output <= 50 tokens (hard cap, ~200 chars).
    """
    if not tools:
        return ""

    parts = []
    for t in tools[:3]:  # max 3 tools injected
        name = t.get("name", "?")
        desc = t.get("description", "")
        # Truncate description to keep compact
        if len(desc) > 30:
            desc = desc[:27] + "..."
        parts.append(f"{name} ({desc})")

    line = "[env: " + ", ".join(parts) + "]"

    # Hard cap at ~200 chars to stay under 50 tokens
    if len(line) > 200:
        line = line[:197] + "...]"

    return line
