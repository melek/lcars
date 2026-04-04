"""Tests for lib/judge.py — escalation gate, judge call, response validation, monotonic enhancement."""

import json
import time
from unittest.mock import patch, MagicMock

import judge
import drift


class TestJudgeConfig:
    def test_config_absent_returns_none(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert judge.judge_config() is None

    def test_config_empty_returns_none(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        assert judge.judge_config() is None

    def test_config_present_returns_dict(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        config = judge.judge_config()
        assert config is not None
        assert config["api_key"] == "sk-test-123"
        assert config["model"] == judge.DEFAULT_MODEL
        assert config["max_calls"] == judge.DEFAULT_MAX_CALLS

    def test_config_custom_max_calls(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        monkeypatch.setenv("LCARS_JUDGE_MAX_CALLS", "5")
        config = judge.judge_config()
        assert config["max_calls"] == 5


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
        # density=0.61, threshold=0.60 for factual -> within 0.03
        escalate, reason = judge.should_escalate(self._score(padding=0, density=0.61), "factual")
        assert escalate
        assert reason == "borderline_density"

    def test_novel_filler_escalated(self):
        # density=0.64 is above borderline_density range (>0.03 from 0.60)
        # but below clearly_clean (< 0.60+0.05=0.65), with preamble
        escalate, reason = judge.should_escalate(self._score(padding=0, density=0.64, position=5), "factual")
        assert escalate
        assert reason == "novel_filler"

    def test_clearly_clean_high_density(self):
        # padding=0, density well above threshold+0.05
        escalate, reason = judge.should_escalate(self._score(padding=0, density=0.80), "factual")
        assert not escalate
        assert reason == "clearly_clean"

    def test_no_criteria_met_dead_zone(self):
        # density=0.64: above borderline_density (>0.03 from 0.60) but below
        # clearly_clean (<0.65). No filler, no preamble. Falls through all rules.
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
        result = judge.validate_response('{"SyA": 1, "VDet": 0, "EpAd": 2}')
        assert result is None

    def test_malformed_json_returns_none(self):
        assert judge.validate_response("not json at all") is None

    def test_non_integer_returns_none(self):
        result = judge.validate_response('{"SyA": "high", "VDet": 0, "EpAd": 0, "EPad": 0}')
        assert result is None

    def test_none_input_returns_none(self):
        assert judge.validate_response(None) is None

    def test_array_input_returns_none(self):
        assert judge.validate_response("[1, 2, 3, 4]") is None


class TestCallJudge:
    def _mock_api_response(self, judge_json_str):
        """Create a mock urllib response with Messages API format."""
        response_body = json.dumps({
            "content": [{"type": "text", "text": judge_json_str}],
            "model": "claude-haiku-4-5-20251001",
            "usage": {"input_tokens": 200, "output_tokens": 30},
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def _config(self):
        return {"api_key": "sk-test", "model": "claude-haiku-4-5-20251001", "max_calls": 20, "timeout": 5}

    def test_success_returns_scores(self, monkeypatch):
        judge._session_call_count = 0
        mock_resp = self._mock_api_response('{"SyA": 0, "VDet": 1, "EpAd": 0, "EPad": 2}')
        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: mock_resp)

        result = judge.call_judge("test response", {"padding_count": 1}, "factual", self._config())
        assert result is not None
        assert result["SyA"] == 0
        assert result["VDet"] == 1
        assert result["EpAd"] == 0
        assert result["EPad"] == 2

    def test_provenance_fields(self, monkeypatch):
        judge._session_call_count = 0
        mock_resp = self._mock_api_response('{"SyA": 0, "VDet": 0, "EpAd": 0, "EPad": 0}')
        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: mock_resp)

        result = judge.call_judge("test", {}, "factual", self._config())
        assert "model" in result
        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], int)

    def test_timeout_returns_none(self, monkeypatch):
        judge._session_call_count = 0
        import socket
        monkeypatch.setattr("urllib.request.urlopen",
                            lambda req, timeout=None: (_ for _ in ()).throw(socket.timeout("timed out")))

        result = judge.call_judge("test", {}, "factual", self._config())
        assert result is None

    def test_network_error_returns_none(self, monkeypatch):
        judge._session_call_count = 0
        monkeypatch.setattr("urllib.request.urlopen",
                            lambda req, timeout=None: (_ for _ in ()).throw(
                                urllib.error.URLError("connection refused")))

        import urllib.error
        result = judge.call_judge("test", {}, "factual", self._config())
        assert result is None

    def test_malformed_api_response_returns_none(self, monkeypatch):
        judge._session_call_count = 0
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json"
        monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: mock_resp)

        result = judge.call_judge("test", {}, "factual", self._config())
        assert result is None

    def test_session_cap_enforced(self, monkeypatch):
        judge._session_call_count = 0
        config = self._config()
        config["max_calls"] = 2

        call_count = 0
        def mock_urlopen(req, timeout=None):
            nonlocal call_count
            call_count += 1
            return self._mock_api_response('{"SyA": 0, "VDet": 0, "EpAd": 0, "EPad": 0}')

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

        # First two calls succeed
        judge.call_judge("test", {}, "factual", config)
        judge.call_judge("test", {}, "factual", config)
        # Third call returns None without HTTP call
        result = judge.call_judge("test", {}, "factual", config)
        assert result is None
        assert call_count == 2  # only 2 actual HTTP calls made


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
