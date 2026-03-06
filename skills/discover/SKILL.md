---
name: discover
description: Scan environment for non-standard CLI tools and show registry status
---

# LCARS Environment Discovery

Scan the system PATH for useful CLI tools and manage the tool registry.

## Instructions

When user runs `/lcars:discover`:

### 1. Run Environment Scan

```bash
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/lib'); from discover import scan; import json; print(json.dumps(scan(), indent=2))"
```

Report: tools found, newly discovered, removed since last scan.

### 2. Show Registry Status

```bash
python3 -c "
import sys, json
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/lib')
import registry
reg = registry.load()
tools = reg.get('tools', [])
for t in sorted(tools, key=lambda x: x.get('tier', '')):
    rate = ''
    inv = t.get('lifetime_invocations', 0)
    if inv > 0:
        r = t.get('lifetime_successes', 0) / inv
        rate = f' fitness={r:.0%}'
    print(f'{t[\"id\"]:20s}  {t[\"tier\"]:10s}  {t[\"status\"]:8s}  inv={inv}{rate}  {t.get(\"description\", \"\")}')
"
```

### 3. Display by Tier

Group tools into sections:

- **Promoted** (injected into session context): list with usage stats
- **Standard** (tracked, not injected): list with fitness rate
- **Candidate** (newly discovered): list with path
- **Archived/Dormant**: count only, unless user asks for details

### 4. Show Allowlist Info

Report total tools in `data/discoverable.json` vs. found on system.

If user asks to add a tool to the allowlist, edit `data/discoverable.json` directly.

## When Nothing Is Discovered

If no tools found, suggest checking PATH or installing common tools (rg, fd, jq, gh).
