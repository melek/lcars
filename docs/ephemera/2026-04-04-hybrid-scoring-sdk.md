# Hybrid Scoring: Claude SDK for Sub-Agent Hooks

Date: 2026-04-04

The hybrid scoring escalation gate (Phase 2-3 in `docs/hybrid-scoring-design.md`) can be implemented using the Claude SDK to spawn sub-agents from hooks. This enables LLM-as-judge scoring for borderline cases without blocking the deterministic pipeline.

Requirements:
- **User setup:** SDK requires API key configuration. Must be handled explicitly with the user during plugin setup, not assumed.
- **Graceful degradation:** If the user declines SDK setup or the SDK call fails, the system falls back to deterministic-only scoring. The LLM judge is an enhancement, not a dependency.
- **Budget awareness:** Sub-agent calls have token cost. Amortize or gate to avoid surprising the user with API charges.

This is the ceiling-breaking mechanism that deterministic classification cannot provide. The classifier stays regex; the scorer escalates when ambiguous.
