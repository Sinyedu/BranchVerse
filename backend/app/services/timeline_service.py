"""Git Time Machine: snapshots along HEAD's first-parent ancestry. Read-only."""

from __future__ import annotations

from ..core.cache import cached
from ..core.errors import GitOutputTooLarge, GitTimeout, InvalidInput
from ..core.git_runner import iter_git, run_git
from ..core.security import validate_sha
from ..schemas.git import PathChange, Snapshot, Timeline, TimelineCommit
from .git_service import Repo, changed_files, ensure_commit, head_sha

MAX_TIMELINE = 5000
MAX_LISTED = 200
MAX_FILES_LISTED = 3000
NOTE = "Snapshots along the current HEAD's first-parent history, oldest to newest."


def _first_parent_commits(repo: Repo) -> tuple[list[TimelineCommit], bool]:
    out = run_git(
        repo.root,
        [
            "log", "--first-parent", "-z", f"--max-count={MAX_TIMELINE + 1}",
            "--format=%H%x00%at%x00%an%x00%s", "HEAD",
        ],
    ).text().split("\x00")
    if out and out[-1] == "":
        out.pop()
    commits = [
        TimelineCommit(
            sha=out[i], short_sha=out[i][:7], timestamp=int(out[i + 1] or 0),
            author=out[i + 2], subject=out[i + 3],
        )
        for i in range(0, len(out) - 3, 4)
    ]
    truncated = len(commits) > MAX_TIMELINE
    return list(reversed(commits[:MAX_TIMELINE])), truncated


def _file_count_series(repo: Repo, commits: list[TimelineCommit]) -> None:
    """Fill file_count by accumulating Added/Deleted entries from the root forward."""
    try:
        raw = run_git(
            repo.root,
            [
                "log", "--first-parent", "--diff-merges=first-parent", "--no-renames",
                "--diff-filter=AD", "--name-status", "--format=%x01%H", "HEAD",
            ],
            max_bytes=16 * 1024 * 1024,
            timeout=30,
        ).text()
    except (GitOutputTooLarge, GitTimeout):
        return
    delta: dict[str, int] = {}
    sha = ""
    for line in raw.splitlines():
        if line.startswith("\x01"):
            sha = line[1:]
            delta.setdefault(sha, 0)
        elif line[:1] == "A":
            delta[sha] += 1
        elif line[:1] == "D":
            delta[sha] -= 1
    total = 0
    for c in commits:
        total += delta.get(c.sha, 0)
        c.file_count = total


def get_timeline(repo: Repo) -> Timeline:
    return cached(repo, "timeline", lambda: _compute_timeline(repo))


def _compute_timeline(repo: Repo) -> Timeline:
    if head_sha(repo) is None:
        return Timeline(commits=[], truncated=False, note="This repository has no commits on HEAD.")
    commits, truncated = _first_parent_commits(repo)
    if truncated:
        note = f"{NOTE} Only the newest {MAX_TIMELINE:,} snapshots are shown; file-count chart disabled."
    else:
        note = NOTE
        _file_count_series(repo, commits)
    return Timeline(commits=commits, truncated=truncated, note=note)


def _changes(files, status: str) -> list[PathChange]:
    return [PathChange(path=f.path, old_path=f.old_path) for f in files if f.status == status]


def get_snapshot(repo: Repo, sha: str) -> Snapshot:
    validate_sha(sha)
    ensure_commit(repo, sha)
    order = [c.sha for c in get_timeline(repo).commits]  # cached per repository state
    if sha not in order:
        raise InvalidInput("That commit is not on the current first-parent timeline.")
    idx = order.index(sha)
    previous = order[idx - 1] if idx > 0 else None

    names: list[str] = []
    file_count = 0
    for rec in iter_git(repo.root, ["ls-tree", "-r", "-z", "--name-only", sha], max_bytes=64 * 1024 * 1024):
        file_count += 1  # count everything, but keep only what the UI can show
        if len(names) < MAX_FILES_LISTED:
            names.append(rec.decode("utf-8", errors="replace"))

    files = changed_files(repo, sha, previous)
    added = _changes(files, "added")
    deleted = _changes(files, "deleted")
    modified = _changes(files, "modified")
    renamed = _changes(files, "renamed")
    return Snapshot(
        sha=sha,
        previous_sha=previous,
        file_count=file_count,
        files=names,
        files_truncated=file_count > MAX_FILES_LISTED,
        added=added[:MAX_LISTED],
        deleted=deleted[:MAX_LISTED],
        modified=modified[:MAX_LISTED],
        renamed=renamed[:MAX_LISTED],
        additions=sum(f.additions or 0 for f in files),
        deletions=sum(f.deletions or 0 for f in files),
        changes_truncated=max(len(added), len(deleted), len(modified), len(renamed)) > MAX_LISTED,
    )
