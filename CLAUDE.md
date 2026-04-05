# CLAUDE.md — LCARS

Self-correcting cognitive ergonomics for Claude Code. Deterministic scoring pipeline that detects and corrects response drift — filler, preambles, low information density — across conversations.

## Commands

```bash
# Run tests (pytest)
python3 -m pytest tests/ -v

# Run a single test file
python3 -m pytest tests/test_score.py -v

# Standalone scoring (pipe text in)
echo "some text" | python3 lib/score.py

# Run consolidation manually
python3 lib/consolidate.py --consolidate
```

## Architecture

Seven hooks form the runtime pipeline. Deterministic scoring is the floor; an optional prompt-type hook adds LLM judge evaluation via Claude Code's auth.

| Hook | Trigger | Module/Type | Sync | Purpose |
|------|---------|-------------|------|---------|
| SessionStart | New session | `inject.py` (command) | Yes | Inject anchor + correction + stats; summarize previous session |
| UserPromptSubmit | User sends message | `classify.py` (command) | Yes | Classify query type (9 categories) |
| PostToolUse | Tool executed | `observe.py` (command) | Async | Log tool use; attribute CLI tools to registry |
| PreCompact | Context compaction | `consolidate.py` (command) | Async | Session summaries + pattern consolidation |
| Stop | Response complete | `score.py` (command) | Async | Score response, detect drift, store |
| Stop | Response complete | prompt hook | Async | LLM judge: boolean drift evaluation on 4 rubric dimensions |
| SubagentStart | Subagent spawned | `observe.py` (command) | Async | Log subagent start |

### Key Modules

| Module | Purpose |
|--------|---------|
| `lib/score.py` | Deterministic scoring: 24 filler patterns, preamble position, info density |
| `lib/classify.py` | Query-type classifier: code, diagnostic, claim, emotional, meta, factual, directive, conversational, ambiguous |
| `lib/drift.py` | Drift detection with query-type-aware thresholds; severity classification |
| `lib/inject.py` | Context assembly: anchor + correction + stats + discovered tools |
| `lib/fitness.py` | Correction effectiveness tracking |
| `lib/thresholds.py` | Per-query-type threshold management |
| `lib/store.py` | JSONL ledger with rotation and rolling stats |
| `lib/consolidate.py` | Session summary extraction + pattern consolidation |
| `lib/foundry.py` | Strategy crystallization from validated patterns |
| `lib/registry.py` | Tool registry: discovered + crystallized + user tools |
| `lib/discover.py` | Environment CLI tool discovery vs curated allowlist |
| `lib/tool_fitness.py` | Tool promotion/demotion lifecycle |
| `lib/observe.py` | PostToolUse + SubagentStart logger; CLI tool attribution |
| `lib/judge.py` | Hybrid scoring utilities: escalation gate, response validation |
| `lib/compat.py` | Cross-platform file locking, `lcars_dir()` (single source for storage path) |

### Data Files

| File | Purpose |
|------|---------|
| `data/anchor.txt` | ~50-token behavioral anchor injected at session start |
| `data/corrections.json` | v19; 14 correction strategies (drift x severity x query type) |
| `data/thresholds.json` | v2; global + per-query-type density thresholds |
| `data/discoverable.json` | Curated allowlist of discoverable CLI tools |

### Runtime Data

All runtime state lives in `~/.claude/lcars/`:
- `scores.jsonl` — immutable append-only scoring ledger
- `memory/` — session summaries, validated patterns, tool registry
- `foundry/` — staged strategy proposals

## Design Principles

LCARS is built on **recursive ergonomics**: cognitive load theory applied in two directions.

1. **User-facing**: minimize extraneous cognitive load (filler, preambles, social signals)
2. **Model-facing**: treat the context window as a cognitive system — minimize injected tokens, place anchors at primacy position, consume ephemeral signals on read

### Core Commitments

- **Deterministic-first.** All scoring is regex-based. No LLM calls in the observation/scoring path. Inference is a last resort.
- **Auditability.** Every score, correction, and pattern decision is recorded in the JSONL ledger. Work should be traceable from its record alone.
- **Minimal context budget.** ~50 tokens/session typical. Every injected token competes with task-relevant content for attention.
- **Overfit prevention.** Patterns require 5+ sessions spanning 3+ calendar days before crystallization. Single-session anomalies are noise.
- **Tool transparency.** The plugin should be invisible when working well. No social presence, no engagement demands.

## Project Documents

| Path | Purpose |
|------|---------|
| `ROADMAP.md` | Version milestones — what shipped, what's next |
| `DESIGN.md` | Recursive ergonomics rationale |
| `docs/methodology.md` | Research-grounded design methodology (35 citations) |
| `docs/plans/` | Implementation plans for in-progress Feature-tier work |
| `docs/incidents/` | Bug and anomaly postmortems: what happened, how it was caught, what changed |
| `docs/ephemera/` | Design observations worth preserving but not yet actionable |

## Change Management

Every change starts with scope classification. No code is written until the protocol for that scope is satisfied.

### Scope Classification (always first)

| Tier | Scope | Examples | Protocol |
|------|-------|----------|----------|
| **Patch** | No behavioral change | Test fixes, typos, docs, threshold tuning | Classify + verify against design + implement |
| **Feature** | New/modified observable behavior | New hook, new scoring signal, new correction strategy, pipeline routing | Full protocol (below) |

If uncertain, classify upward.

### Full Protocol (Feature-tier changes)

**1. Spec Review** — Read before writing:
- Identify governing design documents (`DESIGN.md`, `docs/methodology.md`, relevant module)
- Read every file that will be modified
- State the change in terms of current behavior vs. required behavior
- Identify **semantic contracts** — what must be *behaviorally* true beyond structural correctness (e.g., "scoring must remain deterministic," "corrections must not exceed context budget")

**2. Review** — Assess the spec review:
- Does the change preserve deterministic-first scoring?
- Does it respect the context budget?
- Is auditability maintained (ledger, provenance)?
- Does it introduce inference where a deterministic approach exists?
- Verdict: PASS, CONCERN (with conditions), or BLOCK (with reason). Any BLOCK returns to spec review.

**3. Implementation Plan** — Numbered steps before code:
- Files to create/modify with specific changes
- Test plan: one test minimum per semantic contract
- Design principle checklist: which commitments apply, one sentence each
- Rollback boundary: safe state if interrupted

User approves this plan before implementation begins.

**4. Implementation** — Execute plan in order:
- Run tests after each logical unit
- If implementation reveals a gap in the spec review: **stop and return to step 1**
- Commit messages reference semantic contracts, not mechanical changes

### No Quick-Fix Path

Bug found post-implementation? Classify via scope classification. If the fix reveals a missed semantic contract, that's Feature-tier — return to spec review. The missed contract is evidence the original review was incomplete.
