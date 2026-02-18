"""Transcript parsing utilities.

Reads Claude Code JSONL transcripts to extract messages and tool calls.
Used by score.py (Stop hook) and consolidate.py (PreCompact hook).
"""

import json
from pathlib import Path


def _read_transcript(path: Path) -> list[dict]:
    """Read transcript entries from JSONL or JSON array format."""
    text = path.read_text().strip()
    if not text:
        return []

    # Try JSON array first (starts with '[')
    if text.startswith("["):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    # Fall back to JSONL
    entries = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def extract_last_assistant_text(transcript_path: str) -> str | None:
    """Extract the last assistant text block from a JSONL transcript."""
    path = Path(transcript_path)
    if not path.exists():
        return None

    last_text = None
    try:
        entries = _read_transcript(path)
        for entry in entries:
            if entry.get("type") != "assistant":
                continue
            content = entry.get("message", {}).get("content", [])
            for block in content:
                if block.get("type") == "text":
                    last_text = block["text"]
    except OSError:
        return None

    return last_text


def count_assistant_messages(transcript_path: str) -> int:
    """Count total assistant text messages in a transcript."""
    path = Path(transcript_path)
    if not path.exists():
        return 0

    count = 0
    try:
        for entry in _read_transcript(path):
            if entry.get("type") == "assistant":
                content = entry.get("message", {}).get("content", [])
                if any(b.get("type") == "text" for b in content):
                    count += 1
    except OSError:
        pass

    return count


def extract_tool_calls(transcript_path: str) -> list[dict]:
    """Extract all tool calls from a transcript. Returns list of {name, success}."""
    path = Path(transcript_path)
    if not path.exists():
        return []

    calls = []
    try:
        for entry in _read_transcript(path):
            if entry.get("type") == "assistant":
                content = entry.get("message", {}).get("content", [])
                for block in content:
                    if block.get("type") == "tool_use":
                        calls.append({
                            "name": block.get("name", "unknown"),
                            "id": block.get("id", ""),
                        })

            if entry.get("type") == "tool_result":
                tool_id = entry.get("tool_use_id", "")
                is_error = entry.get("is_error", False)
                for call in reversed(calls):
                    if call.get("id") == tool_id and "success" not in call:
                        call["success"] = not is_error
                        break
    except OSError:
        pass

    return calls
