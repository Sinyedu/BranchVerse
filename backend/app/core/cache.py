"""Small in-process result cache, invalidated whenever a repository's refs move.

Expensive read-only queries (analytics, strategy, timeline, branch comparisons)
are memoised per repository *state*. The state fingerprint is cheap (one tiny
Git call, reused for 2 seconds) and changes if any ref or HEAD changes, so stale data is never served.
"""

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Any, TypeVar

from .git_runner import run_git

T = TypeVar("T")
MAX_ENTRIES = 32

_lock = threading.Lock()
_store: OrderedDict[tuple, Any] = OrderedDict()


FP_TTL = 2.0  # seconds a fingerprint is trusted; avoids a subprocess on rapid repeat requests
_fp_seen: dict[str, tuple[float, str]] = {}


def _head_file(root) -> bytes:
    """The current-branch pointer, read directly (a tiny file) so it costs no subprocess."""
    try:
        with open(Path(root) / ".git" / "HEAD", "rb") as fh:
            return fh.read(4096)
    except OSError:
        return b""  # bare repositories and worktrees fall back to the ref list alone


def fingerprint(root) -> str:
    key = str(root)
    now = time.monotonic()
    seen = _fp_seen.get(key)
    if seen and now - seen[0] < FP_TTL:
        return seen[1]
    refs = run_git(root, ["show-ref", "--head"], check=False).stdout  # HEAD + every ref, one call
    h = hashlib.sha1(usedforsecurity=False)
    for part in (refs, _head_file(root)):
        h.update(part)
        h.update(b"\x00")
    fp = h.hexdigest()
    _fp_seen[key] = (now, fp)
    return fp


def cached(repo, name: str, factory: Callable[[], T], *extra: Hashable) -> T:
    key = (str(repo.root), name, extra, fingerprint(repo.root))
    with _lock:
        if key in _store:
            _store.move_to_end(key)
            return _store[key]
    value = factory()  # computed outside the lock: two racing misses just do the work twice
    with _lock:
        _store[key] = value
        _store.move_to_end(key)
        while len(_store) > MAX_ENTRIES:
            _store.popitem(last=False)
    return value


def forget(root) -> None:
    """Drop the remembered fingerprint so the next request re-checks the repository (e.g. on reopen)."""
    _fp_seen.pop(str(root), None)


def clear() -> None:
    with _lock:
        _store.clear()
        _fp_seen.clear()
