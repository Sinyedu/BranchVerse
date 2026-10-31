"""Repository analytics derived from real history, deduplicated by commit SHA."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from ..core.errors import InvalidInput
from ..core.git_runner import run_git
from ..schemas.git import Analytics, Contributor, WeekBucket
from .git_service import Repo

SCAN_LIMIT = 50_000
MAX_WEEKS = 104
_NUMSTAT = re.compile(r"^(\d+|-)\t(\d+|-)\t")


def _week_start(ts: int) -> datetime:
    d = datetime.fromtimestamp(ts, tz=timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return d - timedelta(days=d.weekday())


def _fill_weeks(buckets: dict[datetime, WeekBucket]) -> list[WeekBucket]:
    if not buckets:
        return []
    cur, last = min(buckets), max(buckets)
    out: list[WeekBucket] = []
    while cur <= last:
        out.append(buckets.get(cur) or WeekBucket(week_start=cur.date().isoformat()))
        cur += timedelta(days=7)
    return out[-MAX_WEEKS:]


def _bucket(buckets: dict[datetime, WeekBucket], ts: int) -> WeekBucket:
    key = _week_start(ts)
    if key not in buckets:
        buckets[key] = WeekBucket(week_start=key.date().isoformat())
    return buckets[key]


def get_analytics(repo: Repo, days: int = 180) -> Analytics:
    if not 1 <= days <= 730:
        raise InvalidInput("days must be between 1 and 730.")

    refs = run_git(repo.root, ["for-each-ref", "--format=%(refname)"]).text().splitlines()
    local = sum(r.startswith("refs/heads/") for r in refs)
    remote = sum(r.startswith("refs/remotes/") and not r.endswith("/HEAD") for r in refs)
    if not refs:
        return Analytics(
            total_commits=0, contributor_count=0, local_branches=0, remote_branches=0,
            first_commit=None, latest_commit=None, top_contributor=None, contributors=[],
            weekly_commits=[], weekly_changes=[], changes_days=days,
            scan_truncated=False, scan_limit=SCAN_LIMIT, scope_note="Repository has no commits.",
        )

    total = int(run_git(repo.root, ["rev-list", "--all", "--count"]).text().strip() or 0)

    scan = run_git(
        repo.root,
        ["log", "--all", "-z", f"--max-count={SCAN_LIMIT}", "--format=%an%x00%ae%x00%at"],
        max_bytes=32 * 1024 * 1024,
    ).text().split("\x00")
    if scan and scan[-1] == "":
        scan.pop()

    counts: Counter[str] = Counter()
    names: dict[str, str] = {}
    weeks: dict[datetime, WeekBucket] = {}
    stamps: list[int] = []
    for i in range(0, len(scan) - 2, 3):
        name, email, ts = scan[i], scan[i + 1], int(scan[i + 2] or 0)
        key = email.lower()
        counts[key] += 1
        names.setdefault(key, name)  # newest commit's display name wins
        stamps.append(ts)
        _bucket(weeks, ts).commits += 1

    contributors = [
        Contributor(name=names[k], email=k, commits=c) for k, c in counts.most_common()
    ]

    roots = run_git(
        repo.root, ["log", "--all", "--max-parents=0", "--format=%at"]
    ).text().split()
    first = min((int(x) for x in roots), default=None)

    # The window is anchored to the newest commit (not "today") so dormant
    # repositories still show their most recent activity.
    since = f"--max-age={max(stamps) - days * 86400}"
    raw = run_git(
        repo.root,
        ["log", "--all", "--no-merges", since, "--numstat", "--format=%x01%at"],
        max_bytes=16 * 1024 * 1024,
        truncate_ok=True,
        timeout=30,
    )
    change_weeks: dict[datetime, WeekBucket] = {}
    current: WeekBucket | None = None
    for line in raw.text().splitlines():
        if line.startswith("\x01"):
            current = _bucket(change_weeks, int(line[1:] or 0))
        elif current is not None and (m := _NUMSTAT.match(line)):
            if m.group(1) != "-":
                current.additions += int(m.group(1))
            if m.group(2) != "-":
                current.deletions += int(m.group(2))

    truncated = total > SCAN_LIMIT
    scope = f"All commits reachable from any branch or tag ({total:,} unique commits)."
    if truncated:
        scope += (
            f" Contributor and weekly figures cover the newest {SCAN_LIMIT:,} commits only."
        )
    scope += (
        f" Line changes cover the {days} days before the newest commit"
        " (merge commits excluded)."
    )
    if raw.truncated:
        scope += " Line-change totals were cut off because the output was very large."

    return Analytics(
        total_commits=total,
        contributor_count=len(counts),
        local_branches=local,
        remote_branches=remote,
        first_commit=first,
        latest_commit=max(stamps) if stamps else None,
        top_contributor=contributors[0] if contributors else None,
        contributors=contributors[:15],
        weekly_commits=_fill_weeks(weeks),
        weekly_changes=_fill_weeks(change_weeks),
        changes_days=days,
        scan_truncated=truncated,
        scan_limit=SCAN_LIMIT,
        scope_note=scope,
    )
