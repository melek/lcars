"""Tests for lib/score.py — deterministic scoring accuracy."""

from score import score_response, count_words, count_words_before_answer, count_filler_phrases, information_density


class TestFillerDetection:
    def test_known_sycophantic_text(self):
        text = "Great question! I'd be happy to help. Let me know if you need anything else."
        result = score_response(text)
        # "Happy to help" also matches (substring of "I'd be happy to help")
        assert result["padding_count"] >= 3
        assert "Great question" in result["filler_phrases"]
        assert any("happy to" in p.lower() for p in result["filler_phrases"])
        assert "Let me know if" in result["filler_phrases"]

    def test_clean_technical_response(self):
        text = "The error is on line 42. Change 'foo' to 'bar'."
        result = score_response(text)
        assert result["padding_count"] == 0
        assert result["filler_phrases"] == []

    def test_all_filler_categories_detected(self):
        text = (
            "I understand your concern. Great question! "
            "Let me know if you need more. I'd be happy to continue."
        )
        count, phrases = count_filler_phrases(text)
        assert count == 4
        assert "I understand" in phrases
        assert "Great question" in phrases
        assert "Let me know if" in phrases
        assert "I'd be happy to" in phrases

    def test_case_insensitive(self):
        text = "great question! i'd be happy to help."
        count, phrases = count_filler_phrases(text)
        # "Happy to help" also matches independently
        assert count >= 2


class TestPreambleDetection:
    def test_preamble_present(self):
        text = "Great question! The answer is 42."
        pos = count_words_before_answer(text)
        assert pos > 0

    def test_no_preamble(self):
        text = "The answer is 42."
        pos = count_words_before_answer(text)
        assert pos == 0

    def test_multiline_preamble_checks_first_line(self):
        text = "Sure, here's what I found.\nThe config file is at /etc/app.conf"
        pos = count_words_before_answer(text)
        assert pos > 0

    def test_direct_answer_multiline(self):
        text = "42.\nThat's the answer to everything."
        pos = count_words_before_answer(text)
        assert pos == 0


class TestInformationDensity:
    def test_high_density(self):
        text = "PostgreSQL indexes accelerate queries through B-tree structures."
        density = information_density(text)
        assert density > 0.60

    def test_low_density(self):
        text = "I would have to say that it is the one that is in the thing over there."
        density = information_density(text)
        assert density < 0.50

    def test_code_block_density(self):
        text = "def sort_list(items):\n    return sorted(items)"
        density = information_density(text)
        # Code has its own density profile — just verify it computes without error
        assert 0.0 <= density <= 1.0


class TestWordBoundaries:
    def test_substring_not_matched(self):
        """Words containing filler phrases as substrings should not match."""
        result = score_response("The solution is uncertainly better than the alternative.")
        assert result["padding_count"] == 0

    def test_filler_still_matched_standalone(self):
        """Filler phrases still match when used as standalone phrases."""
        result = score_response("Certainly! The answer is 42.")
        assert result["padding_count"] >= 1


class TestEdgeCases:
    def test_empty_string(self):
        result = score_response("")
        assert result["word_count"] == 0
        assert result["padding_count"] == 0
        assert result["info_density"] == 0.0

    def test_whitespace_only(self):
        result = score_response("   \n\n  ")
        assert result["word_count"] == 0

    def test_none_input(self):
        result = score_response(None)
        assert result["word_count"] == 0

    def test_single_word(self):
        result = score_response("Yes.")
        assert result["word_count"] == 1
        assert result["padding_count"] == 0
