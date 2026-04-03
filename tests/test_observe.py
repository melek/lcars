"""Tests for lib/observe.py — tool usage observation and CLI tool attribution."""

import json

import observe
import registry


class TestExtractExecutables:
    def test_simple_command(self):
        assert observe._extract_executables("gh pr view") == ["gh"]

    def test_chained_commands(self):
        result = observe._extract_executables("git status && gh pr list")
        assert "git" in result
        assert "gh" in result

    def test_piped_commands(self):
        result = observe._extract_executables("echo hello | jq .")
        assert "echo" in result
        assert "jq" in result

    def test_semicolon_separated(self):
        result = observe._extract_executables("cd /tmp; gh issue list")
        assert "cd" in result
        assert "gh" in result

    def test_env_var_prefix(self):
        assert observe._extract_executables("GH_TOKEN=xxx gh pr view") == ["gh"]

    def test_absolute_path(self):
        assert observe._extract_executables("/usr/bin/gh pr view") == ["gh"]

    def test_empty_command(self):
        assert observe._extract_executables("") == []

    def test_deduplicates(self):
        result = observe._extract_executables("gh pr list && gh issue list")
        assert result == ["gh"]

    def test_or_operator(self):
        result = observe._extract_executables("command1 || gh pr view")
        assert "gh" in result


class TestBashToolRegistryAttribution:
    def test_bash_gh_increments_registry(self, lcars_tmpdir, monkeypatch):
        """Bash call with 'gh' command increments disc:gh usage."""
        import io

        # Set up registry with a discovered gh tool
        registry.upsert({
            "id": "disc:gh",
            "provenance": "discovered",
            "name": "gh",
            "description": "GitHub CLI",
            "status": "active",
            "tier": "candidate",
            "lifetime_invocations": 0,
            "lifetime_successes": 0,
            "last_used_epoch": 0,
        })

        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "gh pr list"},
            "tool_response": {"output": "..."},
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook_input)))

        # Patch tool log path to use temp dir
        monkeypatch.setattr(observe, "_tool_log_path",
                            lambda: str(lcars_tmpdir / "tool-usage.jsonl"))

        observe.hook_main()

        entry = registry.get("disc:gh")
        assert entry["lifetime_invocations"] == 1
        assert entry["lifetime_successes"] == 1

    def test_bash_non_discovered_tool_no_increment(self, lcars_tmpdir, monkeypatch):
        """Bash call with unknown command doesn't touch registry."""
        import io

        registry.upsert({
            "id": "disc:gh",
            "provenance": "discovered",
            "name": "gh",
            "description": "GitHub CLI",
            "status": "active",
            "tier": "candidate",
            "lifetime_invocations": 0,
            "lifetime_successes": 0,
            "last_used_epoch": 0,
        })

        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "tool_response": {"output": "..."},
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook_input)))
        monkeypatch.setattr(observe, "_tool_log_path",
                            lambda: str(lcars_tmpdir / "tool-usage.jsonl"))

        observe.hook_main()

        entry = registry.get("disc:gh")
        assert entry["lifetime_invocations"] == 0

    def test_bash_error_increments_invocations_not_successes(self, lcars_tmpdir, monkeypatch):
        """Failed Bash call increments invocations but not successes."""
        import io

        registry.upsert({
            "id": "disc:gh",
            "provenance": "discovered",
            "name": "gh",
            "description": "GitHub CLI",
            "status": "active",
            "tier": "candidate",
            "lifetime_invocations": 0,
            "lifetime_successes": 0,
            "last_used_epoch": 0,
        })

        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "gh pr view 999"},
            "tool_response": {"is_error": True, "output": "not found"},
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook_input)))
        monkeypatch.setattr(observe, "_tool_log_path",
                            lambda: str(lcars_tmpdir / "tool-usage.jsonl"))

        observe.hook_main()

        entry = registry.get("disc:gh")
        assert entry["lifetime_invocations"] == 1
        assert entry["lifetime_successes"] == 0

    def test_chained_bash_command_matches_multiple(self, lcars_tmpdir, monkeypatch):
        """Bash call with chained commands matches all discovered tools."""
        import io

        for tool_id, name in [("disc:gh", "gh"), ("disc:jq", "jq")]:
            registry.upsert({
                "id": tool_id,
                "provenance": "discovered",
                "name": name,
                "description": name,
                "status": "active",
                "tier": "candidate",
                "lifetime_invocations": 0,
                "lifetime_successes": 0,
                "last_used_epoch": 0,
            })

        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "gh pr list --json title | jq '.[].title'"},
            "tool_response": {"output": "..."},
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook_input)))
        monkeypatch.setattr(observe, "_tool_log_path",
                            lambda: str(lcars_tmpdir / "tool-usage.jsonl"))

        observe.hook_main()

        assert registry.get("disc:gh")["lifetime_invocations"] == 1
        assert registry.get("disc:jq")["lifetime_invocations"] == 1

    def test_non_bash_tool_unchanged(self, lcars_tmpdir, monkeypatch):
        """Non-Bash tool calls don't trigger command parsing."""
        import io

        hook_input = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test"},
            "tool_response": {"output": "..."},
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook_input)))
        monkeypatch.setattr(observe, "_tool_log_path",
                            lambda: str(lcars_tmpdir / "tool-usage.jsonl"))

        observe.hook_main()
        # Should not raise — just logs normally
