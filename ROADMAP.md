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

## v0.5.1 — Mid-conversation corrections (#9) (shipped)

### Bug: corrections inject cross-session instead of mid-conversation
Correction injection moved from `SessionStart` (inject.py) to `UserPromptSubmit` (classify.py). Corrections now fire on the next user message within the same session. UserPromptSubmit hook is synchronous to support `additionalContext` output. SessionStart continues to inject anchor + stats.

### Investigation: answer_position drift (#12)
Dashboard data showed answer_position as dominant drift (9/10 recent events). Investigation confirmed answer_position shares the preamble detection path — existing preamble corrections cover it (100% effective). Detecting non-pattern delayed answers is a v0.6.0 hybrid scoring concern.

### Closed as non-issues
- #11: Per-record density appeared missing but field name is `info_density` (working correctly)
- #13: "Unknown" query types were records from early install (Feb 17-19) missing the field entirely — no current classifier issue

## v0.6.0 — Tool Crystallization (OpenClaw-inspired) (shipped)

Extend the Foundry from behavioral correction strategies to deterministic tool creation. Foundry observes drift patterns and crystallizes correction *templates* (text injected into context). v0.6.0 adds tool crystallization: reusable *tools* — executable scripts created, tested, and managed by the plugin itself.

### tool-factory absorbed (#10, #17)

The standalone tool-factory MCP server has been absorbed into the LCARS repo at `tool_factory/server.py`. Storage is unified: tool metadata in the LCARS registry (`tool-registry.json`), scripts in `~/.claude/lcars/tools/`.

**What shipped:**
- `tool_factory/server.py` — MCP server with 6 meta-tools (create, list, get, delete, archive, restore) + dynamic tool execution
- `lib/staging.py` — simplified from the old `bridge.py`; stages Foundry proposals for user approval
- Formal verification of tool lifecycle invariants via Proven/Dafny (7 properties)
- 20 new tests covering CRUD, archive/restore cycle, execution, and registry integration

**Design decisions:**
- **Scope boundary:** Corrections fix *how the model responds*. Tools automate *what the model does*. Corrections for behavioral drift, tools for repeated deterministic operations.
- **Tool lifecycle:** Tools are subject to the same fitness tracking as corrections (candidate → standard → promoted). Unused tools get archived.
- **Safety:** Stage → approve gate is mandatory (NoAutoDeployment invariant). Foundry proposes tools, user approves via MCP call.

## v0.6.4 — Classifier Discrimination & Correction Fitness (shipped)

Dashboard review at 31 days (1,662 responses, 288 sessions) revealed three issues:

### Classifier improvement
Ambiguous query type dominated at 55% of classifications, inflating a heterogeneous catch-all. Added two new categories (`directive`, `conversational`) and expanded `factual` and `diagnostic` patterns. Ambiguous rate drops to ~13% on representative prompts. Dict order adjusted so `directive` breaks ties against `factual` for "can you X" patterns.

### Correction fitness recovery
Correction fitness declined from 90% → 76% week-over-week, concentrated in `ambiguous` + low-severity density corrections (65.6% effective). Root cause: the generic density correction was too vague for the heterogeneous ambiguous bucket. Fix: suppress low-severity density corrections for `ambiguous`, `conversational`, and `directive` query types. High-severity density corrections still fire for all query types.

### Tool registry initialization (#15, #18)
`tool-registry.json` was never created because `discover.scan()` only fired at ~5% probability during PreCompact. Added one-time initialization: SessionStart now calls `discover.scan()` when the registry file doesn't exist. Subsequent sessions skip the scan.

### Threshold overrides
Added query-type-specific density thresholds: `conversational` (0.40), `directive` (0.50). These join existing overrides for `code` (0.50) and `diagnostic` (0.55). Global density threshold (0.60) unchanged.

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
