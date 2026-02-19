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

## Foundry

LCARS includes a self-contained strategy crystallization system inspired by [OpenClaw](https://github.com/openclaw)'s Foundry pattern. Instead of creating external tools, it crystallizes observations into its own correction strategies.

The flow: **observe → validate → crystallize → stage → approve**.

1. Scoring and drift data accumulate over sessions
2. The PreCompact hook consolidates session summaries and identifies recurring patterns
3. Overfit gates prevent premature crystallization: a pattern must appear in **5+ sessions** across **3+ calendar days**
4. The Foundry analyzes validated patterns against correction effectiveness and proposes new or refined strategies
5. Proposals are staged — never auto-applied. Run `/lcars:foundry` to review and approve.

Three proposal types:
- **Gap**: a validated drift pattern has no query-type-specific strategy (e.g., filler drift on emotional queries keeps firing but the generic correction doesn't help)
- **Refinement**: an existing strategy has low fitness (< 50% effective) for a specific query type
- **Suppression**: a strategy fires in > 30% of sessions but rarely improves the targeted dimension

## Skills

| Skill | Purpose |
|---|---|
| `/lcars:dashboard` | Scoring stats, drift history, correction fitness, active patterns |
| `/lcars:calibrate` | Propose threshold adjustments from evidence (human-approved) |
| `/lcars:consolidate` | Manually trigger pattern consolidation |
| `/lcars:foundry` | Review and apply staged strategy proposals |
| `/lcars:deep-eval` | On-demand LLM-as-judge evaluation against structured rubric |

## Architecture

```
lib/
├── score.py        # Deterministic scoring (24 filler patterns, 20 preamble regexes)
├── store.py        # JSONL ledger, rotation, rolling stats
├── inject.py       # Context assembly (anchor + correction + stats)
├── drift.py        # Drift detection, severity, correction strategy selection
├── classify.py     # Deterministic query-type classifier (no LLM calls)
├── fitness.py      # Correction effectiveness tracking
├── consolidate.py  # Session summary extraction + pattern consolidation
├── foundry.py      # Strategy crystallization from validated patterns
├── observe.py      # PostToolUse + SubagentStart logger (silent, async)
├── thresholds.py   # Query-type-aware threshold management
├── transcript.py   # Transcript parsing utilities
└── compat.py       # Cross-platform file locking (macOS/Linux/Windows)

skills/
├── dashboard/      # /lcars:dashboard
├── calibrate/      # /lcars:calibrate
├── consolidate/    # /lcars:consolidate
├── foundry/        # /lcars:foundry
└── deep-eval/      # /lcars:deep-eval (LLM-as-judge)

agents/
└── eval.md         # Autonomous evaluation agent (read-only)

tests/              # 77 unit + integration tests (pytest)

docs/
├── methodology.md              # Design methodology (research basis, evaluation results)
└── cognitive-ergonomics-primer.html  # Interactive primer (standalone, open in browser)
```

Runtime data: `~/.claude/lcars/`

```
~/.claude/lcars/
├── scores.jsonl                    # Score ledger (weekly rotation)
├── drift.json                      # Ephemeral drift flag (consumed on read)
├── thresholds.json                 # Active thresholds
├── query-type.tmp                  # Current query classification
├── pending-correction.json         # Correction awaiting effectiveness evaluation
└── memory/
    ├── session-summaries.jsonl     # Per-session summaries (30-day window)
    ├── patterns.json               # Consolidated recurring patterns
    ├── correction-outcomes.jsonl   # Correction → result pairs for fitness
    └── staged-strategies.json      # Foundry proposals awaiting approval
```

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

## Testing

```bash
python3 -m pytest tests/ -v
```

77 tests covering: scoring accuracy, query classification, drift detection, severity classification, correction strategy selection, fitness tracking, overfit gates, foundry proposals, context assembly, data operations, end-to-end correction loop, and graceful degradation.

## Design rationale

See [DESIGN.md](DESIGN.md) for the recursive ergonomics framework — applying cognitive load theory to the LLM's own context constraints (attention sinks, lost-in-the-middle effects, context rot).

## Documentation

- [docs/methodology.md](docs/methodology.md) — Design methodology, research basis (35 citations), evaluation results across 48 queries
- [docs/cognitive-ergonomics-primer.html](docs/cognitive-ergonomics-primer.html) — Interactive primer on cognitive ergonomics from first principles (open in browser)
- [DESIGN.md](DESIGN.md) — Recursive ergonomics: the Sweller CLT → LLM mapping

## Research basis

Grounded in cognitive load theory (Sweller, 1988), tool transparency (Winograd & Flores, 1986), calm technology (Weiser & Brown, 1996), organizational ergonomics (Hendrick & Kleiner, 2002), sycophancy characterization (Sharma et al., ICLR 2024), verbosity taxonomy (Zhang et al., 2024), sycophancy decomposition (Vennemeyer et al., 2025), and empirical evaluation across 48 queries. Full methodology and bibliography: [docs/methodology.md](docs/methodology.md).

## Requirements

- Python 3.10+
- Claude Code with plugin support
- macOS, Linux, or Windows

## License

MIT
