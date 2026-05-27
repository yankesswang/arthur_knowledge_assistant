"""Shared process lock for Claude CLI calls.

Implements a file-based semaphore: up to CLAUDE_MAX_CONCURRENT claude -p
processes can run at the same time. Each slot is a separate lock file;
a caller grabs whichever slot is free first.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import time
from collections.abc import Callable, Iterator
from pathlib import Path

LOCK_DIR = Path(__file__).resolve().parent / "data"

# Maximum concurrent claude -p invocations. 2 is the sweet spot:
# two jobs finish within the 5-minute prompt-cache TTL window so both
# benefit from cache hits, while a third would likely miss.
CLAUDE_MAX_CONCURRENT = 2


def _slot_path(slot: int) -> Path:
    return LOCK_DIR / f"claude_cli.{slot}.lock"


@contextlib.contextmanager
def claude_cli_lock(
    label: str,
    *,
    on_wait: Callable[[], None] | None = None,
    on_acquired: Callable[[], None] | None = None,
) -> Iterator[None]:
    """Acquire one of CLAUDE_MAX_CONCURRENT slots, then yield.

    Tries each slot non-blocking first; if all are taken, waits on slot 0
    (blocking) so the caller eventually proceeds rather than spinning.
    """
    LOCK_DIR.mkdir(parents=True, exist_ok=True)

    # Open all slot files upfront so we can attempt non-blocking grabs.
    slot_files = [_slot_path(i).open("a+", encoding="utf-8") for i in range(CLAUDE_MAX_CONCURRENT)]

    acquired_fd = None
    try:
        # Round 1: try every slot without blocking.
        for i, fh in enumerate(slot_files):
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired_fd = fh
                break
            except BlockingIOError:
                continue

        # Round 2: all slots busy — notify caller, then block on slot 0.
        if acquired_fd is None:
            if on_wait:
                on_wait()
            fcntl.flock(slot_files[0].fileno(), fcntl.LOCK_EX)
            acquired_fd = slot_files[0]

        # Write owner info for debugging.
        acquired_fd.seek(0)
        acquired_fd.truncate()
        acquired_fd.write(
            f"pid={os.getpid()} label={label} acquired_at={time.time():.3f}\n"
        )
        acquired_fd.flush()

        if on_acquired:
            on_acquired()

        yield

    finally:
        if acquired_fd is not None:
            fcntl.flock(acquired_fd.fileno(), fcntl.LOCK_UN)
        for fh in slot_files:
            fh.close()
