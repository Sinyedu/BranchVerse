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
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from .errors import (
    GitCommandError,
    GitOutputTooLarge,
    GitTimeout,
    GitUnavailable,
    InvalidInput,
)

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


def _clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(
        GIT_TERMINAL_PROMPT="0",
        GIT_OPTIONAL_LOCKS="0",
        GIT_PAGER="cat",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_ASKPASS="",
        LC_ALL="C",
    )
    return env


def build_command(repo: Path, args: list[str]) -> list[str]:
    if not args or args[0] not in READ_ONLY_SUBCOMMANDS:
        raise InvalidInput("Unsupported Git operation.")
    if any(not isinstance(a, str) or "\x00" in a for a in args):
        raise InvalidInput("Invalid Git argument.")
    return ["git", "-C", str(repo), *_BASE_FLAGS, *args]


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
            env=_clean_env(),
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
