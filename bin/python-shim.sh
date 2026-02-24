#!/bin/sh
# LCARS Python shim — resolves python3 or python across platforms.
# Validates Python >= 3.10 before exec.

for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        valid=$("$cmd" -c "import sys; print(sys.version_info >= (3, 10))" 2>/dev/null)
        if [ "$valid" = "True" ]; then
            exec "$cmd" "$@"
        fi
    fi
done

echo "LCARS: Python 3.10+ not found" >&2
exit 1
