"""Tool fitness computation.

Mirrors fitness.py for corrections. Reads registry usage data, computes
fitness metrics, evaluates promotion/demotion/pruning. Called from consolidate.py.

Tier system:
  candidate: not injected. Newly discovered/created.
  standard: listed in registry. 5+ obs, 3+ days, fitness >= 0.50.
  promoted: injected into session context. 20+ obs, 7+ days, fitness >= 0.80.

Invariants:
  PromotionOneStep: tier changes only one step per cycle
  OverfitGates: no promotion without MIN_OBSERVATIONS and MIN_CALENDAR_DAYS
  PruningPreservesData: archive changes status, never deletes entries
"""

import json
import os
import time
from pathlib import Path

import registry

VALID_TIERS = {"candidate", "standard", "promoted"}

# Default thresholds — overridden by data/thresholds.json if present
MIN_OBSERVATIONS = 5
MIN_CALENDAR_DAYS = 3
STALE_DAYS = 30


def _load_thresholds() -> dict:
    """Load tool fitness thresholds from data/thresholds.json."""
    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).parent.parent))
    path = plugin_root / "data" / "thresholds.json"
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("tool_fitness", {})
    except (OSError, json.JSONDecodeError):
        return {}


def _fitness_rate(tool: dict) -> float | None:
    """Compute fitness rate for a tool. None if no invocations."""
    invocations = tool.get("lifetime_invocations", 0)
    if invocations == 0:
        return None
    return tool.get("lifetime_successes", 0) / invocations


def _days_since_creation(tool: dict) -> float:
    """Calendar days since tool was created."""
    created = tool.get("created_epoch", 0)
    if created == 0:
        return 0
    return (time.time() - created) / 86400


def _days_since_last_use(tool: dict) -> float:
    """Calendar days since tool was last used."""
    last_used = tool.get("last_used_epoch", 0)
    if last_used == 0:
        return float("inf")
    return (time.time() - last_used) / 86400


def evaluate_promotion(tool: dict) -> str | None:
    """Evaluate whether a tool should be promoted one tier.

    Returns new tier or None if no change.
    Pre: tool has tier, lifetime_invocations, lifetime_successes, created_epoch.
    Post: returns at most one step up (PromotionOneStep).
    """
    thresholds = _load_thresholds()
    current_tier = tool.get("tier", "candidate")
    rate = _fitness_rate(tool)
    invocations = tool.get("lifetime_invocations", 0)
    days = _days_since_creation(tool)

    if current_tier == "candidate":
        cfg = thresholds.get("promote_to_standard", {})
        min_obs = cfg.get("min_obs", MIN_OBSERVATIONS)
        min_days = cfg.get("min_days", MIN_CALENDAR_DAYS)
        min_rate = cfg.get("min_rate", 0.50)

        if invocations >= min_obs and days >= min_days and rate is not None and rate >= min_rate:
            return "standard"

    elif current_tier == "standard":
        cfg = thresholds.get("promote_to_promoted", {})
        min_obs = cfg.get("min_obs", 20)
        min_days = cfg.get("min_days", 7)
        min_rate = cfg.get("min_rate", 0.80)

        if invocations >= min_obs and days >= min_days and rate is not None and rate >= min_rate:
            return "promoted"

    return None


def evaluate_pruning(tool: dict) -> str | None:
    """Evaluate whether a tool should be demoted or archived.

    Returns "archive"|"demote"|None.
    Post: PruningPreservesData — never deletes, only status changes.
    """
    thresholds = _load_thresholds()
    current_tier = tool.get("tier", "candidate")
    rate = _fitness_rate(tool)
    stale_days = thresholds.get("archive_zero_use_days", STALE_DAYS)
    demote_threshold = thresholds.get("demote_threshold", 0.60)

    # Archive: no usage for stale_days
    if _days_since_last_use(tool) >= stale_days and tool.get("lifetime_invocations", 0) == 0:
        return "archive"

    # Demote promoted tools with declining fitness
    if current_tier == "promoted" and rate is not None and rate < demote_threshold:
        return "demote"

    return None


def recompute() -> dict:
    """Recompute fitness for all active tools. Apply promotions and pruning.

    Returns report of changes made.
    """
    reg = registry.load()
    tools = reg["tools"]

    promoted = []
    demoted = []
    archived = []

    for tool in tools:
        if tool.get("status") not in ("active", "staged"):
            continue

        # Check promotion
        new_tier = evaluate_promotion(tool)
        if new_tier:
            tool["tier"] = new_tier
            promoted.append({"id": tool["id"], "new_tier": new_tier})

        # Check pruning
        action = evaluate_pruning(tool)
        if action == "archive":
            tool["status"] = "archived"
            archived.append(tool["id"])
        elif action == "demote":
            if tool.get("tier") == "promoted":
                tool["tier"] = "standard"
                demoted.append(tool["id"])

    registry.save(reg)

    return {
        "promoted": promoted,
        "demoted": demoted,
        "archived": archived,
        "tools_evaluated": len([t for t in tools if t.get("status") in ("active", "staged")]),
    }
