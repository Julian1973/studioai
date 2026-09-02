"""A whole-file advisory lock that works on Linux/macOS (fcntl) AND Windows (msvcrt).

Two engine modules serialise their read-modify-write transactions with `fcntl.flock`; `fcntl` does not
exist on Windows, so the studio refused to even import there (found 2026-09-02, the first Windows start
of the projects branch). `lock(fh)` / `unlock(fh)` take an open file object and block until the lock is
held, exactly as the flock calls did.
"""
from __future__ import annotations

import os

if os.name == "nt":
    import msvcrt

    def lock(fh) -> None:
        # msvcrt locks a byte range from the current position; lock the first byte, blocking.
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)

    def unlock(fh) -> None:
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def lock(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)

    def unlock(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
