"""Unified tool registry — CRUD on tool-registry.json.

Pure data module (like store.py). No domain logic, no hook responsibilities.
Stores discovered tools, crystallized tools, and user-created tools in a
single registry at ~/.claude/lcars/memory/tool-registry.json.

Invariants:
  UniqueIds: no two entries share id
  ValidProvenance: provenance in {discovered, crystallized, user-created}
  ValidStatus: status in {staged, active, dormant, archived}
  MonotonicUsage: lifetime_invocations never decreases
  FitnessConsistency: rate = successes/invocations when invocations > 0, else null
"""

import json
import os
import time

from compat import file_lock, file_unlock, lcars_memory_dir

REGISTRY_FILE = os.path.join(lcars_memory_dir(), "tool-registry.json")

VALID_PROVENANCES = {"discovered", "crystallized", "user-created"}
VALID_STATUSES = {"staged", "active", "dormant", "archived"}


def _default_registry() -> dict:
    return {"version": 1, "tools": []}


def load() -> dict:
    """Load registry, create if missing."""
    if not os.path.exists(REGISTRY_FILE):
        return _default_registry()
    try:
        with open(REGISTRY_FILE) as f:
            file_lock(f, exclusive=False)
            data = json.load(f)
            file_unlock(f)
        if not isinstance(data, dict) or "tools" not in data:
            return _default_registry()
        return data
    except (json.JSONDecodeError, OSError):
        return _default_registry()


def save(registry: dict):
    """Atomic write with file_lock."""
    os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        file_lock(f)
        json.dump(registry, f, indent=2)
        file_unlock(f)


def get(tool_id: str) -> dict | None:
    """Lookup by ID."""
    registry = load()
    for tool in registry["tools"]:
        if tool["id"] == tool_id:
            return tool
    return None


def upsert(entry: dict):
    """Insert or update by ID.

    Pre: entry must have 'id', 'provenance', 'name', 'status'.
    Post: entry exists in registry with given values. UniqueIds maintained.
    """
    assert "id" in entry, "entry must have 'id'"
    assert entry.get("provenance") in VALID_PROVENANCES, f"invalid provenance: {entry.get('provenance')}"
    assert entry.get("status") in VALID_STATUSES, f"invalid status: {entry.get('status')}"

    registry = load()
    tools = registry["tools"]

    for i, t in enumerate(tools):
        if t["id"] == entry["id"]:
            tools[i] = entry
            save(registry)
            return

    tools.append(entry)
    save(registry)


def list_by_provenance(prov: str) -> list:
    """Filter by provenance: discovered|crystallized|user-created."""
    registry = load()
    return [t for t in registry["tools"] if t.get("provenance") == prov]


def list_active() -> list:
    """All tools with status=='active'."""
    registry = load()
    return [t for t in registry["tools"] if t.get("status") == "active"]


def record_usage(tool_id: str, success: bool):
    """Increment usage counters for a tool.

    Pre: tool_id exists in registry.
    Post: lifetime_invocations incremented by 1. MonotonicUsage maintained.
          If success, lifetime_successes incremented by 1.
          last_used_epoch updated.
    """
    registry = load()
    for tool in registry["tools"]:
        if tool["id"] == tool_id:
            tool["lifetime_invocations"] = tool.get("lifetime_invocations", 0) + 1
            if success:
                tool["lifetime_successes"] = tool.get("lifetime_successes", 0) + 1
            tool["last_used_epoch"] = time.time()
            save(registry)
            return


def mark_status(tool_id: str, status: str):
    """Set status: staged|active|dormant|archived.

    Pre: status in VALID_STATUSES.
    Post: tool's status updated. PruningPreservesData: archive changes status, never deletes.
    """
    assert status in VALID_STATUSES, f"invalid status: {status}"
    registry = load()
    for tool in registry["tools"]:
        if tool["id"] == tool_id:
            tool["status"] = status
            save(registry)
            return
