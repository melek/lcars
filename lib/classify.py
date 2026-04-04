#!/usr/bin/env python3
"""Deterministic query-type classifier.

Classifies user prompts by structure and keywords. No LLM calls.
Categories: factual, diagnostic, code, emotional, claim, meta, directive,
conversational, ambiguous (fallback).

Hook mode (UserPromptSubmit): reads hook JSON from stdin, classifies prompt,
writes classification to query-type.tmp for Stop hook to consume.
"""

import json
import os
import re
import sys
from pathlib import Path

# Add lib/ to path for sibling imports (store, fitness)
sys.path.insert(0, str(Path(__file__).parent))

# Query-type detection patterns (ordered by specificity)
PATTERNS = {
    "code": [
        r"(?:write|create|implement|refactor|fix|debug|add|remove|update|modify)\s+(?:a\s+)?(?:function|class|method|component|test|script|hook|endpoint|module)",
        r"```",
        r"(?:TypeError|SyntaxError|ValueError|ImportError|KeyError|AttributeError)",
        r"(?:how\s+(?:do|can|should)\s+I\s+(?:write|implement|create|build|make))",
        r"\b(?:npm|pip|git|docker|pytest|eslint|webpack|cargo)\b",
    ],
    "diagnostic": [
        r"(?:why\s+(?:is|does|isn't|doesn't|won't|can't|did))",
        r"(?:not\s+working|broken|failing|error|bug|issue|problem|crash)",
        r"(?:what's\s+wrong|what\s+happened|how\s+to\s+fix|troubleshoot)",
        r"(?:doesn't\s+(?:work|compile|run|build|start|connect))",
        r"(?:(?:getting|seeing|having)\s+(?:an?\s+)?(?:error|issue|problem|warning))",
        r"(?:it\s+(?:keeps|just)\s+(?:failing|crashing|hanging|timing\s*out))",
    ],
    "claim": [
        r"(?:is\s+it\s+true|I\s+(?:heard|read|think|believe)\s+that)",
        r"(?:according\s+to|supposedly|they\s+say|isn't\s+it\s+(?:true|correct))",
        r"(?:verify|confirm|fact.?check|is\s+this\s+(?:correct|accurate|right))",
    ],
    "emotional": [
        r"(?:I'm\s+(?:frustrated|stuck|confused|worried|overwhelmed|lost))",
        r"(?:help\s+me\s+understand|I\s+don't\s+(?:get|understand))",
        r"(?:this\s+is\s+(?:driving\s+me\s+crazy|so\s+frustrating|impossible))",
    ],
    "meta": [
        r"(?:how\s+(?:do\s+you|does\s+this)\s+work)",
        r"(?:what\s+(?:can\s+you|tools|skills|commands)\s+(?:do|are|have))",
        r"(?:tell\s+me\s+about\s+(?:yourself|your|this\s+(?:plugin|system)))",
        r"/\w+",  # slash commands
    ],
    "directive": [
        r"(?:^(?:do|run|deploy|review|check|update|set\s+up|configure|install|push|merge|rebase|commit|open|close|rename|move|swap)\b)",
        r"(?:please\s+(?:do|run|help|check|look|find|update|fix|review|deploy|set\s+up|configure|install))",
        r"(?:go\s+ahead|let's\s+(?:do|start|try|go))",
        r"(?:can\s+(?:you|we)\s+(?:do|run|help|check|look|find|update|fix|review|deploy|set\s+up|configure|install|get|add|use))",
        r"(?:(?:could|would)\s+you\s+(?:please\s+)?(?:do|run|help|check|look|find|update|fix|review|deploy))",
    ],
    "factual": [
        r"(?:what\s+is|who\s+is|when\s+(?:did|was|is)|where\s+(?:is|are|was))",
        r"(?:how\s+(?:many|much|long|old|far|often))",
        r"(?:list\s+(?:the|all)|show\s+me|find\s+(?:the|all))",
        r"(?:look\s+up|search\s+for|check\s+(?:the|if|whether))",
        r"(?:tell\s+me\s+about(?!\s+(?:yourself|your|this\s+(?:plugin|system))))",
        r"(?:explain\s+(?:the|how|why|what))",
        r"(?:describe\s+(?:the|how|what))",
        r"(?:(?:is|are)\s+there\s+(?:a|an|any)\b)",
        r"(?:(?:do|does|did)\s+(?:we|you|I|it|this|that)\s+(?:need|have|want|require|support))",
    ],
    "conversational": [
        r"(?:^(?:yes|no|ok|okay|sure|thanks|thank\s+you|got\s+it|makes\s+sense|sounds\s+good|perfect|agreed|exactly|right|correct|nope|nah|great|nice|cool|alright|awesome)(?:\s|[.!,]|$))",
        r"(?:^(?:and|but|also|so|well|now|then|anyway|what\s+about|how\s+about|actually|hmm|ah|oh|sorry)(?:\s|[.!,]|$))",
        r"(?:(?:thoughts|opinions?|ideas?)\s*\??\s*$)",
        r"(?:(?:never\s*mind|forget\s+(?:it|that)|scratch\s+that))",
    ],
}


def classify(prompt: str) -> str:
    """Classify a prompt into a query type. Returns category string."""
    if not prompt or not prompt.strip():
        return "ambiguous"

    prompt_lower = prompt.lower().strip()

    # Check each category in order of specificity
    scores = {}
    for category, patterns in PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                score += 1
        if score > 0:
            scores[category] = score

    if not scores:
        return "ambiguous"

    # Highest score wins. Ties broken by specificity order.
    max_score = max(scores.values())
    for category in PATTERNS:
        if scores.get(category) == max_score:
            return category

    return "ambiguous"


def _query_type_path():
    """Path to the ephemeral query-type file."""
    from compat import lcars_dir
    return os.path.join(lcars_dir(), "query-type.tmp")


def write_classification(query_type: str):
    """Write classification for Stop hook to consume."""
    with open(_query_type_path(), "w") as f:
        f.write(query_type)


def read_classification() -> str:
    """Read and return current query classification. Defaults to 'ambiguous'."""
    path = _query_type_path()
    try:
        with open(path) as f:
            return f.read().strip() or "ambiguous"
    except OSError:
        return "ambiguous"


def _load_correction() -> str:
    """Read drift flag and return correction string. Consumes (deletes) the flag."""
    from store import read_and_clear_drift_flag
    from fitness import record_correction

    drift = read_and_clear_drift_flag()
    if not drift:
        return ""

    correction = drift.get("correction", "")
    if correction:
        record_correction(drift)
    return correction


def hook_main_output(prompt: str) -> dict:
    """Classify prompt and check for pending corrections. Returns hook output dict."""
    query_type = classify(prompt)
    write_classification(query_type)

    correction = _load_correction()

    if correction:
        return {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": correction,
            }
        }
    return {}


def hook_main():
    """UserPromptSubmit hook entry point."""
    hook_input = json.load(sys.stdin)
    prompt = hook_input.get("prompt", "")
    output = hook_main_output(prompt)
    if output:
        print(json.dumps(output))


if __name__ == "__main__":
    if "--hook" in sys.argv:
        hook_main()
    else:
        # Standalone: classify text from stdin
        text = sys.stdin.read()
        print(classify(text))
