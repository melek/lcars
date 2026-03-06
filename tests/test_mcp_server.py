"""Tests for tool_factory/server.py — LCARS tool factory MCP server.

Tests the handler functions directly (no MCP transport needed).
Uses lcars_tmpdir fixture for isolated registry + script storage.
"""

import json
import os
import stat
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Add repo root so tool_factory package is importable
_REPO_ROOT = str(Path(__file__).parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from tool_factory import server as tf
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    tf = None

skipif_no_mcp = pytest.mark.skipif(not MCP_AVAILABLE, reason="mcp pip package not installed")


@pytest.fixture
def notify():
    return AsyncMock()


def _make_create_args(name="test_tool", description="A test tool", script=None):
    if script is None:
        script = 'import json, sys; args = json.load(sys.stdin); print(json.dumps({"result": "ok"}))'
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {"x": {"type": "string"}},
        },
        "script_content": script,
    }


def _patch_server_paths(lcars_tmpdir, monkeypatch):
    """Patch server module paths to use temp directory."""
    tdir = Path(str(lcars_tmpdir)) / "tools"
    tdir.mkdir(exist_ok=True)
    adir = tdir / "archive"
    adir.mkdir(exist_ok=True)
    monkeypatch.setattr(tf, "TOOLS_DIR", tdir)
    monkeypatch.setattr(tf, "ARCHIVE_DIR", adir)


@skipif_no_mcp
class TestHandleCreate:
    @pytest.fixture(autouse=True)
    def _setup(self, lcars_tmpdir, monkeypatch):
        _patch_server_paths(lcars_tmpdir, monkeypatch)

    @pytest.mark.asyncio
    async def test_create_valid_tool(self, notify):
        result = await tf.handle_create(_make_create_args(), notify)
        assert not result.isError
        assert "created and registered" in result.content[0].text
        notify.assert_awaited_once()

        tool = tf._get_factory_tool("test_tool")
        assert tool is not None
        assert tool["provenance"] == "user-created"
        assert tool["status"] == "active"
        assert tool["handler"]["type"] == "python"

        script = tf._script_path("test_tool")
        assert script.exists()
        assert script.stat().st_mode & stat.S_IEXEC

    @pytest.mark.asyncio
    async def test_create_invalid_name(self, notify):
        result = await tf.handle_create(_make_create_args(name="invalid-name"), notify)
        assert result.isError
        assert "Invalid tool name" in result.content[0].text
        notify.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_factory_prefix_rejected(self, notify):
        result = await tf.handle_create(_make_create_args(name="factory__bad"), notify)
        assert result.isError
        assert "factory__" in result.content[0].text

    @pytest.mark.asyncio
    async def test_create_duplicate_rejected(self, notify):
        await tf.handle_create(_make_create_args(), notify)
        result = await tf.handle_create(_make_create_args(), notify)
        assert result.isError
        assert "already exists" in result.content[0].text


@skipif_no_mcp
class TestHandleList:
    @pytest.fixture(autouse=True)
    def _setup(self, lcars_tmpdir, monkeypatch):
        _patch_server_paths(lcars_tmpdir, monkeypatch)

    def test_empty_list(self):
        result = tf.handle_list()
        assert "No dynamic tools" in result.content[0].text

    @pytest.mark.asyncio
    async def test_list_after_create(self, notify):
        await tf.handle_create(_make_create_args(name="tool_a", description="Tool A"), notify)
        await tf.handle_create(_make_create_args(name="tool_b", description="Tool B"), notify)
        result = tf.handle_list()
        assert "2 dynamic tool(s)" in result.content[0].text


@skipif_no_mcp
class TestHandleGet:
    @pytest.fixture(autouse=True)
    def _setup(self, lcars_tmpdir, monkeypatch):
        _patch_server_paths(lcars_tmpdir, monkeypatch)

    @pytest.mark.asyncio
    async def test_get_existing(self, notify):
        await tf.handle_create(_make_create_args(), notify)
        result = tf.handle_get({"name": "test_tool"})
        assert not result.isError
        assert "--- Script" in result.content[0].text

    def test_get_nonexistent(self):
        result = tf.handle_get({"name": "nonexistent"})
        assert result.isError


@skipif_no_mcp
class TestArchiveRestoreCycle:
    @pytest.fixture(autouse=True)
    def _setup(self, lcars_tmpdir, monkeypatch):
        _patch_server_paths(lcars_tmpdir, monkeypatch)

    @pytest.mark.asyncio
    async def test_archive_preserves_stats(self, notify):
        import registry
        await tf.handle_create(_make_create_args(), notify)
        tool = tf._get_factory_tool("test_tool")
        registry.record_usage(tool["id"], success=True)
        registry.record_usage(tool["id"], success=True)
        registry.record_usage(tool["id"], success=False)

        tool_before = tf._get_factory_tool("test_tool")
        assert tool_before["lifetime_invocations"] == 3
        assert tool_before["lifetime_successes"] == 2

        await tf.handle_archive({"name": "test_tool"}, notify)
        tool_after = tf._get_factory_tool("test_tool")
        assert tool_after["status"] == "archived"
        assert tool_after["lifetime_invocations"] == 3
        assert tool_after["lifetime_successes"] == 2
        assert tool_after["tier"] == tool_before["tier"]

    @pytest.mark.asyncio
    async def test_restore_after_archive(self, notify):
        await tf.handle_create(_make_create_args(), notify)
        await tf.handle_archive({"name": "test_tool"}, notify)
        assert not tf._script_path("test_tool").exists()

        await tf.handle_restore({"name": "test_tool"}, notify)
        tool = tf._get_factory_tool("test_tool")
        assert tool["status"] == "active"
        assert tf._script_path("test_tool").exists()

    @pytest.mark.asyncio
    async def test_archive_nonexistent_fails(self, notify):
        result = await tf.handle_archive({"name": "nonexistent"}, notify)
        assert result.isError


@skipif_no_mcp
class TestHandleDelete:
    @pytest.fixture(autouse=True)
    def _setup(self, lcars_tmpdir, monkeypatch):
        _patch_server_paths(lcars_tmpdir, monkeypatch)

    @pytest.mark.asyncio
    async def test_delete_active_tool(self, notify):
        await tf.handle_create(_make_create_args(), notify)
        result = await tf.handle_delete({"name": "test_tool"}, notify)
        assert not result.isError
        assert "permanently deleted" in result.content[0].text
        assert tf._get_factory_tool("test_tool") is None
        assert not tf._script_path("test_tool").exists()

    @pytest.mark.asyncio
    async def test_delete_archived_tool(self, notify):
        await tf.handle_create(_make_create_args(), notify)
        await tf.handle_archive({"name": "test_tool"}, notify)
        result = await tf.handle_delete({"name": "test_tool"}, notify)
        assert not result.isError
        assert tf._get_factory_tool("test_tool") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, notify):
        result = await tf.handle_delete({"name": "nope"}, notify)
        assert result.isError


@skipif_no_mcp
class TestToolExecution:
    @pytest.fixture(autouse=True)
    def _setup(self, lcars_tmpdir, monkeypatch):
        _patch_server_paths(lcars_tmpdir, monkeypatch)

    @pytest.mark.asyncio
    async def test_execute_tool(self, notify):
        script = 'import json, sys; args = json.load(sys.stdin); print(json.dumps({"echo": args.get("msg", "")}))'
        await tf.handle_create(_make_create_args(script=script), notify)
        result = await tf.execute_tool("test_tool", {"msg": "hello"})
        assert not result.isError
        data = json.loads(result.content[0].text)
        assert data["echo"] == "hello"

    @pytest.mark.asyncio
    async def test_execute_records_usage(self, notify):
        await tf.handle_create(_make_create_args(), notify)
        await tf.execute_tool("test_tool", {})
        tool = tf._get_factory_tool("test_tool")
        assert tool["lifetime_invocations"] == 1
        assert tool["lifetime_successes"] == 1

    @pytest.mark.asyncio
    async def test_execute_failing_script(self, notify):
        await tf.handle_create(_make_create_args(script="import sys; sys.exit(1)"), notify)
        result = await tf.execute_tool("test_tool", {})
        assert result.isError
        tool = tf._get_factory_tool("test_tool")
        assert tool["lifetime_invocations"] == 1
        assert tool["lifetime_successes"] == 0

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        result = await tf.execute_tool("nonexistent", {})
        assert result.isError


@skipif_no_mcp
class TestRegistryIntegration:
    @pytest.fixture(autouse=True)
    def _setup(self, lcars_tmpdir, monkeypatch):
        _patch_server_paths(lcars_tmpdir, monkeypatch)

    @pytest.mark.asyncio
    async def test_created_tool_in_registry_list_active(self, notify):
        import registry
        await tf.handle_create(_make_create_args(), notify)
        names = {t["name"] for t in registry.list_active()}
        assert "test_tool" in names

    @pytest.mark.asyncio
    async def test_archived_tool_not_in_active(self, notify):
        import registry
        await tf.handle_create(_make_create_args(), notify)
        await tf.handle_archive({"name": "test_tool"}, notify)
        names = {t["name"] for t in registry.list_active()}
        assert "test_tool" not in names
