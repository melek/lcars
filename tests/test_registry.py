"""Tests for lib/registry.py — unified tool registry CRUD."""

import json
import os
import time

import registry


def _make_entry(tool_id="disc:rg", name="rg", provenance="discovered", status="active", **kwargs):
    entry = {
        "id": tool_id,
        "provenance": provenance,
        "name": name,
        "description": f"test tool {name}",
        "status": status,
        "tier": "candidate",
        "created_epoch": time.time(),
        "last_used_epoch": 0,
        "lifetime_invocations": 0,
        "lifetime_successes": 0,
    }
    entry.update(kwargs)
    return entry


class TestLoadSave:
    def test_load_empty(self, lcars_tmpdir):
        reg = registry.load()
        assert reg["version"] == 1
        assert reg["tools"] == []

    def test_save_and_load(self, lcars_tmpdir):
        reg = {"version": 1, "tools": [_make_entry()]}
        registry.save(reg)

        loaded = registry.load()
        assert len(loaded["tools"]) == 1
        assert loaded["tools"][0]["id"] == "disc:rg"

    def test_load_corrupt_file(self, lcars_tmpdir):
        with open(registry.REGISTRY_FILE, "w") as f:
            f.write("not json")
        reg = registry.load()
        assert reg["version"] == 1
        assert reg["tools"] == []


class TestGet:
    def test_get_existing(self, lcars_tmpdir):
        registry.save({"version": 1, "tools": [_make_entry()]})
        result = registry.get("disc:rg")
        assert result is not None
        assert result["name"] == "rg"

    def test_get_missing(self, lcars_tmpdir):
        registry.save({"version": 1, "tools": [_make_entry()]})
        assert registry.get("disc:nonexistent") is None

    def test_get_empty_registry(self, lcars_tmpdir):
        assert registry.get("disc:rg") is None


class TestUpsert:
    def test_insert_new(self, lcars_tmpdir):
        entry = _make_entry()
        registry.upsert(entry)

        reg = registry.load()
        assert len(reg["tools"]) == 1
        assert reg["tools"][0]["id"] == "disc:rg"

    def test_update_existing(self, lcars_tmpdir):
        entry = _make_entry()
        registry.upsert(entry)

        updated = _make_entry(description="updated description")
        registry.upsert(updated)

        reg = registry.load()
        assert len(reg["tools"]) == 1
        assert reg["tools"][0]["description"] == "updated description"

    def test_unique_ids(self, lcars_tmpdir):
        registry.upsert(_make_entry("disc:rg"))
        registry.upsert(_make_entry("disc:fd", name="fd"))

        reg = registry.load()
        assert len(reg["tools"]) == 2
        ids = [t["id"] for t in reg["tools"]]
        assert len(set(ids)) == 2

    def test_invalid_provenance_rejected(self, lcars_tmpdir):
        import pytest
        with pytest.raises(AssertionError, match="invalid provenance"):
            registry.upsert(_make_entry(provenance="bogus"))

    def test_invalid_status_rejected(self, lcars_tmpdir):
        import pytest
        with pytest.raises(AssertionError, match="invalid status"):
            registry.upsert(_make_entry(status="bogus"))


class TestListByProvenance:
    def test_filter(self, lcars_tmpdir):
        registry.upsert(_make_entry("disc:rg", provenance="discovered"))
        registry.upsert(_make_entry("cryst:formatter", name="formatter", provenance="crystallized"))

        discovered = registry.list_by_provenance("discovered")
        assert len(discovered) == 1
        assert discovered[0]["id"] == "disc:rg"

        crystallized = registry.list_by_provenance("crystallized")
        assert len(crystallized) == 1

    def test_empty_result(self, lcars_tmpdir):
        registry.upsert(_make_entry())
        assert registry.list_by_provenance("user-created") == []


class TestListActive:
    def test_filters_active(self, lcars_tmpdir):
        registry.upsert(_make_entry("disc:rg", status="active"))
        registry.upsert(_make_entry("disc:fd", name="fd", status="archived"))

        active = registry.list_active()
        assert len(active) == 1
        assert active[0]["id"] == "disc:rg"


class TestRecordUsage:
    def test_increment_success(self, lcars_tmpdir):
        registry.upsert(_make_entry())
        registry.record_usage("disc:rg", success=True)

        tool = registry.get("disc:rg")
        assert tool["lifetime_invocations"] == 1
        assert tool["lifetime_successes"] == 1
        assert tool["last_used_epoch"] > 0

    def test_increment_failure(self, lcars_tmpdir):
        registry.upsert(_make_entry())
        registry.record_usage("disc:rg", success=False)

        tool = registry.get("disc:rg")
        assert tool["lifetime_invocations"] == 1
        assert tool["lifetime_successes"] == 0

    def test_monotonic_usage(self, lcars_tmpdir):
        registry.upsert(_make_entry())
        for _ in range(5):
            registry.record_usage("disc:rg", success=True)

        tool = registry.get("disc:rg")
        assert tool["lifetime_invocations"] == 5
        assert tool["lifetime_successes"] == 5

    def test_nonexistent_tool_noop(self, lcars_tmpdir):
        registry.upsert(_make_entry())
        registry.record_usage("disc:nonexistent", success=True)
        # No error, no change
        tool = registry.get("disc:rg")
        assert tool["lifetime_invocations"] == 0


class TestMarkStatus:
    def test_change_status(self, lcars_tmpdir):
        registry.upsert(_make_entry(status="active"))
        registry.mark_status("disc:rg", "archived")

        tool = registry.get("disc:rg")
        assert tool["status"] == "archived"

    def test_invalid_status(self, lcars_tmpdir):
        import pytest
        registry.upsert(_make_entry())
        with pytest.raises(AssertionError, match="invalid status"):
            registry.mark_status("disc:rg", "deleted")
