# LCARS

Self-correcting cognitive ergonomics plugin for [Claude Code](https://claude.com/claude-code).

LCARS observes Claude responses, classifies queries, scores against cognitive load metrics, and injects targeted corrections when behavior drifts. Query-type-aware thresholds prevent false positives — a verbose code explanation isn't drift, but a verbose "what time is it" answer is.

## Install

Add as a marketplace, then install:

```bash
# In Claude Code:
/plugin marketplace add melek/lcars
/plugin install lcars@melek-lcars
```

Or load directly for testing:

```bash
claude --plugin-dir /path/to/lcars
```

## What it does

Five hooks observe and correct behavior without blocking your workflow:

| Hook | Purpose | Latency |
|------|---------|---------|
| **SessionStart** | Inject behavioral anchor + drift corrections | Sync, <100ms |
| **UserPromptSubmit** | Classify query type (factual, code, diagnostic, ...) | Async, 0ms |
| **PostToolUse** | Log tool usage patterns | Async, 0ms |
| **Stop** | Score response, detect drift, flag corrections | Async, 0ms |

All observation hooks are async — zero perceived latency.

## How it works

```
User query → classify.py (async)     → query-type.tmp
                                          ↓
Claude responds → score.py (async)   → scores.jsonl
                                          ↓
                                     drift.py checks thresholds
                                     (query-type-aware)
                                          ↓ (if drift)
                                     drift.json ← correction from
                                                   corrections.json
                                          ↓
Next session → inject.py             → anchor + correction injected
                                       via additionalContext
```

### Context injection

| Layer | When | Content | ~Tokens |
|-------|------|---------|---------|
| **Anchor** | Always | Behavioral anchor (answer first, no filler, no affect) | 50 |
| **Correction** | After drift | Strategy from decision table, matched to drift type + severity + query type | 0-60 |
| **Stats** | Resume (>4h gap) | Rolling 7-day stats | ~30 |

Typical cost: **~50 tokens/session**.

### Query-type-aware thresholds

Default thresholds with query-type overrides (`data/thresholds.json`):

| Query type | Density threshold | Why |
|------------|------------------|-----|
| Global default | 0.60 | Research-validated baseline |
| Code | 0.50 | Variable names, syntax lower natural density |
| Diagnostic | 0.55 | Step-by-step detail is appropriate |

### Correction decision table

`data/corrections.json` maps drift type × severity × query type to correction templates. Examples:

- Filler (low severity): `[Prior response contained filler. Omit.]`
- Density (low, code query): *no correction* — code naturally has lower density
- Compound (high): `[Prior: multiple drift signals. Reset: transparent tool, answer first, no filler.]`

### Drift severity

- **Low**: single dimension, marginal (e.g., density 0.58 vs 0.60)
- **High**: far from threshold (3+ filler phrases), or multiple dimensions
- **Compound**: 2+ drift categories simultaneously

## Design goals

1. **Ready-to-hand** — the assistant is invisible as a social entity
2. **Zero attention tax** — no response element forces a context switch from your task
3. **Self-correcting** — drift detected and corrected without user intervention
4. **Calm by default** — the plugin's own corrections are minimal and non-intrusive
5. **Recursive ergonomics** — the plugin applies its own standards to its own operation

## Standalone scoring

```bash
echo "Great question! I'd be happy to help." | python3 lib/score.py
```

```json
{
  "word_count": 8,
  "answer_position": 0,
  "padding_count": 2,
  "filler_phrases": ["Great question", "happy to help"],
  "info_density": 0.5
}
```

## Architecture

```
lib/
├── score.py        # Deterministic scoring (24 filler patterns, 20 preamble regexes)
├── store.py        # JSONL ledger, rotation, rolling stats
├── inject.py       # Context assembly (anchor + correction + stats)
├── drift.py        # Drift detection, severity, correction strategy selection
├── classify.py     # Deterministic query-type classifier
├── observe.py      # PostToolUse logger (silent observation)
├── thresholds.py   # Query-type-aware threshold management
├── transcript.py   # Transcript parsing utilities
└── compat.py       # Cross-platform file locking (macOS/Linux/Windows)
```

Runtime data: `~/.claude/lcars/`

## Research basis

Cognitive load theory (Sweller, 1988), tool transparency (Winograd & Flores, 1986), calm technology (Weiser & Brown, 1996), organizational ergonomics (Hendrick & Kleiner, 2002), and empirical evaluation across 48 queries with pairwise judging.

## Requirements

- Python 3.10+
- Claude Code with plugin support
- Any OS (macOS, Linux, Windows)

## License

MIT
