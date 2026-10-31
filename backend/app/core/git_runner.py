"""The single choke point through which every Git subprocess runs.

Security rules enforced here, for every call:
  * argument arrays only, never a shell
  * allow-list of read-only Git subcommands
  * hooks, fsmonitor, external diff and pagers disabled
  * user/system/inherited GIT_* configuration ignored
  * no terminal prompts, no optional locks
  * literal pathspecs (no glob / magic interpretation)
  * wall-clock timeout and a hard cap on captured output
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .errors import (
    Busy,
    GitCommandError,
    GitOutputTooLarge,
    GitTimeout,
    GitUnavailable,
    InvalidInput,
)


# Repositories cloned from GitHub live under CACHE_ROOT. Only they may use the
# network (Git fetches missing file contents lazily from a blobless clone).
CACHE_ROOT = Path(
    os.environ.get("BRANCHVERSE_CACHE_DIR") or Path(tempfile.gettempdir()) / "branchverse-cache"
).resolve()
ALLOWED_REMOTE_PROTOCOL = "https"
CLONE_TIMEOUT = 180.0
MAX_CLONE_BYTES = 750 * 1024 * 1024
_clone_lock = threading.Lock()


def is_cached_repo(path: Path) -> bool:
    try:
        return Path(path).resolve().is_relative_to(CACHE_ROOT)
    except OSError:
        return False

READ_ONLY_SUBCOMMANDS = frozenset(
    {
        "log",
        "rev-list",
        "rev-parse",
        "show",
        "diff",
        "diff-tree",
        "ls-tree",
        "for-each-ref",
        "cat-file",
        "symbolic-ref",
        "merge-base",
    }
)

DEFAULT_TIMEOUT = 15.0
DEFAULT_MAX_BYTES = 8 * 1024 * 1024
_STDERR_LIMIT = 16 * 1024

_BASE_FLAGS = [
    "--no-pager",
    "--no-optional-locks",
    "--literal-pathspecs",
    "-c", "core.fsmonitor=false",
    "-c", f"core.hooksPath={os.devnull}",
    "-c", "diff.external=",
    "-c", "core.quotePath=true",
    "-c", "color.ui=never",
]


@dataclass
class GitResult:
    stdout: bytes
    returncode: int
    truncated: bool = False
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def text(self) -> str:
        return self.stdout.decode("utf-8", errors="replace")


def _clean_env(network: bool = False) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(
        GIT_TERMINAL_PROMPT="0",
        GIT_OPTIONAL_LOCKS="0",
        GIT_PAGER="cat",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_ASKPASS="",
        LC_ALL="C",
    )
    if not network:  # system config is only needed for TLS certificates
        env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _protocol_flags(network: bool) -> list[str]:
    flags = ["-c", "protocol.allow=never"]
    if network:
        flags += ["-c", f"protocol.{ALLOWED_REMOTE_PROTOCOL}.allow=always", "-c", "credential.helper="]
    return flags


def build_command(repo: Path, args: list[str]) -> list[str]:
    if not args or args[0] not in READ_ONLY_SUBCOMMANDS:
        raise InvalidInput("Unsupported Git operation.")
    if any(not isinstance(a, str) or "\x00" in a for a in args):
        raise InvalidInput("Invalid Git argument.")
    return ["git", "-C", str(repo), *_BASE_FLAGS, *_protocol_flags(is_cached_repo(repo)), *args]


def run_git(
    repo: Path,
    args: list[str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    truncate_ok: bool = False,
    check: bool = True,
) -> GitResult:
    cmd = build_command(repo, args)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.Popen(
            cmd,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_clean_env(is_cached_repo(repo)),
            creationflags=flags,
        )
    except FileNotFoundError as exc:
        raise GitUnavailable("The Git executable was not found on PATH.") from exc
    except OSError as exc:
        raise GitUnavailable("Git could not be started.") from exc

    timed_out = threading.Event()

    def _kill() -> None:
        timed_out.set()
        proc.kill()

    timer = threading.Timer(timeout, _kill)
    timer.start()

    stderr_buf = bytearray()

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        while chunk := proc.stderr.read(4096):
            if len(stderr_buf) < _STDERR_LIMIT:
                stderr_buf.extend(chunk)

    err_thread = threading.Thread(target=_drain_stderr, daemon=True)
    err_thread.start()

    chunks: list[bytes] = []
    total = 0
    truncated = False
    try:
        assert proc.stdout is not None
        while chunk := proc.stdout.read(65536):
            if total + len(chunk) > max_bytes:
                chunks.append(chunk[: max_bytes - total])
                truncated = True
                proc.kill()
                break
            chunks.append(chunk)
            total += len(chunk)
        proc.wait()
    finally:
        timer.cancel()
        err_thread.join(timeout=2)
        for stream in (proc.stdout, proc.stderr):
            if stream:
                stream.close()

    if timed_out.is_set():
        raise GitTimeout("Git took too long to respond and was stopped.")
    if truncated and not truncate_ok:
        raise GitOutputTooLarge("Git produced more output than BranchVerse will load.")

    stderr_text = stderr_buf.decode("utf-8", errors="replace").strip()
    result = GitResult(b"".join(chunks), proc.returncode, truncated, stderr_text)
    if check and not truncated and not result.ok:
        lines = stderr_text.splitlines()
        raise GitCommandError(lines[0][:300] if lines else "Git command failed.")
    return result


# ------------------------------------------------------------------- cloning


def _dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def remove_tree(path: Path) -> None:
    def _chmod_retry(func, p, _exc):  # read-only pack files on Windows
        os.chmod(p, 0o700)
        func(p)

    if Path(path).exists():
        shutil.rmtree(path, onexc=_chmod_retry)


def clone_bare(
    url: str,
    dest: Path,
    *,
    timeout: float = CLONE_TIMEOUT,
    max_bytes: int = MAX_CLONE_BYTES,
    poll: float = 1.0,
) -> None:
    """Blobless bare clone: all commits/trees/refs, no file contents.

    The only network-capable, state-creating Git call in BranchVerse. The caller
    must pass a URL it built itself from a validated GitHub owner/name. The
    protocol is restricted, hooks and credential helpers are off, and time and
    disk use are bounded.
    """
    dest = Path(dest)
    if not is_cached_repo(dest):
        raise InvalidInput("Clone destination must be inside the cache directory.")
    if not _clone_lock.acquire(blocking=False):
        raise Busy("Another repository is being downloaded. Try again in a moment.")
    try:
        cmd = [
            "git", "--no-pager",
            "-c", f"core.hooksPath={os.devnull}", "-c", "core.fsmonitor=false",
            *_protocol_flags(True),
            "clone", "--bare", "--filter=blob:none", "--quiet", "--", url, str(dest),
        ]
        try:
            proc = subprocess.Popen(
                cmd, shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, env=_clean_env(True),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            raise GitUnavailable("The Git executable was not found on PATH.") from exc
        err = bytearray()

        def _drain() -> None:
            assert proc.stderr is not None
            while chunk := proc.stderr.read(4096):
                if len(err) < _STDERR_LIMIT:
                    err.extend(chunk)

        reader = threading.Thread(target=_drain, daemon=True)
        reader.start()
        started = time.monotonic()
        failure: Exception | None = None
        while True:
            try:
                proc.wait(timeout=min(poll, timeout))
                break
            except subprocess.TimeoutExpired:
                pass
            if time.monotonic() - started > timeout:
                failure = GitTimeout("Downloading took too long and was stopped. Try a smaller repository.")
            elif dest.exists() and _dir_size(dest) > max_bytes:
                failure = GitOutputTooLarge("That repository is too large to download here.")
            if failure:
                proc.kill()
                proc.wait()
                break
        reader.join(timeout=2)
        if proc.stderr:
            proc.stderr.close()
        if failure:
            remove_tree(dest)
            raise failure
        if proc.returncode != 0:
            remove_tree(dest)
            raw = err.decode("utf-8", errors="replace")
            low = raw.lower()
            if any(k in low for k in ("not found", "could not read username", "authentication", "403", "404")):
                raise InvalidInput("Repository not found, or it is not public.")
            lines = raw.strip().splitlines()
            raise GitCommandError("Download failed: " + (lines[-1][:200] if lines else "unknown error"))
    finally:
        _clone_lock.release()


def prune_cache(max_age_hours: float = 24.0) -> int:
    """Delete downloaded GitHub copies older than the limit. Best effort; returns count removed."""
    parent = CACHE_ROOT / "github"
    removed = 0
    if not parent.is_dir():
        return 0
    cutoff = time.time() - max_age_hours * 3600
    for child in parent.iterdir():
        try:
            if child.is_dir() and child.stat().st_mtime < cutoff:
                remove_tree(child)
                removed += 1
        except OSError:
            continue
    return removed
