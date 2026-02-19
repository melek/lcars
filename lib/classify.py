#!/usr/bin/env python3
"""Deterministic query-type classifier.

Classifies user prompts by structure and keywords. No LLM calls.
Categories: factual, diagnostic, code, emotional, claim, ambiguous, meta.

Hook mode (UserPromptSubmit): reads hook JSON from stdin, classifies prompt,
writes classification to query-type.tmp for Stop hook to consume.
"""

import json
import os
import re
import sys

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
    "factual": [
        r"(?:what\s+is|who\s+is|when\s+(?:did|was|is)|where\s+(?:is|are|was))",
        r"(?:how\s+(?:many|much|long|old|far|often))",
        r"(?:list\s+(?:the|all)|show\s+me|find\s+(?:the|all))",
        r"(?:look\s+up|search\s+for|check\s+(?:the|if|whether))",
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
    lcars_dir = os.path.join(os.path.expanduser("~"), ".claude", "lcars")
    os.makedirs(lcars_dir, exist_ok=True)
    return os.path.join(lcars_dir, "query-type.tmp")


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


def hook_main():
    """UserPromptSubmit hook entry point."""
    hook_input = json.load(sys.stdin)
    prompt = hook_input.get("prompt", "")
    query_type = classify(prompt)
    write_classification(query_type)


if __name__ == "__main__":
    if "--hook" in sys.argv:
        hook_main()
    else:
        # Standalone: classify text from stdin
        text = sys.stdin.read()
        print(classify(text))
