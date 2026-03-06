---
name: foundry
description: Review and apply LCARS strategy proposals crystallized from observed drift patterns
---

# LCARS Foundry

Review correction strategies that the plugin has crystallized from observed patterns. Proposals are staged for your approval — nothing is auto-applied.

## How It Works

The Foundry observes three signals:
1. **Gaps**: validated drift patterns that lack query-type-specific correction strategies
2. **Refinements**: existing strategies with low correction fitness (< 50% effective)
3. **Suppressions**: strategies that fire frequently but rarely help (noise)

Proposals are staged in `~/.claude/lcars/memory/staged-strategies.json` and only applied when you approve them here.

## Instructions

When user runs `/lcars:foundry`:

### 1. Run Analysis

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/foundry.py --analyze
```

This scans patterns and outcomes, generates new proposals if warranted, and reports what it found.

### 2. Show Staged Proposals

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/foundry.py --staged
```

For each proposal, display:
- **Index**: number for selection
- **Type**: gap / refinement / suppression
- **Target**: drift type + query type
- **Reason**: why this was proposed (with evidence counts and fitness rate)
- **Suggestion**: the proposed correction template (or suppression)

### 3. Ask for User Decision

Present the proposals and ask which to apply. Options:
- Apply all
- Apply specific indices (comma-separated)
- Reject all (clear staged)
- Skip (leave staged for later)

### 4. Apply Selected

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/foundry.py --apply {indices}
```

Report what was applied: strategies added to `corrections.json`, version bumped, remaining staged count.

### 5. For Suppression Proposals

Suppression proposals suggest threshold changes rather than new strategies. Present them as recommendations for `/lcars:calibrate` rather than applying directly.

### 6. Tool Proposals

The analysis output includes `tool_proposals` — repeated tool sequences detected in `tool-usage.jsonl` that could be crystallized into tool-factory tools.

If tool proposals exist, show them from `~/.claude/lcars/memory/staged-tools.json`:

```bash
python3 -c "import sys, json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/lib'); from staging import load_staged; print(json.dumps(load_staged(), indent=2))"
```

For each tool proposal, display:
- **Name**: proposed tool name
- **Pattern**: the tool sequence detected
- **Evidence**: occurrence count and session count

If user approves a tool proposal:
1. Call `factory__create_tool` via MCP with the tool's name and description
2. After MCP confirms, mark registered:
   ```bash
   python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/lib'); from staging import mark_registered; mark_registered('TOOL_ID', 'MCP_NAME')"
   ```

## When There's Nothing Staged

If no proposals exist and analysis finds nothing new, report:
- How many patterns and outcomes were analyzed
- That current strategies have adequate coverage
- Suggest running longer or checking `/lcars:dashboard` for current fitness rate
