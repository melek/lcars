---
name: setup
description: Validate LCARS installation and diagnose issues
---

# LCARS Setup Diagnostic

Run installation checks and surface actionable fixes.

## Instructions

When user runs `/lcars:setup`:

1. Run the diagnostic script:

```bash
sh ${CLAUDE_PLUGIN_ROOT}/bin/python-shim.sh ${CLAUDE_PLUGIN_ROOT}/lib/setup.py
```

2. Present results as a table:

| Check | Status | Detail |
|-------|--------|--------|
| python | pass/fail/warn | version and path |
| dirs | pass/fail | data directory status |
| scores | pass/fail/warn | scoring ledger status |
| thresholds | pass/fail/warn | config validity |
| imports | pass/fail | module availability |
| scoring | pass/fail/warn | pipeline test result |

3. For any failures, provide platform-specific remediation:

### Python not found or too old

- **macOS**: `brew install python@3.12`
- **Linux (Debian/Ubuntu)**: `sudo apt install python3`
- **Linux (Fedora)**: `sudo dnf install python3`
- **Windows**: Install from [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12`

### Data directory missing

The directory `~/.claude/lcars/` is created automatically on first hook run. If missing:
- Verify LCARS is installed as a Claude Code plugin (`claude mcp list` or check `~/.claude/plugins/`)
- Start a new Claude Code session to trigger the SessionStart hook

### Scores empty or stale

- Scores are recorded by the Stop hook after each response
- If empty after multiple sessions, check that hooks are firing (`hooks.json` is loaded)

### Thresholds missing or invalid

- The file `data/thresholds.json` ships with the plugin
- If missing, the plugin installation may be incomplete — reinstall

### Import failures

- Ensure the plugin files are intact (no missing `lib/*.py` modules)
- Reinstall the plugin if files are missing

## Output Format

Present as a compact diagnostic summary. No preambles. Data first.
