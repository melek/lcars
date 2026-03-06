---
name: dashboard
description: Show LCARS scoring stats, drift history, correction fitness rate, and active patterns
---

# LCARS Dashboard

Display current plugin state: rolling stats, drift patterns, correction effectiveness, and active thresholds.

## Instructions

When user runs `/lcars:dashboard`:

1. Read the following files from `~/.claude/lcars/`:
   - `scores.jsonl` — score ledger
   - `thresholds.json` — active thresholds
   - `memory/correction-outcomes.jsonl` — correction outcomes
   - `memory/patterns.json` — consolidated patterns
   - `memory/session-summaries.jsonl` — session summaries

2. Compute and display:

### Rolling Stats (7 days)

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/lib/score.py` is available for ad-hoc scoring, but for stats, read `scores.jsonl` directly and compute:
- Total responses scored
- Drift rate (responses with filler > 0 or preamble > 0) / total
- Average info density
- Average word count
- Most common query types

### Correction Fitness

Run: `python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/lib'); from fitness import fitness_rate; import json; r = fitness_rate(); print(json.dumps(r, indent=2) if r else 'No correction data yet.')"`

Display the rate with interpretation:
- >= 0.70: "Corrections working well"
- 0.50-0.70: "Some strategies may be ineffective"
- < 0.50: "Corrections may be adding noise"
- No data: "No corrections evaluated yet"

### Active Thresholds

Read `thresholds.json` and display the global defaults plus any query-type overrides in a table.

### Validated Patterns

Read `memory/patterns.json` and list any validated or stale patterns with their session counts and date ranges.

### Tool Registry

Read `~/.claude/lcars/memory/tool-registry.json` and display tracked tools by tier:

```bash
python3 -c "
import sys, json
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/lib')
import registry
reg = registry.load()
tools = reg.get('tools', [])
by_tier = {}
for t in tools:
    tier = t.get('tier', 'candidate')
    by_tier.setdefault(tier, []).append(t)
for tier in ['promoted', 'standard', 'candidate']:
    group = by_tier.get(tier, [])
    if group:
        print(f'\n{tier.upper()} ({len(group)}):')
        for t in group:
            inv = t.get('lifetime_invocations', 0)
            rate = t.get('lifetime_successes', 0) / inv if inv > 0 else None
            rate_str = f'{rate:.0%}' if rate is not None else 'n/a'
            print(f'  {t[\"name\"]:15s}  inv={inv:3d}  fitness={rate_str:>4s}  {t.get(\"status\", \"\")}')
archived = len(by_tier.get('archived', []) + [t for t in tools if t.get('status') == 'archived'])
if archived:
    print(f'\nARCHIVED: {archived}')
"
```

Show promoted tools (injected into context), standard tools (tracked), and candidate count. Include fitness rate for tools with usage.

### Recent Drift Events

Read the last 10 entries from `scores.jsonl` that have `padding_count > 0` or `answer_position > 0`, showing timestamp, query type, and which dimensions drifted.

## Output Format

Present as a compact summary. No preambles. Data first.
