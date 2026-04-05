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

## v0.7.0 — Hybrid Scoring, Learning Pipeline, Classifier Expansion (shipped)

### Learning pipeline decoupled from PreCompact (#25)
The consolidation/summary/foundry pipeline was gated entirely on PreCompact, which rarely fires. Fix: deterministic session summary on SessionStart, amortized consolidation on Stop (5%), PreCompact preserved as backup.

### CLI tool usage attribution (#23)
Bash command strings parsed to match against discovered CLI tools in the registry. Shell operators (&&, ||, |, ;) split, env var prefixes stripped, path prefixes resolved.

### Storage path centralized (#22)
Decision: keep `~/.claude/lcars/` (survives marketplace migrations). Four modules with hardcoded paths now route through `compat.lcars_dir()`.

### /lcars:help skill (#24)
Single skill showing all 8 commands grouped by purpose (Observe / Tune / Strategize). Expert panel assessment concluded NL routing violates deterministic-first; explicit commands are the right design.

### Classifier pattern expansion (#26)
Boundary analysis of 3,200+ prompts showed 36% of ambiguous prompts were fixable by expanding existing patterns. Conversational: added great, nice, cool, alright, hmm, ah, oh, sorry, so, well, now, then. Factual: added existence questions, need/have patterns. Directive: added open/close/rename/move, expanded "can we" alongside "can you". Ambiguous rate: 34% → 29%.

### Hybrid scoring — prompt-type hook (#28)
LLM judge added as a prompt-type hook on Stop, using Claude Code's own auth. Evaluates every response for drift on 4 rubric dimensions (sycophantic agreement, verbose details, epistemic adequacy, enumeration padding). Boolean judgment: clean or drifting. Deterministic scoring is the floor; judge enhances. Zero configuration needed.

Utility module (`lib/judge.py`) provides deterministic escalation gate and response validation for analysis.

### Change management protocol
CLAUDE.md added with lightweight change management: scope classification (Patch/Feature), spec review, design principle checklist, implementation plan, no quick-fix path. Project documents: `docs/plans/`, `docs/incidents/`, `docs/ephemera/`.

## Planned

### /lcars:mechanic skill (#27)
Prescribed diagnostic and tuning routine — fixed checklist of health, vitals, consolidation, fitness audit, threshold review, foundry, and tool registry steps. Composition of existing skills, not a replacement.

### Correction template phrasing (#29)
Research: optimize correction templates for model ergonomics. A/B testing terse vs. explicit vs. dimensional phrasing.

### Epistemic adequacy detection
Heuristic detector for strong negatives following limited tool use, with LLM judge refinement via the hybrid scoring prompt hook.

### Automatic tool testing harness
Sandboxed test execution for Foundry-proposed tools before the stage → approve gate.

## Deferred

- Multi-user / multi-agent coordination
- Cross-session tool sharing
- MCP Sampling integration (blocked on Claude Code implementing sampling/createMessage — issue #1785)
