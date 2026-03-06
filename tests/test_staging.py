"""Tests for lib/staging.py — tool proposal staging for Foundry crystallization."""

import json
import os
import time

import staging
import registry


class TestStageProposal:
    def test_stage_new_proposal(self, lcars_tmpdir):
        proposal = {
            "name": "json_formatter",
            "description": "Format JSON consistently",
            "source_pattern": "tool-usage sequence",
        }
        staging.stage_proposal(proposal)

        staged = staging.load_staged()
        assert len(staged) == 1
        assert staged[0]["name"] == "json_formatter"
        assert staged[0]["status"] == "staged"
        assert "staged_epoch" in staged[0]

    def test_dedup_by_name(self, lcars_tmpdir):
        proposal = {"name": "json_formatter", "description": "v1"}
        staging.stage_proposal(proposal)
        staging.stage_proposal(proposal)

        staged = staging.load_staged()
        assert len(staged) == 1

    def test_multiple_proposals(self, lcars_tmpdir):
        staging.stage_proposal({"name": "tool_a", "description": "A"})
        staging.stage_proposal({"name": "tool_b", "description": "B"})

        staged = staging.load_staged()
        assert len(staged) == 2


class TestLoadStaged:
    def test_empty_when_no_file(self, lcars_tmpdir):
        assert staging.load_staged() == []

    def test_corrupt_file(self, lcars_tmpdir):
        with open(staging.STAGED_TOOLS_FILE, "w") as f:
            f.write("not json")
        assert staging.load_staged() == []


class TestMarkRegistered:
    def test_moves_to_registry(self, lcars_tmpdir):
        staging._save_staged_file([{
            "tool_id": "prop:formatter",
            "name": "json_formatter",
            "description": "Format JSON",
            "staged_epoch": time.time(),
        }])

        staging.mark_registered("prop:formatter", "json_fmt")

        # Should be in registry
        tool = registry.get("cryst:json_fmt")
        assert tool is not None
        assert tool["provenance"] == "crystallized"
        assert tool["status"] == "active"

        # Should be removed from staged
        assert staging.load_staged() == []

    def test_nonexistent_tool_noop(self, lcars_tmpdir):
        staging._save_staged_file([{
            "tool_id": "prop:other",
            "name": "other",
            "description": "Other tool",
        }])
        staging.mark_registered("prop:nonexistent", "nonexistent")
        # Staged unchanged
        assert len(staging.load_staged()) == 1
