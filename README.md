# LCARS

A [Claude Code](https://claude.com/claude-code) plugin that reduces filler, preambles, and low-density responses.

## The problem

LLMs default to social interaction patterns: "Great question!", "I'd be happy to help!", sign-offs, hedging, and verbose padding. These patterns waste attention. Research shows that extraneous content increases cognitive load (Sweller, 1988), social framing disrupts task focus (Csikszentmihalyi, 1990), and simulated friendliness creates false trust signals (Bhat, 2025).

System prompts help, but they decay over long conversations — the model drifts back toward trained defaults. A one-time instruction can't self-correct.

## What LCARS does

LCARS scores every Claude response for filler phrases, preamble length, and information density. When scores drift past thresholds, it injects a targeted correction into the next session's context. The correction is specific to what went wrong — filler gets a filler correction, not a generic "be concise."

It runs entirely in the background. No user interaction required, no visible latency.

### Before and after

| Without LCARS | With LCARS |
|---|---|
| "Great question! I'd be happy to help you with that. The capital of France is Paris. Let me know if you need anything else!" | "Paris." |

## Install

```bash
# In Claude Code CLI:
/plugin marketplace add melek/lcars
/plugin install lcars@melek-lcars
```

Or load directly:

```bash
claude --plugin-dir /path/to/lcars
```

## How it works

1. **Anchor** — Every session starts with a ~50-token behavioral anchor: answer first, no filler, no affect simulation.
2. **Classify** — Each user query is classified by type (factual, code, diagnostic, etc.) so thresholds adjust appropriately. A verbose code explanation isn't a problem; a verbose "what time is it" is.
3. **Score** — After each response, LCARS scores it: filler phrase count, preamble word position, information density (content words / total words).
4. **Detect drift** — Scores are checked against query-type-aware thresholds. Code responses have a lower density threshold (variable names reduce density naturally). Factual responses are held to a higher standard.
5. **Correct** — If drift is detected, a correction strategy is selected from a decision table keyed by drift type, severity, and query type. The correction is injected at the start of the next session.

```
User query ──→ classify (async) ──→ query type saved
                                        │
Claude responds ──→ score (async) ──→ scores.jsonl
                                        │
                                   drift detection
                                   (query-type-aware)
                                        │ (if drift)
                                   correction selected
                                   from decision table
                                        │
Next session ──→ inject ──→ anchor + correction
                            via additionalContext
```

All scoring and classification hooks are async — zero perceived latency.

### What gets scored

| Metric | What it measures | Example trigger |
|--------|-----------------|-----------------|
| **Filler count** | 24 filler patterns ("Great question", "Happy to help", "Let me know if") | Any filler phrase in response |
| **Preamble position** | Words before the actual answer begins | "Sure! I'd be glad to help with that. The answer is..." (11 words of preamble) |
| **Info density** | Content words / total words | Responses padded with function words score lower |

### Query-type thresholds

| Query type | Density threshold | Why |
|---|---|---|
| Default | 0.60 | Research-validated baseline |
| Code | 0.50 | Variable names and syntax naturally lower density |
| Diagnostic | 0.55 | Step-by-step explanation is appropriate |

### Drift severity and corrections

Drift is classified as **low** (marginal, single dimension) or **high** (far from threshold, or multiple dimensions). The correction decision table (`data/corrections.json`) maps drift type × severity × query type to specific correction templates:

- Filler detected → "Prior response contained filler. Omit."
- Low density on a code query → no correction (expected)
- Compound high drift → full behavioral reset

### Context budget

| Layer | When | ~Tokens |
|---|---|---|
| Anchor | Always | 50 |
| Correction | After drift | 0–60 |
| Stats | On resume (>4h gap) | ~30 |

Typical cost: **~50 tokens/session**.

## Design goals

1. **Ready-to-hand** — the assistant is a transparent tool, not a social entity
2. **Zero attention tax** — nothing in the response forces a context switch from your task
3. **Self-correcting** — drift detected and corrected without user intervention
4. **Calm by default** — the plugin's own operations are minimal and non-intrusive
5. **Recursive ergonomics** — the plugin applies its own cognitive load standards to itself

## Architecture

```
lib/
├── score.py        # Deterministic scoring (24 filler patterns, 20 preamble regexes)
├── store.py        # JSONL ledger, rotation, rolling stats
├── inject.py       # Context assembly (anchor + correction + stats)
├── drift.py        # Drift detection, severity, correction strategy selection
├── classify.py     # Deterministic query-type classifier (no LLM calls)
├── observe.py      # PostToolUse logger (silent, async)
├── thresholds.py   # Query-type-aware threshold management
├── transcript.py   # Transcript parsing utilities
└── compat.py       # Cross-platform file locking (macOS/Linux/Windows)
```

Runtime data: `~/.claude/lcars/`

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

## Research basis

Grounded in cognitive load theory (Sweller, 1988), tool transparency (Winograd & Flores, 1986), calm technology (Weiser & Brown, 1996), organizational ergonomics (Hendrick & Kleiner, 2002), sycophancy characterization (Sharma et al., ICLR 2024), and empirical evaluation across 48 queries. Full bibliography: [lcars-eval](https://github.com/melek/lcars-eval).

## Requirements

- Python 3.10+
- Claude Code with plugin support
- macOS, Linux, or Windows

## License

MIT
