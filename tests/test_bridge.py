"""Tests for lib/bridge.py — tool-factory coordination bridge."""

import json
import os
import time

import bridge
import registry


class TestStageProposal:
    def test_stage_new_proposal(self, lcars_tmpdir):
        proposal = {
            "name": "json_formatter",
            "description": "Format JSON consistently",
            "source_pattern": "tool-usage sequence",
        }
        bridge.stage_proposal(proposal)

        staged = bridge.load_staged()
        assert len(staged) == 1
        assert staged[0]["name"] == "json_formatter"
        assert staged[0]["status"] == "staged"
        assert "staged_epoch" in staged[0]

    def test_dedup_by_name(self, lcars_tmpdir):
        proposal = {"name": "json_formatter", "description": "v1"}
        bridge.stage_proposal(proposal)
        bridge.stage_proposal(proposal)

        staged = bridge.load_staged()
        assert len(staged) == 1

    def test_multiple_proposals(self, lcars_tmpdir):
        bridge.stage_proposal({"name": "tool_a", "description": "A"})
        bridge.stage_proposal({"name": "tool_b", "description": "B"})

        staged = bridge.load_staged()
        assert len(staged) == 2


class TestLoadStaged:
    def test_empty_when_no_file(self, lcars_tmpdir):
        assert bridge.load_staged() == []

    def test_corrupt_file(self, lcars_tmpdir):
        with open(bridge.STAGED_TOOLS_FILE, "w") as f:
            f.write("not json")
        assert bridge.load_staged() == []


class TestMarkRegistered:
    def test_moves_to_registry(self, lcars_tmpdir):
        bridge._save_staged_file([{
            "tool_id": "prop:formatter",
            "name": "json_formatter",
            "description": "Format JSON",
            "staged_epoch": time.time(),
        }])

        bridge.mark_registered("prop:formatter", "json_fmt")

        # Should be in registry
        tool = registry.get("cryst:json_fmt")
        assert tool is not None
        assert tool["provenance"] == "crystallized"
        assert tool["status"] == "active"

        # Should be removed from staged
        assert bridge.load_staged() == []

    def test_nonexistent_tool_noop(self, lcars_tmpdir):
        bridge._save_staged_file([{
            "tool_id": "prop:other",
            "name": "other",
            "description": "Other tool",
        }])
        bridge.mark_registered("prop:nonexistent", "nonexistent")
        # Staged unchanged
        assert len(bridge.load_staged()) == 1


class TestSyncFromFactory:
    def test_imports_new_tools(self, lcars_tmpdir):
        factory_list = [
            {"name": "epoch_time", "description": "Convert epoch timestamps"},
            {"name": "json_fmt", "description": "Format JSON"},
        ]
        bridge.sync_from_factory(factory_list)

        tools = registry.list_by_provenance("user-created")
        assert len(tools) == 2
        names = {t["name"] for t in tools}
        assert names == {"epoch_time", "json_fmt"}

    def test_skips_existing(self, lcars_tmpdir):
        # Pre-populate
        registry.upsert({
            "id": "tf:epoch_time",
            "provenance": "user-created",
            "name": "epoch_time",
            "description": "existing",
            "status": "active",
            "tier": "candidate",
            "created_epoch": time.time(),
            "last_used_epoch": 0,
            "lifetime_invocations": 0,
            "lifetime_successes": 0,
        })

        bridge.sync_from_factory([
            {"name": "epoch_time", "description": "should not duplicate"},
            {"name": "json_fmt", "description": "new tool"},
        ])

        tools = registry.list_by_provenance("user-created")
        assert len(tools) == 2

    def test_empty_list(self, lcars_tmpdir):
        bridge.sync_from_factory([])
        assert registry.list_by_provenance("user-created") == []
