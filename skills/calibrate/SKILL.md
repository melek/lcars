---
name: calibrate
description: Propose LCARS threshold adjustments based on accumulated scoring evidence
---

# LCARS Calibrate

Analyze scoring data and propose threshold adjustments. Changes require explicit user approval — never automatic.

## Instructions

When user runs `/lcars:calibrate`:

1. Load data from `~/.claude/lcars/`:
   - `scores.jsonl` — full score history
   - `thresholds.json` — current active thresholds
   - `memory/correction-outcomes.jsonl` — correction effectiveness
   - `memory/patterns.json` — consolidated patterns

2. Analyze for threshold misalignment:

### False Positive Detection

Look for query types where drift is frequently detected but corrections are ineffective (fitness < 0.50 for that query type). This suggests the threshold is too aggressive.

Propose: relax the threshold for that query type.

### False Negative Detection

Look for query types where scores consistently approach but don't cross thresholds (e.g., density 0.61 against 0.60 threshold repeatedly). If patterns.json shows validated drift patterns for that type, the threshold may be too lenient.

Propose: tighten the threshold for that query type.

### New Query-Type Overrides

If a query type has enough data (10+ scores) and its average metrics differ significantly from global defaults (> 1 standard deviation), propose adding a query-type-specific override.

3. Present proposals:

For each proposed change, show:
- **Current threshold**: the value now
- **Proposed threshold**: the new value
- **Evidence**: score count, fitness rate, pattern data supporting the change
- **Risk**: what could go wrong (more false positives, less correction, etc.)

4. Wait for user approval:

Ask: "Apply these changes? (yes/no/select specific proposals)"

5. If approved, update `~/.claude/lcars/thresholds.json`:

Run: `python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/lib'); from thresholds import load, save; data = load(); [apply changes]; save(data)"`

Increment the `version` field in the thresholds file.

6. Confirm what changed.

## Guardrails

- Never auto-apply. Always present and wait for approval.
- Never propose removing the global defaults — only adding overrides or adjusting existing ones.
- Never propose a density threshold below 0.40 or above 0.80. Those are the hard bounds.
- Never propose filler threshold above 2 (allowing 3+ filler phrases defeats the purpose).
- If insufficient data (< 20 total scores), say so and suggest running longer before calibrating.
