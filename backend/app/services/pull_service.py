"""GitHub pull requests for repositories opened from a GitHub URL (read-only).

`refs/pull/N/head` is fetched into a private ref, GitHub's public API supplies the
title/state/base (best effort), and the existing compare machinery builds the
PR-style view. Merged and closed PRs keep their own diff because the base commit
GitHub recorded is used rather than the base branch's current tip.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

from ..core import cache, git_runner, github_api
from ..core.errors import InvalidInput, NotFound
from ..core.git_runner import PR_REF_PREFIX, run_git
from ..core.security import parse_github_url
from ..schemas.git import Compare, FileDiff, PullMeta, PullRequest
from .git_service import (
    Repo, _diff_one_file, _short, build_compare, changed_files, get_branches,
)

_ctx: OrderedDict[tuple[str, int], Compare] = OrderedDict()
_ctx_lock = threading.Lock()
MAX_CONTEXTS = 64


def _owner_and_name(repo: Repo) -> tuple[str, str]:
    if not repo.remote_url:
        raise InvalidInput("Pull requests are only available for repositories opened from GitHub.")
    return parse_github_url(repo.remote_url)


def _commit_exists(repo: Repo, sha: str) -> bool:
    return run_git(repo.root, ["cat-file", "-e", f"{sha}^{{commit}}"], check=False).ok


def get_pull(repo: Repo, number: int) -> PullRequest:
    owner, name = _owner_and_name(repo)
    git_runner.fetch_pull_ref(repo.root, number)  # validates `number`; NotFound if no such PR
    cache.forget(repo.root)  # a new ref exists now
    head = run_git(
        repo.root, ["rev-parse", "--verify", "-q", f"{PR_REF_PREFIX}{number}^{{commit}}"], check=False
    )
    if not head.ok:
        raise NotFound(f"Pull request #{number} was not found.")
    head_sha = head.text().strip()

    raw = github_api.fetch_pull_meta(owner, name, number)
    base_sha = raw["base_sha"] if raw and raw["base_sha"] and _commit_exists(repo, raw["base_sha"]) else None
    base_label = raw["base_ref"] if raw and base_sha else None
    note = None
    if base_sha is None:
        branches = get_branches(repo)
        default = next((b for b in branches.branches if not b.is_remote and b.name == branches.default_branch), None)
        if default is None:
            raise InvalidInput("Could not determine which branch this pull request targets.")
        base_sha, base_label = default.sha, default.name
        note = ("GitHub details were unavailable (offline or rate-limited), so the pull request is "
                f"compared with {default.name}. Merged pull requests may look empty.") if raw is None else \
               f"Base commit not found locally; compared with {default.name}."

    mb = run_git(repo.root, ["merge-base", base_sha, head_sha], check=False)
    merge_base = mb.text().strip() or None if mb.ok else None
    compare = build_compare(repo, base_label or "base", f"#{number}", base_sha, head_sha, merge_base)

    with _ctx_lock:
        _ctx[(str(repo.root), number)] = compare
        _ctx.move_to_end((str(repo.root), number))
        while len(_ctx) > MAX_CONTEXTS:
            _ctx.popitem(last=False)

    state = (raw or {}).get("state") or "unknown"
    if raw and base_label and state in ("merged", "closed"):
        compare.note = (
            f"This pull request was {state}. Changes are measured from the base commit GitHub recorded, "
            "so the diff matches what was reviewed."
        )

    meta = PullMeta(
        number=number,
        title=(raw or {}).get("title") or f"Pull request #{number}",
        state=state,
        draft=bool((raw or {}).get("draft")),
        author=(raw or {}).get("author"),
        body=(raw or {}).get("body") or "",
        url=f"https://github.com/{owner}/{name}/pull/{number}",
        base_ref=(raw or {}).get("base_ref") or _short(base_label or ""),
        head_label=(raw or {}).get("head_label"),
        created_at=(raw or {}).get("created_at"),
        metadata_available=raw is not None,
        note=note,
    )
    return PullRequest(meta=meta, compare=compare)


def get_pull_diff(repo: Repo, number: int, path: str) -> FileDiff:
    _owner_and_name(repo)
    if not path or "\x00" in path or len(path) > 4096:
        raise InvalidInput("Invalid file path.")
    with _ctx_lock:
        compare = _ctx.get((str(repo.root), number))
    if compare is None:  # e.g. after a server restart: rebuild the context
        compare = get_pull(repo, number).compare
    files = changed_files(repo, compare.head_sha, compare.merge_base)
    return _diff_one_file(repo, compare.merge_base, compare.head_sha, files, path)
