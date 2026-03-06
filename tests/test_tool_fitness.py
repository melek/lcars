"""Tests for lib/tool_fitness.py — tool fitness computation and tier management."""

import time

import registry
import tool_fitness


def _make_tool(tool_id="disc:rg", tier="candidate", invocations=0, successes=0,
               created_days_ago=0, last_used_days_ago=None, status="active"):
    now = time.time()
    entry = {
        "id": tool_id,
        "provenance": "discovered",
        "name": tool_id.split(":")[-1],
        "description": "test tool",
        "status": status,
        "tier": tier,
        "created_epoch": now - (created_days_ago * 86400),
        "last_used_epoch": now - (last_used_days_ago * 86400) if last_used_days_ago is not None else 0,
        "lifetime_invocations": invocations,
        "lifetime_successes": successes,
    }
    return entry


class TestEvaluatePromotion:
    def test_candidate_to_standard(self, lcars_tmpdir):
        tool = _make_tool(tier="candidate", invocations=6, successes=4, created_days_ago=4)
        result = tool_fitness.evaluate_promotion(tool)
        assert result == "standard"

    def test_candidate_insufficient_obs(self, lcars_tmpdir):
        tool = _make_tool(tier="candidate", invocations=3, successes=3, created_days_ago=4)
        assert tool_fitness.evaluate_promotion(tool) is None

    def test_candidate_insufficient_days(self, lcars_tmpdir):
        tool = _make_tool(tier="candidate", invocations=10, successes=8, created_days_ago=1)
        assert tool_fitness.evaluate_promotion(tool) is None

    def test_candidate_low_fitness(self, lcars_tmpdir):
        tool = _make_tool(tier="candidate", invocations=10, successes=3, created_days_ago=5)
        assert tool_fitness.evaluate_promotion(tool) is None

    def test_standard_to_promoted(self, lcars_tmpdir):
        tool = _make_tool(tier="standard", invocations=25, successes=22, created_days_ago=10)
        result = tool_fitness.evaluate_promotion(tool)
        assert result == "promoted"

    def test_standard_insufficient_for_promoted(self, lcars_tmpdir):
        tool = _make_tool(tier="standard", invocations=15, successes=14, created_days_ago=10)
        assert tool_fitness.evaluate_promotion(tool) is None

    def test_promoted_stays(self, lcars_tmpdir):
        tool = _make_tool(tier="promoted", invocations=50, successes=45, created_days_ago=30)
        assert tool_fitness.evaluate_promotion(tool) is None

    def test_no_invocations(self, lcars_tmpdir):
        tool = _make_tool(tier="candidate", invocations=0, successes=0, created_days_ago=5)
        assert tool_fitness.evaluate_promotion(tool) is None


class TestEvaluatePruning:
    def test_archive_stale_unused(self, lcars_tmpdir):
        tool = _make_tool(tier="candidate", invocations=0, last_used_days_ago=None, created_days_ago=35)
        result = tool_fitness.evaluate_pruning(tool)
        assert result == "archive"

    def test_demote_low_fitness_promoted(self, lcars_tmpdir):
        tool = _make_tool(tier="promoted", invocations=20, successes=8, created_days_ago=15)
        result = tool_fitness.evaluate_pruning(tool)
        assert result == "demote"

    def test_no_prune_active_tool(self, lcars_tmpdir):
        tool = _make_tool(tier="standard", invocations=10, successes=8, last_used_days_ago=2, created_days_ago=5)
        assert tool_fitness.evaluate_pruning(tool) is None

    def test_no_prune_candidate_with_usage(self, lcars_tmpdir):
        tool = _make_tool(tier="candidate", invocations=3, successes=3, last_used_days_ago=1, created_days_ago=2)
        assert tool_fitness.evaluate_pruning(tool) is None


class TestRecompute:
    def test_promotes_eligible_tool(self, lcars_tmpdir):
        registry.upsert(_make_tool("disc:rg", tier="candidate", invocations=6,
                                   successes=5, created_days_ago=4))
        result = tool_fitness.recompute()
        assert len(result["promoted"]) == 1
        assert result["promoted"][0]["new_tier"] == "standard"

        tool = registry.get("disc:rg")
        assert tool["tier"] == "standard"

    def test_demotes_low_fitness(self, lcars_tmpdir):
        registry.upsert(_make_tool("disc:rg", tier="promoted", invocations=20,
                                   successes=8, created_days_ago=15))
        result = tool_fitness.recompute()
        assert "disc:rg" in result["demoted"]

        tool = registry.get("disc:rg")
        assert tool["tier"] == "standard"

    def test_archives_stale(self, lcars_tmpdir):
        registry.upsert(_make_tool("disc:rg", tier="candidate", invocations=0,
                                   created_days_ago=35))
        result = tool_fitness.recompute()
        assert "disc:rg" in result["archived"]

        tool = registry.get("disc:rg")
        assert tool["status"] == "archived"

    def test_skips_already_archived(self, lcars_tmpdir):
        registry.upsert(_make_tool("disc:rg", tier="candidate", status="archived"))
        result = tool_fitness.recompute()
        assert result["tools_evaluated"] == 0

    def test_one_step_promotion(self, lcars_tmpdir):
        """Candidate can only go to standard, not skip to promoted."""
        registry.upsert(_make_tool("disc:rg", tier="candidate", invocations=50,
                                   successes=48, created_days_ago=30))
        result = tool_fitness.recompute()
        tool = registry.get("disc:rg")
        assert tool["tier"] == "standard"  # Not promoted — one step only
