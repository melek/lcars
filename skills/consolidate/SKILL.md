---
name: consolidate
description: Manually trigger LCARS pattern consolidation from session summaries
---

# LCARS Consolidate

Manually run pattern consolidation from accumulated session summaries. Normally this runs automatically (amortized during PreCompact), but this skill lets you trigger it on demand and see the results.

## Instructions

When user runs `/lcars:consolidate`:

1. Run consolidation:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/consolidate.py --consolidate
```

2. Display the result:
   - `insufficient_data`: report how many sessions exist vs. the 5-session minimum
   - `consolidated`: report patterns validated, added, and marked stale

3. If patterns were validated or changed, read `~/.claude/lcars/memory/patterns.json` and display:
   - Each pattern's drift type, session count, unique days, date range, and status
   - Any stale patterns that were superseded

4. If no changes, report that current patterns are up to date.

## Context

Consolidation applies overfit gates before accepting patterns:
- **5+ sessions**: pattern must appear across at least 5 scoring sessions
- **3+ calendar days**: prevents single-day anomalies from crystallizing
- **Contradiction check**: if an old pattern no longer meets gates, it's marked stale

These gates are inspired by OpenClaw Foundry's crystallization threshold — observe before codifying.
