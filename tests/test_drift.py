"""Tests for lib/drift.py — drift detection, severity, strategy selection."""

from drift import detect, _classify_severity, _select_correction


class TestDriftDetection:
    def test_compound_drift_high_severity(self):
        score = {
            "padding_count": 3,
            "answer_position": 12,
            "info_density": 0.45,
        }
        result = detect(score, "factual")
        assert result is not None
        assert result["severity"] == "high"
        assert "compound" in result["categories"] or len(result["categories"]) > 1
        assert "filler" in result["categories"]
        assert "preamble" in result["categories"]
        assert "density" in result["categories"]

    def test_code_query_below_density_no_drift(self):
        """Code threshold is 0.50. Density 0.52 should NOT trigger drift."""
        score = {
            "padding_count": 0,
            "answer_position": 0,
            "info_density": 0.52,
        }
        result = detect(score, "code")
        assert result is None

    def test_factual_query_same_density_drifts(self):
        """Global threshold is 0.60. Density 0.52 SHOULD trigger drift for factual."""
        score = {
            "padding_count": 0,
            "answer_position": 0,
            "info_density": 0.52,
        }
        result = detect(score, "factual")
        assert result is not None
        assert "density" in result["categories"]

    def test_no_drift_clean_score(self):
        score = {
            "padding_count": 0,
            "answer_position": 0,
            "info_density": 0.75,
        }
        result = detect(score, "factual")
        assert result is None


class TestSeverityClassification:
    def test_high_filler_count(self):
        score = {"padding_count": 3, "answer_position": 0, "info_density": 0.70}
        severity = _classify_severity(score, ["filler"], 0.60)
        assert severity == "high"

    def test_low_filler_count(self):
        score = {"padding_count": 1, "answer_position": 0, "info_density": 0.70}
        severity = _classify_severity(score, ["filler"], 0.60)
        assert severity == "low"

    def test_multiple_categories_always_high(self):
        score = {"padding_count": 1, "answer_position": 3, "info_density": 0.70}
        severity = _classify_severity(score, ["filler", "preamble"], 0.60)
        assert severity == "high"

    def test_high_density_margin(self):
        score = {"padding_count": 0, "answer_position": 0, "info_density": 0.45}
        severity = _classify_severity(score, ["density"], 0.60)
        assert severity == "high"  # 0.60 - 0.45 = 0.15 > 0.10


class TestCorrectionSelection:
    def test_filler_high_returns_template_with_placeholder(self):
        score = {"padding_count": 5, "answer_position": 0, "info_density": 0.70}
        correction = _select_correction("filler", "high", "*", score, ["filler:5"])
        assert "5" in correction  # {count} should be formatted
        assert "filler" in correction.lower() or "cognitive" in correction.lower()

    def test_code_density_low_returns_empty(self):
        """Code + low density should return empty template (no correction)."""
        score = {"padding_count": 0, "answer_position": 0, "info_density": 0.48}
        correction = _select_correction("density", "low", "code", score, ["density:0.48"])
        assert correction == ""

    def test_compound_high_includes_reasons(self):
        reasons = ["filler:3", "preamble:8w"]
        score = {"padding_count": 3, "answer_position": 8, "info_density": 0.55}
        correction = _select_correction("compound", "high", "*", score, reasons)
        assert "filler:3" in correction
        assert "preamble:8w" in correction
