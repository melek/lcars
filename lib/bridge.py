"""Tool-factory coordination bridge.

File-based handoff between Foundry and tool-factory. Foundry writes proposals
to staged-tools.json. The /lcars:foundry skill reads them and instructs Claude
to call tool-factory MCP tools directly. LCARS never calls MCP itself.

Invariants:
  NoAutoDeployment: crystallized tool is never registered without user approval
  Bridge never executes tool code — only stages/coordinates
"""

import json
import os
import time

from compat import file_lock, file_unlock, lcars_memory_dir
import registry

STAGED_TOOLS_FILE = os.path.join(lcars_memory_dir(), "staged-tools.json")


def _load_staged_file() -> list[dict]:
    if not os.path.exists(STAGED_TOOLS_FILE):
        return []
    try:
        with open(STAGED_TOOLS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_staged_file(proposals: list[dict]):
    with open(STAGED_TOOLS_FILE, "w") as f:
        file_lock(f)
        json.dump(proposals, f, indent=2)
        file_unlock(f)


def stage_proposal(proposal: dict):
    """Write a tool proposal to staged-tools.json.

    Pre: proposal has 'name', 'description', 'source_pattern'.
    Post: proposal appended to staged-tools.json with status='staged'.
    """
    staged = _load_staged_file()

    # Deduplicate by name
    existing_names = {p.get("name") for p in staged}
    if proposal.get("name") in existing_names:
        return

    proposal.setdefault("status", "staged")
    proposal.setdefault("staged_epoch", time.time())
    staged.append(proposal)
    _save_staged_file(staged)


def load_staged() -> list[dict]:
    """Read staged tool proposals."""
    return _load_staged_file()


def mark_registered(tool_id: str, mcp_name: str):
    """After user approves + MCP registers, update registry and remove from staged.

    Pre: tool_id exists in staged proposals.
    Post: tool in registry with provenance='crystallized', status='active'.
          Removed from staged-tools.json.
    """
    staged = _load_staged_file()
    proposal = None
    remaining = []

    for p in staged:
        if p.get("tool_id") == tool_id:
            proposal = p
        else:
            remaining.append(p)

    if proposal is None:
        return

    # Create registry entry
    entry = {
        "id": f"cryst:{mcp_name}",
        "provenance": "crystallized",
        "name": mcp_name,
        "description": proposal.get("description", ""),
        "source": {
            "origin": "foundry",
            "mcp_name": mcp_name,
            "staged_epoch": proposal.get("staged_epoch", 0),
        },
        "status": "active",
        "tier": "candidate",
        "created_epoch": time.time(),
        "last_used_epoch": 0,
        "lifetime_invocations": 0,
        "lifetime_successes": 0,
    }
    registry.upsert(entry)
    _save_staged_file(remaining)


def sync_from_factory(factory_list: list):
    """Import user-created tool-factory tools into registry.

    Pre: factory_list is a list of dicts with 'name' and 'description'.
    Post: tools in registry with provenance='user-created'.
    """
    existing = {t["name"] for t in registry.list_by_provenance("user-created")}

    for tool in factory_list:
        name = tool.get("name", "")
        if not name or name in existing:
            continue

        entry = {
            "id": f"tf:{name}",
            "provenance": "user-created",
            "name": name,
            "description": tool.get("description", ""),
            "source": {"origin": "tool-factory"},
            "status": "active",
            "tier": "candidate",
            "created_epoch": time.time(),
            "last_used_epoch": 0,
            "lifetime_invocations": 0,
            "lifetime_successes": 0,
        }
        registry.upsert(entry)
