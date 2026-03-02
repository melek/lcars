"""Tests for lib/classify.py — deterministic query-type classification."""

import store
import fitness
from classify import classify


class TestQueryTypes:
    def test_code_query(self):
        # "Write a function" matches the code pattern
        assert classify("Write a function that sorts a list in Python") == "code"

    def test_code_query_with_backticks(self):
        assert classify("Fix this: ```def foo(): pass```") == "code"

    def test_code_query_with_error(self):
        # TypeError matches both code (error name) and diagnostic ("not" matches diagnostic patterns)
        # Use a more code-specific context
        assert classify("Getting TypeError in my pytest test suite") == "code"

    def test_diagnostic_query(self):
        assert classify("Why isn't my server starting?") == "diagnostic"

    def test_diagnostic_not_working(self):
        assert classify("The build is broken and I can't compile") == "diagnostic"

    def test_emotional_query(self):
        assert classify("this is so frustrating") == "emotional"

    def test_emotional_query_im_frustrated(self):
        assert classify("I'm frustrated and stuck on this") == "emotional"

    def test_factual_query(self):
        assert classify("What is the capital of France?") == "factual"

    def test_factual_lookup(self):
        assert classify("How many users are in the database?") == "factual"

    def test_claim_query(self):
        assert classify("Is it true that Python is faster than C?") == "claim"

    def test_claim_verify(self):
        assert classify("Can you fact-check this statement?") == "claim"

    def test_meta_query(self):
        assert classify("What tools do you have?") == "meta"

    def test_meta_slash_command(self):
        assert classify("/help") == "meta"

    def test_ambiguous_fallback(self):
        assert classify("thoughts on this?") == "ambiguous"

    def test_ambiguous_minimal(self):
        assert classify("hmm") == "ambiguous"


class TestCorrectionInjection:
    def test_no_drift_no_correction(self, lcars_tmpdir):
        """No drift.json → classify output has no additionalContext."""
        from classify import hook_main_output
        result = hook_main_output("What is Python?")
        assert result.get("hookSpecificOutput", {}).get("additionalContext") is None

    def test_drift_injects_correction(self, lcars_tmpdir):
        """drift.json exists → correction injected via additionalContext."""
        store.write_drift_flag({
            "categories": ["filler"],
            "severity": "high",
            "correction": "[Prior: 3 filler phrases. Cognitive load without information. Omit all.]",
            "query_type": "factual",
            "padding_count": 3,
            "answer_position": 0,
            "info_density": 0.65,
        })
        from classify import hook_main_output
        result = hook_main_output("What is Python?")
        ctx = result["hookSpecificOutput"]["additionalContext"]
        assert "filler" in ctx.lower() or "Omit" in ctx

    def test_drift_flag_consumed_after_injection(self, lcars_tmpdir):
        """drift.json is deleted after correction is read."""
        store.write_drift_flag({
            "categories": ["filler"],
            "severity": "low",
            "correction": "[Prior response contained filler. Omit.]",
            "query_type": "factual",
            "padding_count": 1,
            "answer_position": 0,
            "info_density": 0.65,
        })
        from classify import hook_main_output
        hook_main_output("test prompt")
        assert store.read_and_clear_drift_flag() is None

    def test_correction_records_pending(self, lcars_tmpdir):
        """Injected correction creates a pending-correction.json for fitness tracking."""
        import os
        store.write_drift_flag({
            "categories": ["preamble"],
            "severity": "low",
            "correction": "[Prior response opened with preamble. Answer first.]",
            "query_type": "ambiguous",
            "padding_count": 0,
            "answer_position": 5,
            "info_density": 0.7,
        })
        from classify import hook_main_output
        hook_main_output("test prompt")
        assert os.path.exists(fitness.PENDING_FILE)

    def test_classify_still_writes_query_type(self, lcars_tmpdir):
        """Correction injection doesn't break classification."""
        from classify import hook_main_output, read_classification
        hook_main_output("Write a function that sorts a list")
        assert read_classification() == "code"


class TestEdgeCases:
    def test_empty_string(self):
        assert classify("") == "ambiguous"

    def test_whitespace(self):
        assert classify("   ") == "ambiguous"

    def test_none_like(self):
        # classify expects a string; empty should be safe
        assert classify("") == "ambiguous"
