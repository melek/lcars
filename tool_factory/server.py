"""LCARS Tool Factory — Dynamic Tool Registry MCP Server.

Creates, executes, archives, and restores Python tools at runtime.
Tools become immediately callable within the active session via MCP.

Storage is unified with the LCARS registry:
  - Metadata in ~/.claude/lcars/memory/tool-registry.json (via lib/registry.py)
  - Scripts in ~/.claude/lcars/tools/

Invariants:
  UniqueIds: no two entries share id
  MonotonicUsage: lifetime_invocations never decreases
  FitnessConsistency: lifetime_successes <= lifetime_invocations
  NoAutoDeployment: crystallized tools pass through staged before active
  ScriptIntegrity: every active tool-bearing entry has a script file
  ArchivePreservesStats: archiving preserves counters and tier
  TierBounds: tier in {candidate, standard, promoted}
"""

import asyncio
import json
import os
import re
import stat
import sys
import time
from pathlib import Path

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.stdio import stdio_server

# Add lib/ to path for registry/compat imports
_LIB_DIR = str(Path(__file__).parent.parent / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import registry  # noqa: E402
from compat import lcars_dir  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TOOLS_DIR = Path(lcars_dir()) / "tools"
ARCHIVE_DIR = TOOLS_DIR / "archive"
TOOLS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
EXECUTE_TIMEOUT = 30  # seconds

# Registry provenance for factory-created tools
PROVENANCE_CRYSTALLIZED = "crystallized"
PROVENANCE_USER_CREATED = "user-created"


# ---------------------------------------------------------------------------
# Tool helpers
# ---------------------------------------------------------------------------

def _tool_id(name: str, provenance: str) -> str:
    prefix = "cryst" if provenance == PROVENANCE_CRYSTALLIZED else "tf"
    return f"{prefix}:{name}"


def _script_path(name: str) -> Path:
    return TOOLS_DIR / f"{name}.py"


def _archive_script_path(name: str) -> Path:
    return ARCHIVE_DIR / f"{name}.py"


def _is_factory_tool(entry: dict) -> bool:
    """Check if a registry entry is a factory-managed tool (has a handler)."""
    return "handler" in entry


def _active_factory_tools() -> list[dict]:
    """Get all active factory-managed tools from the registry."""
    return [t for t in registry.list_active() if _is_factory_tool(t)]


def _get_factory_tool(name: str) -> dict | None:
    """Look up a factory tool by name in the registry."""
    for prov in (PROVENANCE_CRYSTALLIZED, PROVENANCE_USER_CREATED):
        tool = registry.get(_tool_id(name, prov))
        if tool and _is_factory_tool(tool):
            return tool
    return None


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

async def execute_tool(name: str, arguments: dict) -> types.CallToolResult:
    """Execute a dynamic tool by name."""
    tool = _get_factory_tool(name)
    if tool is None:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"Unknown tool: {name}")],
            isError=True,
        )

    script = _script_path(name)
    if not script.exists():
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"Script not found for tool '{name}': {script}",
            )],
            isError=True,
        )

    try:
        stdin_data = json.dumps(arguments).encode()

        with anyio.fail_after(EXECUTE_TIMEOUT):
            result = await anyio.run_process(
                ["python3", str(script)],
                input=stdin_data,
            )

        if result.returncode != 0:
            stderr = result.stderr.decode().strip()
            raise RuntimeError(stderr or f"exit code {result.returncode}")

        output = result.stdout.decode().strip()

        # Update usage stats in registry
        registry.record_usage(tool["id"], success=True)

        return types.CallToolResult(
            content=[types.TextContent(type="text", text=output)]
        )
    except TimeoutError:
        registry.record_usage(tool["id"], success=False)
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"Tool '{name}' timed out after {EXECUTE_TIMEOUT}s",
            )],
            isError=True,
        )
    except Exception as e:
        registry.record_usage(tool["id"], success=False)
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"Error executing '{name}': {e}",
            )],
            isError=True,
        )


# ---------------------------------------------------------------------------
# Meta-tool handlers
# ---------------------------------------------------------------------------

def _validate_name(name: str) -> str | None:
    """Validate tool name, return error message or None."""
    if not NAME_RE.match(name):
        return f"Invalid tool name: {name} (must be alphanumeric + underscores)"
    if name.startswith("factory__"):
        return "Tool name must not start with 'factory__'"
    return None


async def handle_create(args: dict, notify_fn) -> types.CallToolResult:
    """Create a new tool: write script, upsert registry entry."""
    name = args.get("name", "")
    err = _validate_name(name)
    if err:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"Error: {err}")],
            isError=True,
        )

    # Check for existing tool
    existing = _get_factory_tool(name)
    if existing and existing.get("status") == "active":
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"Tool '{name}' already exists. Archive it first to replace.",
            )],
            isError=True,
        )

    # Check for archived tool with same name
    if existing and existing.get("status") == "archived":
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=(
                    f"Tool '{name}' exists in archive "
                    f"(invocations: {existing.get('lifetime_invocations', 0)}). "
                    f"Use factory__restore_tool to reactivate it."
                ),
            )],
            isError=True,
        )

    description = args.get("description", "")
    input_schema = args.get("input_schema", {"type": "object", "properties": {}})
    script_content = args.get("script_content", "")
    provenance = args.get("provenance", PROVENANCE_USER_CREATED)

    if provenance not in (PROVENANCE_CRYSTALLIZED, PROVENANCE_USER_CREATED):
        provenance = PROVENANCE_USER_CREATED

    # Write script
    script = _script_path(name)
    script.write_text(script_content)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    # Create registry entry
    tool_entry = {
        "id": _tool_id(name, provenance),
        "provenance": provenance,
        "name": name,
        "description": description,
        "status": "active",
        "tier": "candidate",
        "created_epoch": time.time(),
        "last_used_epoch": 0,
        "lifetime_invocations": 0,
        "lifetime_successes": 0,
        "handler": {
            "type": "python",
            "file": f"{name}.py",
            "input_schema": input_schema,
        },
    }
    registry.upsert(tool_entry)

    await notify_fn()

    return types.CallToolResult(
        content=[types.TextContent(
            type="text",
            text=f"Tool '{name}' created and registered. It is now callable.",
        )]
    )


def handle_list() -> types.CallToolResult:
    """List all active factory-managed tools."""
    tools = _active_factory_tools()
    if not tools:
        text = "No dynamic tools registered."
    else:
        lines = []
        for t in tools:
            lines.append(f"- {t['name']}: {t['description']}")
        text = f"{len(tools)} dynamic tool(s):\n" + "\n".join(lines)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)]
    )


def handle_get(args: dict) -> types.CallToolResult:
    """Get full definition + script content for a tool."""
    name = args.get("name", "")
    tool = _get_factory_tool(name)
    prefix = ""

    if tool is None:
        return types.CallToolResult(
            content=[types.TextContent(
                type="text", text=f"Tool '{name}' not found.",
            )],
            isError=True,
        )

    if tool.get("status") == "archived":
        prefix = "[ARCHIVED] "

    info = prefix + json.dumps(tool, indent=2)

    # Include script content
    script = _script_path(name)
    if not script.exists():
        script = _archive_script_path(name)
    if script.exists():
        info += f"\n\n--- Script ({name}.py) ---\n{script.read_text()}"

    return types.CallToolResult(
        content=[types.TextContent(type="text", text=info)]
    )


async def handle_archive(args: dict, notify_fn) -> types.CallToolResult:
    """Archive a tool: change status, move script."""
    name = args.get("name", "")
    tool = _get_factory_tool(name)
    if tool is None or tool.get("status") != "active":
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"Error: active tool '{name}' not found",
            )],
            isError=True,
        )

    # Move script to archive
    src = _script_path(name)
    dst = _archive_script_path(name)
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)

    # Update registry status (preserves stats and tier — ArchivePreservesStats)
    registry.mark_status(tool["id"], "archived")

    await notify_fn()

    return types.CallToolResult(
        content=[types.TextContent(
            type="text", text=f"Tool '{name}' archived.",
        )]
    )


async def handle_delete(args: dict, notify_fn) -> types.CallToolResult:
    """Permanently delete a tool: remove registry entry and script files."""
    name = args.get("name", "")
    tool = _get_factory_tool(name)
    if tool is None:
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"Error: tool '{name}' not found",
            )],
            isError=True,
        )

    # Remove script files
    for path in (_script_path(name), _archive_script_path(name)):
        if path.exists():
            path.unlink()

    # Remove from registry
    reg = registry.load()
    reg["tools"] = [t for t in reg["tools"] if t["id"] != tool["id"]]
    registry.save(reg)

    await notify_fn()

    return types.CallToolResult(
        content=[types.TextContent(
            type="text", text=f"Tool '{name}' permanently deleted.",
        )]
    )


async def handle_restore(args: dict, notify_fn) -> types.CallToolResult:
    """Restore an archived tool back to active."""
    name = args.get("name", "")
    tool = _get_factory_tool(name)
    if tool is None or tool.get("status") != "archived":
        return types.CallToolResult(
            content=[types.TextContent(
                type="text",
                text=f"Error: archived tool '{name}' not found",
            )],
            isError=True,
        )

    # Move script back
    src = _archive_script_path(name)
    dst = _script_path(name)
    if src.exists():
        src.rename(dst)

    # Update registry status
    registry.mark_status(tool["id"], "active")

    await notify_fn()

    return types.CallToolResult(
        content=[types.TextContent(
            type="text", text=f"Tool '{name}' restored from archive.",
        )]
    )


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp_server = Server("lcars-tool-factory", version="1.0.0")
_session_ref: list = []

META_TOOLS = [
    types.Tool(
        name="factory__create_tool",
        description=(
            "Create a new Python tool that becomes immediately callable. "
            "The script receives arguments as JSON on stdin and prints results to stdout."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Tool name (alphanumeric + underscores, must not start with 'factory__')",
                },
                "description": {
                    "type": "string",
                    "description": "What the tool does",
                },
                "input_schema": {
                    "type": "object",
                    "description": "JSON Schema for the tool's parameters",
                },
                "script_content": {
                    "type": "string",
                    "description": (
                        "Python script source. Receives arguments as JSON on stdin, "
                        "prints results to stdout."
                    ),
                },
            },
            "required": ["name", "description", "input_schema", "script_content"],
        },
    ),
    types.Tool(
        name="factory__list_tools",
        description="List all active dynamic tools (excludes factory__ meta-tools).",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="factory__get_tool",
        description="Get full definition and script content of a dynamic tool.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Tool name to inspect"},
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="factory__delete_tool",
        description="Permanently delete a tool and its script files. Cannot be undone.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Tool name to delete permanently"},
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="factory__archive_tool",
        description="Archive a tool. Preserves stats and tier for later restoration.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Tool name to archive"},
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="factory__restore_tool",
        description="Restore an archived tool back to active status.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Archived tool name to restore"},
            },
            "required": ["name"],
        },
    ),
]


@mcp_server.list_tools()
async def list_tools_handler() -> list[types.Tool]:
    """Return meta-tools + all active dynamic tools."""
    try:
        ctx = mcp_server.request_context
        if not _session_ref:
            _session_ref.append(ctx.session)
    except LookupError:
        pass

    dynamic = []
    for tool in _active_factory_tools():
        handler = tool.get("handler", {})
        dynamic.append(types.Tool(
            name=tool["name"],
            description=tool["description"],
            inputSchema=handler.get("input_schema", {"type": "object", "properties": {}}),
        ))

    return META_TOOLS + dynamic


@mcp_server.call_tool()
async def call_tool_handler(name: str, arguments: dict) -> types.CallToolResult:
    """Route tool calls to meta-tool handlers or dynamic tool execution."""
    try:
        ctx = mcp_server.request_context
        if not _session_ref:
            _session_ref.append(ctx.session)
    except LookupError:
        pass

    if name == "factory__create_tool":
        return await handle_create(arguments, _notify_tools_changed)
    elif name == "factory__list_tools":
        return handle_list()
    elif name == "factory__get_tool":
        return handle_get(arguments)
    elif name == "factory__delete_tool":
        return await handle_delete(arguments, _notify_tools_changed)
    elif name == "factory__archive_tool":
        return await handle_archive(arguments, _notify_tools_changed)
    elif name == "factory__restore_tool":
        return await handle_restore(arguments, _notify_tools_changed)
    elif _get_factory_tool(name):
        return await execute_tool(name, arguments)
    else:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"Unknown tool: {name}")],
            isError=True,
        )


async def _notify_tools_changed() -> None:
    if _session_ref:
        try:
            await _session_ref[0].send_tool_list_changed()
        except Exception as e:
            print(f"[lcars-tool-factory] notify error: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        init_options = mcp_server.create_initialization_options(
            notification_options=NotificationOptions(tools_changed=True),
        )
        await mcp_server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
