#!/usr/bin/env python3
"""Deterministic cognitive ergonomics scorer for Claude Code responses.

Scores responses against cognitive load metrics: filler phrases, preamble
detection, answer position, information density. Pure stdlib — no dependencies.

Hook mode (--hook): reads hook JSON from stdin, extracts transcript_path,
scores the last assistant message, appends to store, flags drift.
"""

import json
import re
import sys
from pathlib import Path

# --- Scoring patterns ---

FILLER_CATEGORIES = {
    "affect_simulation": [
        r"I understand",
        r"I'm sorry to hear",
        r"Happy to help",
        r"I'm here to help",
        r"Don't worry",
        r"No worries",
    ],
    "engagement_filler": [
        r"Great question",
        r"Good question",
        r"Excellent question",
        r"That's a great question",
        r"That's an interesting question",
        r"Absolutely!",
        r"Certainly!",
        r"This is a classic",
    ],
    "interaction_extension": [
        r"Let me know if",
        r"Would you like me to",
        r"Feel free to",
        r"Don't hesitate",
        r"Hope this helps",
        r"I hope this helps",
    ],
    "rapport_building": [
        r"I'd be happy to",
        r"I would be happy to",
        r"Of course!",
        r"Of course,",
        r"I can help",
        r"I can definitely",
    ],
}

FILLER_PATTERNS = [p for patterns in FILLER_CATEGORIES.values() for p in patterns]

PREAMBLE_PATTERNS = [
    r"^I'?d be happy to",
    r"^I would be happy to",
    r"^Of course",
    r"^Sure[,!.]",
    r"^Great question",
    r"^Good question",
    r"^Let me",
    r"^Here'?s",
    r"^I found",
    r"^Based on",
    r"^Looking at",
    r"^I can help",
    r"^I'?ll help",
    r"^Absolutely",
    r"^Definitely",
    r"^Certainly",
    r"^That'?s a great",
    r"^That'?s an? (interesting|good|excellent)",
    r"^Thank you for",
    r"^Thanks for",
]

FUNCTION_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "it", "its", "this", "that", "these", "those",
    "i", "you", "we", "they", "he", "she", "me", "my", "your", "our",
    "their", "and", "or", "but", "not", "if", "then", "than", "so",
    "no", "yes", "all", "any", "each", "every", "some", "such",
})


# --- Scoring functions ---

def count_words(text: str) -> int:
    return len([w for w in text.split() if w])


def count_words_before_answer(text: str) -> int:
    """Count preamble words before substantive content."""
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if any(re.match(p, line, re.IGNORECASE) for p in PREAMBLE_PATTERNS):
            return count_words(line)
        break
    return 0


def count_filler_phrases(text: str) -> tuple[int, list[str]]:
    found = []
    for pattern in FILLER_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found.extend(matches)
    return len(found), found


def information_density(text: str) -> float:
    words = [w.lower().strip(".,!?;:\"'()[]{}#*`~>|-_/\\") for w in text.split() if w.strip()]
    if not words:
        return 0.0
    content_words = [w for w in words if w and w not in FUNCTION_WORDS and len(w) > 1]
    return round(len(content_words) / len(words), 3)


def score_response(text: str) -> dict:
    """Score a single response. Returns metrics dict."""
    if not text:
        return {
            "word_count": 0,
            "answer_position": 0,
            "padding_count": 0,
            "filler_phrases": [],
            "info_density": 0.0,
        }

    padding_count, filler_phrases = count_filler_phrases(text)

    return {
        "word_count": count_words(text),
        "answer_position": count_words_before_answer(text),
        "padding_count": padding_count,
        "filler_phrases": filler_phrases,
        "info_density": information_density(text),
    }


# --- Transcript parsing ---

def extract_last_assistant_text(transcript_path: str) -> str | None:
    """Extract the last assistant text message from a JSONL transcript."""
    path = Path(transcript_path)
    if not path.exists():
        return None

    last_text = None
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") != "assistant":
                    continue

                content = entry.get("message", {}).get("content", [])
                for block in content:
                    if block.get("type") == "text":
                        last_text = block["text"]
    except OSError:
        return None

    return last_text


# --- Hook CLI ---

def hook_main():
    """Stop hook entry point. Reads hook JSON from stdin, scores, stores."""
    from store import append_score, detect_drift, write_drift_flag, rotate_store

    hook_input = json.load(sys.stdin)

    # Guard against infinite loops
    if hook_input.get("stop_hook_active"):
        return

    transcript_path = hook_input.get("transcript_path")
    if not transcript_path:
        return

    text = extract_last_assistant_text(transcript_path)
    if not text:
        return

    score = score_response(text)
    store_score = {k: v for k, v in score.items() if k != "filler_phrases"}
    append_score(store_score)

    drift = detect_drift(score)
    if drift:
        write_drift_flag(drift)

    # Rotate on ~1% of invocations (amortized cost)
    import random
    if random.random() < 0.01:
        rotate_store()


if __name__ == "__main__":
    if "--hook" in sys.argv:
        hook_main()
    else:
        # Standalone mode: score text from stdin
        text = sys.stdin.read()
        result = score_response(text)
        print(json.dumps(result, indent=2))
