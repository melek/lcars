# LCARS Roadmap

## v0.5.0 — Reliability, Analysis, and Scoring Precision (shipped)

### Consolidation data starvation fix (#5)
Consolidation now derives sessions from `scores.jsonl` session markers instead of depending on `session-summaries.jsonl` (which was only written at PreCompact). All sessions are captured regardless of how they end. `session-summaries.jsonl` retained as a write-through cache.

### Cross-platform bootstrap reliability (#3)
Hooks now route through `bin/python-shim.sh` (POSIX), which tries `python3` then `python` with version >= 3.10 validation. Silent failure on Windows eliminated. New `/lcars:setup` diagnostic skill validates the full installation chain.

### FMEA skill (#1)
Interactive failure mode analysis for response breakdowns. Classifies failures (premature negative assertion, sycophantic agreement, hallucinated detail, scope mismatch, context blindness), reconstructs causal chains, checks prior art, and presents an action menu. Standard FMEA scoring: Severity × Occurrence × Detectability = RPN.

### Scoring precision (#2, #4)
- Word boundaries (`\b`) added to all 24 filler patterns to prevent false positives from substring matching
- Epistemic Adequacy (`EpAd`, 0-3) added to the deep-eval rubric — scores whether confidence matches evidence gathered
- Design docs for hybrid scoring (regex + LLM judge escalation) and epistemic adequacy detection

## v0.5.1 — Mid-conversation corrections (#9)

### Bug: corrections inject cross-session instead of mid-conversation

The `Stop` hook detects drift and writes `drift.json`, but corrections are only read during `SessionStart` — meaning drift in turn 3 isn't corrected until the next session (potentially hours later). The pop semantics (`read_and_clear_drift_flag`) confirm the original intent was single-shot mid-conversation course correction.

**Fix:** Move correction injection from `SessionStart` to `UserPromptSubmit`, which already supports `additionalContext` and fires on the next user message within the same session. `SessionStart` continues to inject anchor + stats.

This also clarifies the design split: mid-conversation corrections are ephemeral (pop); cross-session corrections responding to repeated drift patterns would be a separate, durable mechanism.

## v0.6.0 — Tool Crystallization (OpenClaw-inspired)

Extend the Foundry from behavioral correction strategies to deterministic tool creation. The current Foundry observes drift patterns and crystallizes correction *templates* (text injected into context). The next step: crystallize reusable *tools* — executable scripts created, tested, and managed by the plugin itself.

### tool-factory integration (#10)

tool-factory is currently a standalone MCP server providing a dynamic tool registry — Claude can create, test, archive, and invoke Python tools at runtime, with new tools immediately available in-session via MCP. It's underutilized because there's no observer feeding it: Claude must self-identify repeated patterns mid-conversation, which structurally doesn't happen without cross-session memory.

Bundling tool-factory into LCARS connects the observer (scoring, drift detection, consolidation) to the actuator (tool creation). Integration approach is open:

- **LCARS as MCP client** — hooks call tool-factory's `create_tool` endpoint via bridge script
- **Absorb tool-factory** — registry becomes a LCARS module, served from the plugin's own MCP surface
- **Shared data layer** — LCARS writes tool proposals to disk, tool-factory picks them up

### Concept

The same observe → validate → crystallize → stage → approve flow, but the output is an MCP tool rather than a correction template. When the plugin detects a recurring pattern that would benefit from a deterministic tool (e.g., a formatting task the model keeps doing inconsistently), it proposes a tool, stages it for review, and — on approval — registers it.

### Open questions

- **Scope boundary:** When does a pattern warrant a tool vs. a correction template? A correction fixes *how the model responds*. A tool automates *what the model does*. The distinction may be: corrections for behavioral drift, tools for repeated deterministic operations.
- **Tool lifecycle:** Tools created by the Foundry should be subject to the same fitness tracking as corrections. If a tool isn't used or isn't effective, propose archival.
- **Safety:** Auto-generated executable code needs review. The stage → approve gate is mandatory. Consider sandboxed test execution before staging (see automatic tool testing harness below).

### Hybrid scoring implementation

Implement the architecture from `docs/hybrid-scoring-design.md`:
- Phase 1: Contextual pattern improvements (beyond word boundaries)
- Phase 2: Escalation logic in `score.py` (regex → clean/drift/escalate)
- Phase 3: LLM judge integration (Haiku, deep-eval rubric subset)
- Phase 4: Feedback loop (LLM overrides → pattern refinement)

### Epistemic adequacy detection

Implement the approach from `docs/epistemic-adequacy-design.md`:
- Heuristic detector for strong negatives following limited tool use
- Data collection: tool-use patterns alongside scores
- FMEA incident integration as labeled examples

### Automatic tool testing harness

Sandboxed test execution for Foundry-proposed tools before they reach the stage → approve gate. Required for safety when tool crystallization is automated rather than user-initiated.

## Deferred

- Multi-user / multi-agent coordination
- Cross-session tool sharing
