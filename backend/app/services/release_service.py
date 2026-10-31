"""Release timeline: what happened between consecutive tags. Read-only."""

from __future__ import annotations

from ..core.cache import cached
from ..core.errors import GitOutputTooLarge, GitTimeout
from ..core.git_runner import run_git
from ..schemas.git import Release, ReleaseTimeline
from .git_service import Repo

MAX_RELEASES = 100
MAX_RANGE_COMMITS = 50_000
SEP = "\x1f"
NOTE = (
    "Tags that point at commits, oldest to newest by tag date. Each release counts the commits "
    "reachable from it but not from the tag before it, so tags on different branches can overlap."
)


def get_releases(repo: Repo) -> ReleaseTimeline:
    return cached(repo, "releases", lambda: _compute_releases(repo))


def _list_tags(repo: Repo) -> list[Release]:
    fmt = SEP.join([
        "%(refname:short)", "%(objectname)", "%(objecttype)", "%(*objectname)", "%(*objecttype)",
        "%(creatordate:unix)", "%(contents:subject)",
    ])
    out = run_git(repo.root, ["for-each-ref", f"--format={fmt}", "refs/tags"]).text()
    tags: list[Release] = []
    for line in out.splitlines():
        parts = line.split(SEP)
        if len(parts) != 7:
            continue
        name, oid, otype, peeled, ptype, stamp, subject = parts
        annotated = otype == "tag"
        sha, kind = (peeled, ptype) if annotated else (oid, otype)
        if kind != "commit" or len(sha) != 40:  # tags of trees/blobs/nested tags are not releases
            continue
        tags.append(Release(
            name=name, sha=sha, short_sha=sha[:7], timestamp=int(stamp or 0), annotated=annotated,
            message=subject.strip() or None if annotated else None,
        ))
    tags.sort(key=lambda t: (t.timestamp, t.name))
    return tags


def _range_stats(repo: Repo, base: str | None, sha: str) -> tuple[int, int] | None:
    """(commit count, distinct authors) for commits reachable from `sha` but not `base`."""
    args = ["log", f"--max-count={MAX_RANGE_COMMITS}", "--format=%aN", sha]
    if base:
        args.append(f"^{base}")  # both operands are 40-hex SHAs that Git itself reported
    try:
        names = run_git(repo.root, args, timeout=20, max_bytes=8 * 1024 * 1024).text().splitlines()
    except (GitOutputTooLarge, GitTimeout):
        return None
    return len(names), len(set(names))


def _compute_releases(repo: Repo) -> ReleaseTimeline:
    tags = _list_tags(repo)
    total = len(tags)
    truncated = total > MAX_RELEASES
    shown = tags[-MAX_RELEASES:]
    previous = tags[-MAX_RELEASES - 1] if truncated else None
    for i, rel in enumerate(shown):
        before = shown[i - 1] if i else previous
        if before:
            rel.previous = before.name
            rel.days_since_previous = round(max(rel.timestamp - before.timestamp, 0) / 86400, 1)
        stats = _range_stats(repo, before.sha if before else None, rel.sha)
        if stats:
            rel.commits, rel.contributors = stats
    note = NOTE if total else "This repository has no tags yet."
    if truncated:
        note += f" Only the newest {MAX_RELEASES} of {total} tags are shown."
    return ReleaseTimeline(releases=shown, total_tags=total, truncated=truncated, note=note)
