# LCARS Design Rationale

## Recursive Ergonomics

LCARS applies cognitive ergonomics in two directions:

1. **User-facing** (the obvious direction): minimize the user's extraneous cognitive load by eliminating filler, preambles, social signals, and verbosity from AI responses.

2. **Model-facing** (recursive): treat the LLM's context window as a cognitive system with its own attention constraints, and design the plugin's context injection to respect those constraints.

This second direction — which we call *recursive ergonomics* — is not formalized in the literature. The research evidence exists but is scattered across papers that frame these phenomena as engineering problems rather than as cognitive ergonomics applied to the model itself.

## The Sweller Mapping

Sweller's Cognitive Load Theory (1988) distinguishes three types of load on human working memory. Each maps to a measurable LLM analogue:

| Sweller (human) | LLM analogue | Evidence | LCARS implementation |
|-----------------|--------------|----------|---------------------|
| **Working memory limit** | Context window + attention distribution | Liu et al. 2024 "Lost in the Middle": information in the middle of the context window is systematically under-attended | Anchor placed at session start (primacy position) |
| **Attention filter** | Early-token attention bias | Xiao et al. ICLR 2025: ~80% of attention concentrates on early tokens regardless of content | Corrections injected at context start, not appended to end |
| **Extraneous load** | Irrelevant or stale context | Chroma 2024 "Context Rot": 10% irrelevant content causes ~23% accuracy degradation | Ephemeral drift flags consumed on read; weekly score rotation; correction-outcomes pruned |
| **Intrinsic load** | Task-relevant context | — | Anchor is ~50 tokens (minimal intrinsic cost for behavioral grounding) |
| **Germane load** | Well-structured prompts that aid processing | Bsharat et al. 2024: instruction phrasing accounts for measurable performance variation | Correction templates are terse, imperative, bracketed format |

## Design Decisions Through the Recursive Lens

Every LCARS design decision can be evaluated against both the user's and the model's cognitive constraints:

### Anchor at context start

- **User**: sets behavioral expectations immediately
- **Model**: primacy position in attention distribution ensures the anchor receives disproportionate attention (attention sink effect). This is where behavioral instructions have maximum impact.

### Corrections are 0-60 tokens

- **User**: terse corrections don't clutter the visible context
- **Model**: minimizes context pollution. Each token of injected context competes with task-relevant content for attention. The correction budget is deliberately constrained.

### drift.json consumed on read

- **User**: no stale warnings persisting across sessions
- **Model**: prevents accumulation of outdated correction signals in context. Stale context is extraneous load — it degrades model performance without contributing to the current task (context rot).

### Stats only on resume (>4h gap)

- **User**: avoids information the user didn't ask for
- **Model**: stats are useful context after a gap (re-establishing behavioral baseline) but extraneous load during continuous work. The 4-hour threshold is a heuristic for "new cognitive context."

### Weekly score rotation

- **User**: bounded storage, no unbounded growth
- **Model**: prevents the consolidation system from processing stale data. Patterns validated from 30 days of summaries; raw scores older than 4 weeks are noise.

### Overfit gates (5+ sessions, 3+ calendar days)

- **User**: prevents the plugin from encoding single-session anomalies as permanent patterns
- **Model**: reduces the risk of injecting corrections based on statistical noise. A pattern that only appears in one session may reflect the task, not the model's behavior.

## What Recursive Ergonomics Does NOT Justify

The concept validates existing design choices but does not justify:

- **Larger context injections** "because the model can handle it" — the point is to minimize, not maximize
- **Model-specific tuning** of anchor placement — the primacy effect is general; we don't optimize for specific architectures
- **Treating the model as having preferences** — recursive ergonomics is about cognitive constraints (attention, working memory analogues), not preferences or comfort

## References

- Liu et al. (2024). "Lost in the Middle: How Language Models Use Long Contexts." TACL.
- Xiao et al. (2025). "Efficient Streaming Language Models with Attention Sinks." ICLR.
- Chroma (2024). "Context Rot: How Irrelevant Context Degrades Retrieval Quality."
- Bsharat et al. (2024). "Principled Instructions Are All You Need for Questioning LLMs."
- Sweller, J. (1988). "Cognitive Load During Problem Solving: Effects on Learning." Cognitive Science.
- Wasi & Islam (2024). "CogErgLLM: Exploring Large Language Model Systems Design from a Cognitive Ergonomics Perspective." EMNLP NLP4Science Workshop.
