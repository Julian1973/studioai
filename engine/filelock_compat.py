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
    import time

    def lock(fh) -> None:
        # msvcrt locks a byte range from the current position; lock the first byte. LK_LOCK
        # gives up after ten one-second tries with "[Errno 36] Resource deadlock avoided" —
        # found live 2026-09-02 when four scene directors queued on the serial lock at once.
        # flock blocks for as long as it takes; so does this: non-blocking tries, forever.
        fh.seek(0)
        while True:
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                time.sleep(0.25)
                fh.seek(0)

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
