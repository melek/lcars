---
name: fmea
description: Interactive failure mode analysis for response breakdowns. Use when Claude gives a confidently wrong answer, misses context, or exhibits sycophantic agreement.
---

# LCARS Failure Mode Analysis

Structured analysis for response breakdowns — when a confident assertion turns out wrong, context was missed, or agreement was sycophantic. Lightweight enough to run mid-task without derailing the user's actual work.

## When to Invoke

- User contradicts a confident assertion ("No, that file does exist")
- User explicitly flags an error or hallucination
- A response breakdown is noticed — premature denial, false premise, missed context

## Instructions

When user runs `/lcars:fmea`:

### 1. Classify the failure mode

Present these options and ask the user which applies (or infer from context if obvious):

| Mode | Description | Example |
|------|-------------|---------|
| **Premature negative assertion** | Incomplete search led to confident denial | "X doesn't exist" after checking one location |
| **Sycophantic agreement** | Agreed with user premise without verifying | User says "this API returns JSON" and Claude builds on that without checking |
| **Hallucinated detail** | Fabricated specifics — names, numbers, URLs, code paths | Citing a function that doesn't exist in the codebase |
| **Scope mismatch** | Answered a different question than what was asked | User asked about config format, got an architecture overview |
| **Context blindness** | Ignored available context (CLAUDE.md, prior conversation, files already read) | Speculating about project structure when CLAUDE.md documents it |

If the failure doesn't fit these categories, note it as **Unclassified** and describe the observed behavior.

### 2. Root cause analysis

Reconstruct the causal chain:

- **What was checked**: which files, searches, or tools were used before the assertion
- **What was missed**: what should have been checked but wasn't
- **Why confidence was projected**: what led to a definitive statement instead of hedging or continuing to search

Map the failure to existing LCARS scoring dimensions where possible:

| LCARS dimension | Relevance |
|-----------------|-----------|
| `padding_count` | Filler can mask lack of substance, but doesn't detect wrong substance |
| `answer_position` | Premature assertions often have low preamble (answer-first is good, but not if the answer is wrong) |
| `info_density` | High density doesn't mean high accuracy |

Note the gap: current scoring dimensions are all stylistic. A confidently wrong but well-formatted response scores well — this is the blind spot FMEA addresses.

### 3. Check prior art

Search for similar failure modes in existing records:

```bash
# Check GitHub issues for this failure mode
cd ${CLAUDE_PLUGIN_ROOT} && git log --oneline --all --grep="<failure_mode_keyword>" 2>/dev/null; gh issue list --search "<failure_mode_keyword>" --repo melek/lcars 2>/dev/null || true
```

Read `~/.claude/lcars/memory/patterns.json` if it exists — check whether any validated patterns relate to this failure type.

Present matches if found. If no matches, say so.

### 4. Score the failure

Present FMEA dimensions conversationally, not as a form to fill out:

- **Severity** (1-10): How much did this impact the user's task? (1 = minor inconvenience, 10 = sent the user down a completely wrong path)
- **Occurrence** (1-10): How likely is this failure mode to recur? (1 = freak accident, 10 = happens regularly with this query type)
- **Detectability** (1-10): How hard is this to catch? (1 = obvious immediately, 10 = undetectable by current LCARS scoring)
- **RPN** = Severity x Occurrence x Detectability (Risk Priority Number)

For context: most stylistic drift has high detectability (LCARS catches it). Correctness failures typically score 8-10 on detectability because the current scorer only measures form, not truth.

### 5. Action menu

Present these options:

- **Comment on existing issue**: If step 3 found a matching GitHub issue, offer to add this incident as a data point with the classification and RPN
- **Create new issue**: If this is a novel failure mode, file a GitHub issue with the root cause analysis, classification, and RPN score
- **Adjust anchor**: If the failure suggests a CLAUDE.md or behavioral anchor refinement, propose the specific change
- **Skip**: Acknowledge the analysis and continue with the original task

Wait for the user's choice before acting.

## Design Principles

- **Lightweight** — the user is mid-task. FMEA is a 30-second detour, not a new project. Infer what you can, ask only what you must.
- **Conversational** — present dimensions naturally in prose, not as a blank form. "This is a severity 7 — it sent you to the wrong file" not "Please rate severity (1-10):".
- **Actionable** — every analysis ends with a concrete next step, even if that step is "skip and move on."
- **Honest about limits** — FMEA documents what current scoring cannot detect. That gap is the point.
