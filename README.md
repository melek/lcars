# LCARS

Self-correcting cognitive ergonomics plugin for [Claude Code](https://claude.com/claude-code).

LCARS observes every Claude response, scores it against cognitive load metrics, and injects targeted corrections when behavior drifts — all at zero perceived latency.

## What it does

**SessionStart hook** injects a 42-word behavioral anchor into every session:
- Answer first, no preambles
- No filler phrases ("Great question", "Happy to help", "Let me know if")
- No affect simulation, narration, or sign-offs
- Minimum sufficient response length

**Stop hook** (async, zero-latency) scores each response in the background:
- Filler phrase detection (24 patterns across 4 categories)
- Preamble/answer position measurement
- Information density (content words / total words)

When drift is detected (filler appears, density drops, preambles creep in), a correction flag is written and picked up by the next session's start hook.

## Install

```bash
claude --plugin-dir /path/to/lcars
```

## How it works

```
SessionStart hook           Stop hook (async)            Next session
───────────────            ──────────────────           ────────────
Inject behavioral          Score response (BG)          If drift detected:
anchor + any drift         → ~/.claude/lcars/           inject correction
corrections                  scores.jsonl               via additionalContext
                           → drift detection
```

### Three-tier context injection

| Tier | When | Content | ~Tokens |
|------|------|---------|---------|
| 1 | Always | Behavioral anchor | 50 |
| 2 | After drift | Targeted correction | 0-60 |
| 3 | Resume (>4h gap) | Rolling 7-day stats | ~30 |

Typical cost: **~50 tokens/session**.

### Drift thresholds

- Any filler phrase detected
- Any preamble words before the answer
- Information density below 0.60

## Design principles

1. **Ready-to-hand** — the assistant is invisible as a social entity; you notice the answer, not the assistant
2. **Zero attention tax** — no response element forces a context switch from your task
3. **Self-correcting** — drift is detected and corrected without user intervention
4. **Calm by default** — the plugin's own corrections and feedback are minimal and non-intrusive
5. **Recursive ergonomics** — the plugin applies its own standards to its own operation

## Standalone scoring

Score any text against LCARS metrics:

```bash
echo "Great question! I'd be happy to help with that." | python3 lib/scorer.py
```

```json
{
  "word_count": 10,
  "answer_position": 0,
  "padding_count": 2,
  "filler_phrases": ["Great question", "happy to help"],
  "info_density": 0.5
}
```

## Research basis

Built on cognitive load theory (Sweller, 1988), tool transparency (Winograd & Flores, 1986), calm technology (Weiser & Brown, 1996), and empirical evaluation across 48 queries comparing prompted vs. baseline Claude responses.

## Requirements

- Python 3.10+
- Claude Code with plugin support

## License

MIT
