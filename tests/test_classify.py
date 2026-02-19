"""Tests for lib/classify.py — deterministic query-type classification."""

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


class TestEdgeCases:
    def test_empty_string(self):
        assert classify("") == "ambiguous"

    def test_whitespace(self):
        assert classify("   ") == "ambiguous"

    def test_none_like(self):
        # classify expects a string; empty should be safe
        assert classify("") == "ambiguous"
