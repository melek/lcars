"""Tests for lib/discover.py — environment tool discovery."""

import json
import os
import time
from unittest.mock import patch

import discover
import registry


def _make_allowlist(tools=None):
    if tools is None:
        tools = {
            "rg": {"description": "ripgrep", "alternatives": ["grep"]},
            "fd": {"description": "fd-find", "alternatives": ["find"]},
        }
    return tools


class TestLoadAllowlist:
    def test_loads_shipped_file(self, lcars_tmpdir):
        allowlist = discover.load_allowlist()
        # Should load real data/discoverable.json
        assert isinstance(allowlist, dict)
        assert "rg" in allowlist

    def test_missing_file_returns_empty(self, lcars_tmpdir, monkeypatch):
        monkeypatch.setattr(discover, "_plugin_root", lambda: type("P", (), {"__truediv__": lambda s, x: type("P", (), {"__truediv__": lambda s, x: "/nonexistent/path"})()})())
        # Force a path that doesn't exist
        with patch("builtins.open", side_effect=OSError("no file")):
            result = discover.load_allowlist()
        assert result == {}


class TestScan:
    def test_discovers_present_tools(self, lcars_tmpdir, monkeypatch):
        monkeypatch.setattr(discover, "load_allowlist", lambda: _make_allowlist())
        monkeypatch.setattr(discover, "_resolve_tool", lambda name: {
            "rg": {"path": "/usr/bin/rg", "version": "14.1.1"},
            "fd": None,
        }.get(name))

        result = discover.scan()
        assert result["found"] == 1
        assert result["new"] == 1

        # rg should be in registry
        tool = registry.get("disc:rg")
        assert tool is not None
        assert tool["status"] == "active"
        assert tool["provenance"] == "discovered"

    def test_marks_missing_tools_dormant(self, lcars_tmpdir, monkeypatch):
        # First, populate with rg
        entry = {
            "id": "disc:rg",
            "provenance": "discovered",
            "name": "rg",
            "description": "ripgrep",
            "status": "active",
            "tier": "candidate",
            "created_epoch": time.time(),
            "last_used_epoch": 0,
            "lifetime_invocations": 0,
            "lifetime_successes": 0,
            "source": {"path": "/usr/bin/rg", "version": "14.1.1", "discovered_epoch": 0},
        }
        registry.upsert(entry)

        # Now scan with rg missing
        monkeypatch.setattr(discover, "load_allowlist", lambda: _make_allowlist())
        monkeypatch.setattr(discover, "_resolve_tool", lambda name: None)

        result = discover.scan()
        assert result["removed"] == 1

        tool = registry.get("disc:rg")
        assert tool["status"] == "dormant"

    def test_reactivates_dormant_tool(self, lcars_tmpdir, monkeypatch):
        entry = {
            "id": "disc:rg",
            "provenance": "discovered",
            "name": "rg",
            "description": "ripgrep",
            "status": "dormant",
            "tier": "candidate",
            "created_epoch": time.time(),
            "last_used_epoch": 0,
            "lifetime_invocations": 0,
            "lifetime_successes": 0,
            "source": {"path": "/usr/bin/rg", "version": "14.0.0", "discovered_epoch": 0},
        }
        registry.upsert(entry)

        monkeypatch.setattr(discover, "load_allowlist", lambda: _make_allowlist())
        monkeypatch.setattr(discover, "_resolve_tool", lambda name: {
            "rg": {"path": "/usr/bin/rg", "version": "14.1.1"},
        }.get(name))

        discover.scan()
        tool = registry.get("disc:rg")
        assert tool["status"] == "active"

    def test_empty_allowlist(self, lcars_tmpdir, monkeypatch):
        monkeypatch.setattr(discover, "load_allowlist", lambda: {})
        result = discover.scan()
        assert result == {"found": 0, "new": 0, "removed": 0}

    def test_scan_writes_cache(self, lcars_tmpdir, monkeypatch):
        monkeypatch.setattr(discover, "load_allowlist", lambda: _make_allowlist())
        monkeypatch.setattr(discover, "_resolve_tool", lambda name: None)

        discover.scan()
        assert os.path.exists(discover.ENV_SCAN_FILE)
        with open(discover.ENV_SCAN_FILE) as f:
            cache = json.load(f)
        assert "last_scan_epoch" in cache


class TestFormatInjection:
    def test_basic_format(self, lcars_tmpdir):
        tools = [
            {"name": "rg", "description": "ripgrep"},
            {"name": "fd", "description": "fd-find"},
        ]
        result = discover.format_injection(tools)
        assert result.startswith("[env: ")
        assert "rg" in result
        assert "fd" in result

    def test_empty_list(self, lcars_tmpdir):
        assert discover.format_injection([]) == ""

    def test_max_three_tools(self, lcars_tmpdir):
        tools = [{"name": f"t{i}", "description": f"tool {i}"} for i in range(5)]
        result = discover.format_injection(tools)
        # Should only include 3 tools
        assert result.count("(") <= 3

    def test_hard_cap_length(self, lcars_tmpdir):
        tools = [{"name": f"toolname{i}", "description": "a" * 50} for i in range(3)]
        result = discover.format_injection(tools)
        assert len(result) <= 200
