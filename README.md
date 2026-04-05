# LCARS

A [Claude Code](https://claude.com/claude-code) plugin that detects and corrects filler, preambles, and low-density responses automatically across conversations.

| Without LCARS | With LCARS |
|---|---|
| "Great question! I'd be happy to help you with that. The capital of France is Paris. Let me know if you need anything else!" | "Paris." |

## Why

LLMs default to social interaction patterns: "Great question!", "I'd be happy to help!", sign-offs, hedging, and verbose padding. These patterns are distracting and even manipulative. System prompts help, but they decay over long conversations and the model drifts back toward trained defaults.

LCARS scores every response and injects targeted corrections when drift is detected. It runs in the background with zero perceived latency.

## Install

```bash
claude plugins marketplace add melek/lcars
claude plugins install lcars@melek-lcars
```

Verify: `/lcars:setup`

## How it works

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
Next user message ──→ correction injected via additionalContext
```

1. **Anchor** — Every session starts with a ~50-token behavioral anchor: answer first, no filler, no affect simulation.
2. **Classify** — Each user query is classified by type (factual, code, diagnostic, directive, conversational, etc.) so thresholds adjust appropriately.
3. **Score** — After each response: filler phrase count, preamble word position, information density.
4. **Detect drift** — Scores are checked against query-type-aware thresholds. Code responses have a lower density bar; factual responses are held to a higher standard.
5. **Correct** — If drift is detected, a correction is injected on the user's next message within the same session.

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
| Directive | 0.50 | Task commands vary in density |
| Conversational | 0.40 | Follow-ups and acknowledgments are inherently terse |

### Corrections

Drift is classified as **low** or **high** severity. The decision table (`data/corrections.json`) maps drift type × severity × query type to correction templates:

- Filler detected → "Prior response contained filler. Omit."
- Low density on a code query → no correction (expected)
- Low density on an ambiguous query → no correction (too heterogeneous to correct reliably)
- Compound high drift → full behavioral reset

### Context budget

| Layer | When | ~Tokens |
|---|---|---|
| Anchor | Always | 50 |
| Correction | After drift | 0–60 |
| Stats | On resume (>4h gap) | ~30 |

Typical cost: **~50 tokens/session**.

## Foundry

A self-contained strategy crystallization system. Instead of requiring manual tuning, LCARS observes its own correction effectiveness and proposes improvements.

**observe → validate → crystallize → stage → approve**

1. Scoring and drift data accumulate over sessions
2. The PreCompact hook consolidates summaries and identifies recurring patterns
3. Overfit gates prevent premature crystallization: **5+ sessions** across **3+ calendar days**
4. The Foundry proposes new or refined strategies based on correction fitness
5. Proposals are staged — never auto-applied. Review with `/lcars:foundry`

## Tool Registry

LCARS discovers CLI tools in your environment (jq, rg, gh, etc.) and tracks their usage. Discovered tools can be promoted into session context so the model knows what's available. The registry initializes automatically on first session.

## Skills

| Skill | Purpose |
|---|---|
| `/lcars:dashboard` | Scoring stats, drift history, correction fitness, active patterns |
| `/lcars:calibrate` | Propose threshold adjustments from evidence (human-approved) |
| `/lcars:foundry` | Review and apply staged strategy proposals |
| `/lcars:discover` | Scan environment for CLI tools, show registry status |
| `/lcars:deep-eval` | On-demand LLM-as-judge evaluation against structured rubric |
| `/lcars:fmea` | Interactive failure mode analysis for response breakdowns |
| `/lcars:consolidate` | Manually trigger pattern consolidation |
| `/lcars:setup` | Validate installation and diagnose issues |

## Architecture

```
lib/
├── score.py          # Deterministic scoring (24 filler patterns, 20 preamble regexes)
├── classify.py       # Query-type classifier (9 categories, no LLM calls)
├── drift.py          # Drift detection, severity, correction strategy selection
├── inject.py         # Context assembly (anchor + correction + stats + env tools)
├── fitness.py        # Correction effectiveness tracking
├── thresholds.py     # Query-type-aware threshold management
├── store.py          # JSONL ledger, rotation, rolling stats
├── consolidate.py    # Session summary extraction + pattern consolidation
├── foundry.py        # Strategy crystallization from validated patterns
├── registry.py       # Unified tool registry (discovered + crystallized + user tools)
├── discover.py       # Environment tool discovery against curated allowlist
├── tool_fitness.py   # Tool promotion/demotion lifecycle
├── observe.py        # PostToolUse + SubagentStart logger (silent, async)
├── staging.py        # Foundry proposal staging for user approval
├── transcript.py     # Transcript parsing utilities
├── compat.py         # Cross-platform file locking (macOS/Linux/Windows)
└── setup.py          # Installation diagnostics

tool_factory/
└── server.py         # MCP server: dynamic tool creation/execution

bin/
└── python-shim.sh    # Cross-platform Python resolver (POSIX)

skills/               # 9 interactive skills (see table above)
agents/
└── eval.md           # Autonomous evaluation agent (read-only)
tests/                # 241 tests (pytest)
```

Runtime data lives at `~/.claude/lcars/` — scores, drift events, correction outcomes, session summaries, patterns, thresholds, and tool registry.

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

241 tests covering scoring accuracy, query classification, drift detection, correction strategy selection, fitness tracking, pattern consolidation, foundry proposals, tool registry, environment discovery, context assembly, and end-to-end correction loops.

## Design

- [DESIGN.md](DESIGN.md) — Recursive ergonomics: applying cognitive load theory to both the user's attention and the model's context window
- [docs/methodology.md](docs/methodology.md) — Design methodology, 35 research citations, evaluation results across 48 queries
- [docs/cognitive-ergonomics-primer.html](docs/cognitive-ergonomics-primer.html) — Interactive primer (open in browser)
- [docs/hybrid-scoring-design.md](docs/hybrid-scoring-design.md) — Design for hybrid regex + LLM-as-judge scoring (shipped in v0.7.0 via prompt-type hook)
- [docs/epistemic-adequacy-design.md](docs/epistemic-adequacy-design.md) — Design for epistemic adequacy detection (planned)

## Research basis

Grounded in cognitive load theory (Sweller, 1988), tool transparency (Winograd & Flores, 1986), calm technology (Weiser & Brown, 1996), sycophancy characterization (Sharma et al., ICLR 2024), verbosity taxonomy (Zhang et al., 2024), sycophancy decomposition (Vennemeyer et al., 2025), and empirical evaluation across 48 queries. Full bibliography in [docs/methodology.md](docs/methodology.md).

## Requirements

- Python 3.10+
- Claude Code with plugin support
- macOS, Linux, or Windows

## License

MIT
