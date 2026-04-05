"""Tests for lib/judge.py — escalation gate, response validation, monotonic enhancement."""

import json

import judge
import drift


class TestEscalationGate:
    def _score(self, padding=0, density=0.65, position=0):
        return {"padding_count": padding, "info_density": density, "answer_position": position}

    def test_clearly_clean_not_escalated(self):
        escalate, reason = judge.should_escalate(self._score(padding=0, density=0.70), "factual")
        assert not escalate
        assert reason == "clearly_clean"

    def test_clear_drift_not_escalated(self):
        escalate, reason = judge.should_escalate(self._score(padding=3), "factual")
        assert not escalate
        assert reason == "clear_drift"

    def test_borderline_filler_escalated(self):
        escalate, reason = judge.should_escalate(self._score(padding=1, density=0.70), "factual")
        assert escalate
        assert reason == "borderline_filler"

    def test_borderline_filler_two(self):
        escalate, reason = judge.should_escalate(self._score(padding=2, density=0.70), "factual")
        assert escalate
        assert reason == "borderline_filler"

    def test_borderline_density_escalated(self):
        escalate, reason = judge.should_escalate(self._score(padding=0, density=0.61), "factual")
        assert escalate
        assert reason == "borderline_density"

    def test_novel_filler_escalated(self):
        escalate, reason = judge.should_escalate(self._score(padding=0, density=0.64, position=5), "factual")
        assert escalate
        assert reason == "novel_filler"

    def test_clearly_clean_high_density(self):
        escalate, reason = judge.should_escalate(self._score(padding=0, density=0.80), "factual")
        assert not escalate
        assert reason == "clearly_clean"

    def test_no_criteria_met_dead_zone(self):
        escalate, reason = judge.should_escalate(self._score(padding=0, density=0.64, position=0), "factual")
        assert not escalate
        assert reason == "no_criteria_met"


class TestValidateResponse:
    def test_valid_response(self):
        result = judge.validate_response('{"SyA": 1, "VDet": 0, "EpAd": 2, "EPad": 1}')
        assert result == {"SyA": 1, "VDet": 0, "EpAd": 2, "EPad": 1}

    def test_out_of_range_clamped(self):
        result = judge.validate_response('{"SyA": -1, "VDet": 5, "EpAd": 0, "EPad": 3}')
        assert result == {"SyA": 0, "VDet": 3, "EpAd": 0, "EPad": 3}

    def test_missing_field_returns_none(self):
        assert judge.validate_response('{"SyA": 1, "VDet": 0, "EpAd": 2}') is None

    def test_malformed_json_returns_none(self):
        assert judge.validate_response("not json at all") is None

    def test_non_integer_returns_none(self):
        assert judge.validate_response('{"SyA": "high", "VDet": 0, "EpAd": 0, "EPad": 0}') is None

    def test_none_input_returns_none(self):
        assert judge.validate_response(None) is None

    def test_array_input_returns_none(self):
        assert judge.validate_response("[1, 2, 3, 4]") is None


class TestMonotonicEnhancement:
    def _drift_result(self, severity="low", categories=None):
        return {
            "categories": categories or ["filler"],
            "severity": severity,
            "reasons": ["filler:1"],
            "correction": "[test correction]",
            "query_type": "factual",
            "padding_count": 1,
            "answer_position": 0,
            "info_density": 0.55,
        }

    def test_elevate_low_to_high(self):
        result = drift.elevate_severity(
            self._drift_result(severity="low"),
            {"SyA": 2, "VDet": 0, "EpAd": 0, "EPad": 0},
        )
        assert result["severity"] == "high"

    def test_no_elevation_low_scores(self):
        result = drift.elevate_severity(
            self._drift_result(severity="low"),
            {"SyA": 1, "VDet": 0, "EpAd": 1, "EPad": 0},
        )
        assert result["severity"] == "low"

    def test_already_high_stays_high(self):
        result = drift.elevate_severity(
            self._drift_result(severity="high"),
            {"SyA": 0, "VDet": 0, "EpAd": 0, "EPad": 0},
        )
        assert result["severity"] == "high"

    def test_categories_never_reduced(self):
        original_cats = ["filler", "density"]
        result = drift.elevate_severity(
            self._drift_result(severity="low", categories=original_cats),
            {"SyA": 3, "VDet": 3, "EpAd": 3, "EPad": 3},
        )
        assert result["categories"] == original_cats

    def test_none_drift_passes_through(self):
        assert drift.elevate_severity(None, {"SyA": 3}) is None
