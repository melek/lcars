"""Tests for lib/foundry.py — strategy proposal generation."""

import json
import time

import foundry


class TestGapProposals:
    def test_gap_detected(self, lcars_tmpdir, write_outcomes):
        """Validated drift pattern with low fitness + no query-specific strategy → gap."""
        # Write validated pattern
        patterns = [{"drift_type": "filler", "status": "validated", "sessions": 6, "unique_days": 3}]
        with open(foundry.PATTERNS_FILE, "w") as f:
            json.dump(patterns, f)

        # Write outcomes: filler drift on "emotional" queries, mostly ineffective
        outcomes = [
            {
                "epoch": time.time(),
                "categories": ["filler"],
                "query_type": "emotional",
                "effective": False,
            }
            for _ in range(6)
        ]
        # Add 1 effective to avoid 0/6
        outcomes[0]["effective"] = True
        write_outcomes(outcomes)

        result = foundry.analyze()
        gap_proposals = [p for p in result["proposals"] if p["type"] == "gap"]
        assert len(gap_proposals) >= 1
        assert gap_proposals[0]["query"] == "emotional"


class TestSuppressionProposals:
    def test_suppression_detected(self, lcars_tmpdir, write_outcomes):
        """Strategy fires >30% of the time, effective <50% → suppression."""
        # Write patterns (needed for gap analysis but not suppression)
        with open(foundry.PATTERNS_FILE, "w") as f:
            json.dump([], f)

        # 10 outcomes total, 5 are "filler" (50% fire rate), only 1 effective (20% fitness)
        outcomes = []
        for i in range(10):
            if i < 5:
                outcomes.append({
                    "epoch": time.time(),
                    "categories": ["filler"],
                    "query_type": "factual",
                    "effective": i == 0,  # Only first one effective
                })
            else:
                outcomes.append({
                    "epoch": time.time(),
                    "categories": ["density"],
                    "query_type": "factual",
                    "effective": True,
                })
        write_outcomes(outcomes)

        result = foundry.analyze()
        suppression_proposals = [p for p in result["proposals"] if p["type"] == "suppression"]
        assert len(suppression_proposals) >= 1
        assert suppression_proposals[0]["drift"] == "filler"


class TestApplyProposals:
    def test_apply_gap_proposal(self, lcars_tmpdir):
        """Applying a gap proposal adds a strategy to corrections.json."""
        staged = [{
            "type": "gap",
            "drift": "filler",
            "severity": "*",
            "query": "emotional",
            "reason": "test",
            "suggestion": "[Prior emotional response had filler. Omit gently.]",
            "evidence": {"total": 6, "effective": 1},
            "epoch": time.time(),
        }]
        with open(foundry.STAGED_FILE, "w") as f:
            json.dump(staged, f)

        result = foundry.apply_proposals([0])
        assert result["applied"] == 1
        assert result["remaining_staged"] == 0

        # Verify the strategy was added to corrections.json
        corrections_path = foundry._plugin_root() / "data" / "corrections.json"
        with open(corrections_path) as f:
            data = json.load(f)
        emotional_strategies = [
            s for s in data["strategies"]
            if s.get("query") == "emotional" and s.get("drift") == "filler"
        ]
        assert len(emotional_strategies) >= 1

    def test_apply_restores_corrections(self, lcars_tmpdir):
        """After applying, re-read corrections.json to restore original state."""
        # This test modifies corrections.json — read original for cleanup
        corrections_path = foundry._plugin_root() / "data" / "corrections.json"
        with open(corrections_path) as f:
            original = f.read()

        try:
            staged = [{
                "type": "gap",
                "drift": "filler",
                "severity": "*",
                "query": "meta",
                "reason": "test",
                "suggestion": "[test]",
                "evidence": {},
                "epoch": time.time(),
            }]
            with open(foundry.STAGED_FILE, "w") as f:
                json.dump(staged, f)
            foundry.apply_proposals([0])
        finally:
            # Restore original
            with open(corrections_path, "w") as f:
                f.write(original)
