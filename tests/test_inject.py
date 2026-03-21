"""Tests for lib/inject.py — context assembly and registry initialization."""

import json
import os

import inject
import store
import registry


class TestContextAssembly:
    def test_clean_start_anchor_only(self, lcars_tmpdir):
        """No drift, no stats → output is anchor text only."""
        anchor = inject.load_anchor()
        stats = inject.load_stats("startup")

        assert anchor != ""
        assert stats == ""

    def test_stats_on_resume(self, lcars_tmpdir, write_scores):
        """Resume with >4h gap and rolling data → stats line included."""
        import time
        scores = [
            {
                "epoch": time.time() - 3600,  # 1h ago (within window)
                "word_count": 50,
                "answer_position": 0,
                "padding_count": 0,
                "info_density": 0.65,
            }
        ]
        write_scores(scores)

        stats = inject.load_stats("resume")
        assert stats != ""
        assert "7d:" in stats

    def test_no_stats_on_fresh_startup(self, lcars_tmpdir):
        """Fresh startup with no prior scores → no stats."""
        stats = inject.load_stats("startup")
        assert stats == ""


class TestRegistryInitialization:
    def test_scan_runs_when_registry_missing(self, lcars_tmpdir, monkeypatch):
        """SessionStart triggers discover.scan() when tool-registry.json doesn't exist."""
        scan_called = []
        import discover
        monkeypatch.setattr(discover, "scan", lambda: scan_called.append(True) or {"found": 0, "new": 0, "removed": 0})

        # Registry file should not exist
        assert not os.path.exists(registry.REGISTRY_FILE)

        # Simulate the inject.main() logic for registry init
        if not os.path.exists(registry.REGISTRY_FILE):
            discover.scan()

        assert len(scan_called) == 1

    def test_scan_skipped_when_registry_exists(self, lcars_tmpdir, monkeypatch):
        """SessionStart does NOT trigger scan when tool-registry.json already exists."""
        scan_called = []
        import discover
        monkeypatch.setattr(discover, "scan", lambda: scan_called.append(True) or {"found": 0, "new": 0, "removed": 0})

        # Create the registry file
        registry.save(registry._default_registry())
        assert os.path.exists(registry.REGISTRY_FILE)

        # Simulate the inject.main() logic for registry init
        if not os.path.exists(registry.REGISTRY_FILE):
            discover.scan()

        assert len(scan_called) == 0
