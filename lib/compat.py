"""Cross-platform file locking and path utilities.

Provides fcntl-equivalent locking on Windows via msvcrt.
All file operations in the plugin use this module instead of fcntl directly.
"""

import os
import sys


def file_lock(f, exclusive=True):
    """Acquire a file lock. Blocks until lock is available."""
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK if exclusive else msvcrt.LK_RLCK, 1)
    else:
        import fcntl
        fcntl.flock(f, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)


def file_unlock(f):
    """Release a file lock."""
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(f, fcntl.LOCK_UN)


def lcars_dir():
    """Return the plugin runtime data directory, creating it if needed."""
    d = os.path.join(os.path.expanduser("~"), ".claude", "lcars")
    os.makedirs(d, exist_ok=True)
    return d


def lcars_memory_dir():
    """Return the plugin memory subdirectory, creating it if needed."""
    d = os.path.join(lcars_dir(), "memory")
    os.makedirs(d, exist_ok=True)
    return d
