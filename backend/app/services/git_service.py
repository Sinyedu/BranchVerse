"""Read-only Git queries: repository, commits, files, diffs, branches."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from pathlib import Path

from ..core.errors import GitCommandError, InvalidInput, NotFound
from concurrent.futures import ThreadPoolExecutor

from ..core import git_runner
from ..core.cache import cached
from ..core.git_runner import run_git
from ..core.security import parse_github_url, validate_repo_path_input, validate_sha
from ..schemas.git import (
    Branch,
    BranchList,
    Commit,
    CommitDetails,
    CommitPage,
    Compare,
    Comparison,
    FileChange,
    FileDiff,
    Reachable,
    RefLabel,
    RepositoryInfo,
)

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
MAX_PAGE = 200
MAX_FILES = 500
MAX_DIFF_BYTES = 200 * 1024
MAX_REACHABLE = 20000
MAX_COMPARISONS = 150

_STATUS = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
}


@dataclass(frozen=True)
class Repo:
    root: Path
    is_bare: bool
    remote_url: str | None = None


# --------------------------------------------------------------------- open


def open_github(raw_url: str) -> Repo:
    """Download a public GitHub repository (blobless, bare) into the cache and open it."""
    owner, name = parse_github_url(raw_url)
    return _clone_and_open(f"https://github.com/{owner}/{name}.git", owner, name)


def _clone_and_open(clean_url: str, owner: str, name: str) -> Repo:
    parent = git_runner.CACHE_ROOT / "github"
    parent.mkdir(parents=True, exist_ok=True)
    prefix = f"{owner.lower()}__{name.lower()}__"
    dest = parent / f"{prefix}{secrets.token_hex(4)}"
    git_runner.clone_bare(clean_url, dest)
    try:
        repo = open_repository(str(dest))
    except Exception:
        git_runner.remove_tree(dest)
        raise
    for old in parent.glob(prefix + "*"):  # drop earlier downloads of the same repo
        if old != dest:
            try:
                git_runner.remove_tree(old)
            except OSError:
                pass
    return Repo(repo.root, True, remote_url=clean_url)


def open_repository(raw_path: str) -> Repo:
    text = validate_repo_path_input(raw_path)
    try:
        path = Path(text).expanduser().resolve(strict=True)
    except FileNotFoundError:
        raise InvalidInput("That path does not exist.") from None
    except PermissionError:
        raise InvalidInput("Permission denied for that path.") from None
    except OSError:
        raise InvalidInput("That path could not be read.") from None
    if not path.is_dir():
        raise InvalidInput("That path is not a directory.")

    probe = run_git(path, ["rev-parse", "--is-bare-repository"], check=False)
    if not probe.ok:
        if "dubious ownership" in probe.stderr:
            raise InvalidInput("Git refuses this repository (unsafe ownership).")
        raise InvalidInput("That directory is not a Git repository.")
    if probe.text().strip() == "true":
        return Repo(path, True)
    top = run_git(path, ["rev-parse", "--show-toplevel"], check=False)
    if not top.ok or not top.text().strip():
        raise InvalidInput("That directory is not inside a Git working tree.")
    return Repo(Path(top.text().strip()).resolve(), False)


def head_sha(repo: Repo) -> str | None:
    r = run_git(repo.root, ["rev-parse", "--verify", "-q", "HEAD"], check=False)
    return r.text().strip() or None if r.ok else None


def current_branch(repo: Repo) -> str | None:
    r = run_git(repo.root, ["symbolic-ref", "-q", "--short", "HEAD"], check=False)
    return r.text().strip() if r.ok and r.text().strip() else None


def repository_info(repo: Repo) -> RepositoryInfo:
    head = head_sha(repo)
    branch = current_branch(repo)
    name = repo.root.name
    if repo.is_bare and name.endswith(".git"):
        name = name[:-4]
    return RepositoryInfo(
        name=name,
        path=str(repo.root),
        is_bare=repo.is_bare,
        is_empty=head is None and not _any_refs(repo),
        is_detached=head is not None and branch is None,
        current_branch=branch,
        head_sha=head,
        remote_url=repo.remote_url,
    )


def _any_refs(repo: Repo) -> bool:
    r = run_git(repo.root, ["for-each-ref", "--count=1", "--format=%(refname)"])
    return bool(r.text().strip())


# ------------------------------------------------------------------ commits

_LOG_FORMAT = "%H%x00%P%x00%an%x00%ae%x00%at%x00%s%x00%D"
_LOG_FIELDS = 7


def _ref_kinds(repo: Repo) -> tuple[set[str], set[str]]:
    out = run_git(repo.root, ["for-each-ref", "--format=%(refname)"]).text()
    local, remote = set(), set()
    for line in out.splitlines():
        if line.startswith("refs/heads/"):
            local.add(line[len("refs/heads/"):])
        elif line.startswith("refs/remotes/"):
            remote.add(line[len("refs/remotes/"):])
    return local, remote


def _parse_decorations(raw: str, local: set[str], remote: set[str]) -> list[RefLabel]:
    labels: list[RefLabel] = []
    for token in (t for t in raw.split(", ") if t):
        if token.startswith("HEAD -> "):
            labels.append(RefLabel(name=token[8:], kind="head"))
        elif token == "HEAD":
            labels.append(RefLabel(name="HEAD", kind="head"))
        elif token.startswith("tag: "):
            labels.append(RefLabel(name=token[5:], kind="tag"))
        elif token in remote and token not in local:
            if not token.endswith("/HEAD"):
                labels.append(RefLabel(name=token, kind="remote"))
        else:
            labels.append(RefLabel(name=token, kind="branch"))
    return labels


def _to_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _read_commits(repo: Repo, log_args: list[str]) -> list[Commit]:
    out = run_git(
        repo.root, ["log", "-z", *log_args, f"--format={_LOG_FORMAT}"],
    ).text()
    tokens = out.split("\x00")
    if tokens and tokens[-1] == "":
        tokens.pop()
    local, remote = _ref_kinds(repo)
    commits: list[Commit] = []
    for i in range(0, len(tokens) - _LOG_FIELDS + 1, _LOG_FIELDS):
        sha, parents, name, email, ts, subject, deco = tokens[i : i + _LOG_FIELDS]
        sha = sha.lstrip("\n")
        commits.append(
            Commit(
                sha=sha,
                short_sha=sha[:7],
                parents=parents.split(),
                author=name,
                email=email,
                timestamp=_to_int(ts),
                subject=subject,
                refs=_parse_decorations(deco, local, remote),
            )
        )
    return commits


def get_commits(repo: Repo, limit: int, offset: int) -> CommitPage:
    if not 1 <= limit <= MAX_PAGE:
        raise InvalidInput(f"limit must be between 1 and {MAX_PAGE}.")
    if offset < 0:
        raise InvalidInput("offset must not be negative.")
    commits = _read_commits(
        repo, ["--all", "--topo-order", f"--skip={offset}", f"--max-count={limit + 1}"]
    )
    return CommitPage(
        commits=commits[:limit], offset=offset, has_more=len(commits) > limit
    )


def ensure_commit(repo: Repo, sha: str) -> str:
    validate_sha(sha)
    r = run_git(repo.root, ["cat-file", "-e", f"{sha}^{{commit}}"], check=False)
    if not r.ok:
        raise NotFound("No such commit in this repository.")
    return sha


# -------------------------------------------------------------------- files


def _parse_name_status(data: str) -> list[tuple[str, str, str | None]]:
    """-> [(status_letter, path, old_path)]"""
    tokens = data.split("\x00")
    out: list[tuple[str, str, str | None]] = []
    i = 0
    while i < len(tokens) and tokens[i]:
        status = tokens[i][0]
        if status in "RC" and i + 2 < len(tokens) + 0:
            out.append((status, tokens[i + 2], tokens[i + 1]))
            i += 3
        else:
            if i + 1 >= len(tokens):
                break
            out.append((status, tokens[i + 1], None))
            i += 2
    return out


def _parse_numstat(data: str) -> dict[str, tuple[int | None, int | None]]:
    tokens = data.split("\x00")
    out: dict[str, tuple[int | None, int | None]] = {}
    i = 0
    while i < len(tokens) and tokens[i]:
        parts = tokens[i].split("\t", 2)
        if len(parts) < 3:
            break
        add = None if parts[0] == "-" else _to_int(parts[0])
        dele = None if parts[1] == "-" else _to_int(parts[1])
        if parts[2] == "" and i + 2 < len(tokens):
            out[tokens[i + 2]] = (add, dele)
            i += 3
        else:
            out[parts[2]] = (add, dele)
            i += 1
    return out


def changed_files(repo: Repo, sha: str, base: str | None) -> list[FileChange]:
    """All files changed by `sha` relative to `base` (None = root commit)."""
    common = ["diff-tree", "-r", "-M", "-z", "--no-commit-id"]
    target = [base, sha] if base else ["--root", sha]
    ns = run_git(repo.root, [*common, "--name-status", *target]).text()
    num = run_git(repo.root, [*common, "--numstat", *target]).text()
    stats = _parse_numstat(num)
    files: list[FileChange] = []
    for status, path, old in _parse_name_status(ns):
        add, dele = stats.get(path, (None, None))
        binary = path in stats and add is None
        files.append(
            FileChange(
                path=path,
                old_path=old,
                status=_STATUS.get(status, "other"),
                additions=add,
                deletions=dele,
                binary=binary,
            )
        )
    return files


def get_commit_details(repo: Repo, sha: str) -> CommitDetails:
    ensure_commit(repo, sha)
    fmt = "%H%x00%P%x00%an%x00%ae%x00%at%x00%cn%x00%ce%x00%ct%x00%B"
    raw = run_git(repo.root, ["show", "-s", f"--format={fmt}", sha]).text()
    f = raw.split("\x00", 8)
    if len(f) < 9:
        raise GitCommandError("Could not parse commit.")
    parents = f[1].split()
    base = parents[0] if parents else None
    all_files = changed_files(repo, sha, base)
    if len(parents) > 1:
        note = "Merge commit: changes shown relative to the first parent."
    elif base is None:
        note = "Root commit: all files are shown as added."
    else:
        note = "Changes relative to the parent commit."
    return CommitDetails(
        sha=f[0],
        parents=parents,
        author=f[2],
        author_email=f[3],
        author_date=_to_int(f[4]),
        committer=f[5],
        committer_email=f[6],
        commit_date=_to_int(f[7]),
        message=f[8].rstrip("\n"),
        files=all_files[:MAX_FILES],
        files_truncated=len(all_files) > MAX_FILES,
        total_additions=sum(x.additions or 0 for x in all_files),
        total_deletions=sum(x.deletions or 0 for x in all_files),
        diff_base=base,
        diff_base_note=note,
    )


def get_file_diff(repo: Repo, sha: str, path: str) -> FileDiff:
    ensure_commit(repo, sha)
    if not path or "\x00" in path or len(path) > 4096:
        raise InvalidInput("Invalid file path.")
    parents = run_git(repo.root, ["show", "-s", "--format=%P", sha]).text().split()
    base = parents[0] if parents else None
    return _diff_one_file(repo, base, sha, changed_files(repo, sha, base), path)


def _diff_one_file(repo: Repo, base: str | None, sha: str, files: list[FileChange], path: str) -> FileDiff:
    """Diff `path` between base and sha. `path` must be one of the known changed files."""
    match = next((f for f in files if f.path == path), None)
    if match is None:
        raise NotFound("That file was not changed here.")
    if match.binary:
        return FileDiff(path=path, binary=True, diff="", truncated=False, diff_base=base)
    specs = [match.old_path, match.path] if match.old_path else [match.path]
    res = run_git(
        repo.root,
        [
            "diff", "--no-ext-diff", "--no-textconv", "--no-color", "-M",
            "--unified=3", base or EMPTY_TREE, sha, "--", *specs,
        ],
        max_bytes=MAX_DIFF_BYTES,
        truncate_ok=True,
    )
    return FileDiff(
        path=path, binary=False, diff=res.text(), truncated=res.truncated, diff_base=base
    )


# ----------------------------------------------------------------- branches

_REF_FORMAT = (
    "%(refname)%00%(objectname)%00%(committerdate:unix)%00"
    "%(upstream)%00%(HEAD)%00%(symref)"
)


def _short(full_ref: str) -> str:
    for prefix in ("refs/heads/", "refs/remotes/"):
        if full_ref.startswith(prefix):
            return full_ref[len(prefix):]
    return full_ref


def _left_right(repo: Repo, base: str, tip: str) -> tuple[int, int] | None:
    r = run_git(
        repo.root,
        ["rev-list", "--left-right", "--count", f"{base}...{tip}"],
        check=False,
    )
    parts = r.text().split()
    if not r.ok or len(parts) != 2:
        return None
    return int(parts[0]), int(parts[1])  # (behind, ahead) of tip vs base


def _default_ref(repo: Repo, heads: set[str], remotes: set[str]) -> str | None:
    if repo.is_bare:  # a bare clone's HEAD names the remote's default branch
        head = run_git(repo.root, ["symbolic-ref", "-q", "HEAD"], check=False)
        if head.ok and head.text().strip() in heads:
            return head.text().strip()
    r = run_git(repo.root, ["symbolic-ref", "-q", "refs/remotes/origin/HEAD"], check=False)
    target = r.text().strip()
    if r.ok and target in remotes:
        local = "refs/heads/" + target.rsplit("/", 1)[-1]
        return local if local in heads else target
    candidates = [h for h in ("refs/heads/main", "refs/heads/master") if h in heads]
    return candidates[0] if len(candidates) == 1 else None


def get_branches(repo: Repo) -> BranchList:
    return cached(repo, "branches", lambda: _compute_branches(repo))


_TRACK = re.compile(r"ahead (\d+)|behind (\d+)")


def _bulk_counts(repo, rows, plans, default):
    """(behind, ahead) for every branch from ONE `for-each-ref` (needs Git >= 2.41), else None."""
    if not any(plans):
        return [None] * len(rows)
    fmt = "%(refname)%00%(ahead-behind:{})%00%(upstream)%00%(upstream:track,nobracket)".format(
        default if default else "HEAD")
    r = run_git(repo.root, ["for-each-ref", f"--format={fmt}", "refs/heads", "refs/remotes"], check=False)
    if not r.ok:
        return None
    info = {}
    for line in r.text().splitlines():
        parts = line.split("\x00")
        if len(parts) == 4:
            info[parts[0]] = parts
    out = []
    for (ref, *_), plan in zip(rows, plans):
        got = info.get(ref)
        if plan is None or got is None:
            out.append(None)
        elif plan[0] == "default":
            nums = got[1].split()
            out.append((int(nums[1]), int(nums[0])) if len(nums) == 2 else None)
        else:  # upstream: Git's own tracking summary; empty means in sync, [gone] means missing
            track = got[3]
            if track == "gone":
                out.append(None)
            else:
                a = b = 0
                for m in _TRACK.finditer(track):
                    a += int(m.group(1) or 0)
                    b += int(m.group(2) or 0)
                out.append((b, a))
    return out


def _compute_branches(repo: Repo) -> BranchList:
    out = run_git(
        repo.root,
        ["for-each-ref", f"--format={_REF_FORMAT}", "refs/heads", "refs/remotes"],
    ).text()
    rows = []
    for line in out.splitlines():
        f = line.split("\x00")
        if len(f) == 6 and not f[5]:  # skip symbolic refs such as origin/HEAD
            rows.append(f)
    heads = {r[0] for r in rows if r[0].startswith("refs/heads/")}
    remotes = {r[0] for r in rows if r[0].startswith("refs/remotes/")}
    default = _default_ref(repo, heads, remotes)

    # Plan: which base (if any) each branch is compared with.
    plans: list[tuple[str, str] | None] = []
    for n, (ref, _sha, _date, upstream, _head, _sym) in enumerate(rows):
        is_remote = ref.startswith("refs/remotes/")
        if n >= MAX_COMPARISONS:
            plans.append(None)
        elif upstream and not is_remote:
            plans.append(("upstream", upstream))
        elif default and ref != default:
            plans.append(("default", default))
        else:
            plans.append(None)

    counts_all = _bulk_counts(repo, rows, plans, default)
    if counts_all is None:  # older Git: independent read-only subprocesses, run in parallel
        def run(item):
            (ref, *_), plan = item
            return _left_right(repo, plan[1], ref) if plan else None

        with ThreadPoolExecutor(max_workers=8) as pool:
            counts_all = list(pool.map(run, zip(rows, plans)))

    branches: list[Branch] = []
    for n, ((ref, sha, date, _up, head_mark, _), plan, counts) in enumerate(zip(rows, plans, counts_all)):
        is_remote = ref.startswith("refs/remotes/")
        comp = Comparison(kind="none", base=None, ahead=None, behind=None,
                          note="No upstream or default branch to compare with.")
        if n >= MAX_COMPARISONS:
            comp.note = "Comparison skipped: too many branches."
        elif plan and plan[0] == "upstream":
            comp = Comparison(
                kind="upstream", base=_short(plan[1]),
                behind=counts[0] if counts else None,
                ahead=counts[1] if counts else None,
                note=None if counts else "Upstream branch no longer exists.",
            )
        elif plan and counts:
            comp = Comparison(
                kind="default", base=_short(plan[1]), behind=counts[0], ahead=counts[1],
                note="Compared with the default branch (no upstream).",
            )
        branches.append(
            Branch(
                name=_short(ref), full_ref=ref, is_remote=is_remote,
                is_current=head_mark == "*", sha=sha,
                last_commit_date=_to_int(date), comparison=comp,
            )
        )
    branches.sort(key=lambda b: (b.is_remote, -b.last_commit_date))
    return BranchList(branches=branches, default_branch=_short(default) if default else None)


def get_reachable(repo: Repo, full_ref: str) -> Reachable:
    known = {
        line
        for line in run_git(
            repo.root, ["for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"]
        ).text().splitlines()
    }
    if full_ref not in known:
        raise NotFound("Unknown branch.")
    out = run_git(
        repo.root, ["rev-list", f"--max-count={MAX_REACHABLE + 1}", full_ref]
    ).text().split()
    return Reachable(
        full_ref=full_ref, shas=out[:MAX_REACHABLE], truncated=len(out) > MAX_REACHABLE
    )


# ------------------------------------------------------------------ compare

MAX_COMPARE_COMMITS = 100


def _branch_tips(repo: Repo) -> dict[str, str]:
    out = run_git(
        repo.root,
        ["for-each-ref", "--format=%(refname)%00%(objectname)", "refs/heads", "refs/remotes"],
    ).text()
    tips = {}
    for line in out.splitlines():
        ref, _, sha = line.partition("\x00")
        if sha:
            tips[ref] = sha
    return tips


def _resolve_compare(repo: Repo, base_ref: str, head_ref: str):
    tips = _branch_tips(repo)  # refs must come from the repository's own branch list
    if base_ref not in tips or head_ref not in tips:
        raise NotFound("Unknown branch.")
    base_sha, head_sha = tips[base_ref], tips[head_ref]
    mb = run_git(repo.root, ["merge-base", base_sha, head_sha], check=False)
    return base_sha, head_sha, (mb.text().strip() or None) if mb.ok else None


def get_compare(repo: Repo, base_ref: str, head_ref: str) -> Compare:
    base_sha, head_sha, merge_base = _resolve_compare(repo, base_ref, head_ref)
    return build_compare(repo, _short(base_ref), _short(head_ref), base_sha, head_sha, merge_base)


def build_compare(
    repo: Repo, base: str, head: str, base_sha: str, head_sha: str, merge_base: str | None
) -> Compare:
    counts = _left_right(repo, base_sha, head_sha) or (0, 0)
    commits = _read_commits(
        repo,
        ["--topo-order", f"--max-count={MAX_COMPARE_COMMITS + 1}", f"{base_sha}..{head_sha}"],
    )
    files = changed_files(repo, head_sha, merge_base)
    if merge_base is None:
        note = "These branches share no history, so every file on the compare branch is shown as added."
    elif counts[1] == 0:
        note = "The compare branch has no commits of its own: it is already contained in the base branch."
    elif counts[0] == 0:
        note = "Can be fast-forwarded: the base branch has no commits that the compare branch lacks."
    else:
        note = ("Changes are measured from the merge base, as a pull request does, so "
                "work added to the base branch since the split is not counted.")
    return Compare(
        base=base, head=head, base_sha=base_sha, head_sha=head_sha,
        merge_base=merge_base, ahead=counts[1], behind=counts[0],
        commits=commits[:MAX_COMPARE_COMMITS], commits_truncated=len(commits) > MAX_COMPARE_COMMITS,
        files=files[:MAX_FILES], files_truncated=len(files) > MAX_FILES,
        total_additions=sum(f.additions or 0 for f in files),
        total_deletions=sum(f.deletions or 0 for f in files),
        note=note,
    )


def get_compare_file_diff(repo: Repo, base_ref: str, head_ref: str, path: str) -> FileDiff:
    if not path or "\x00" in path or len(path) > 4096:
        raise InvalidInput("Invalid file path.")
    _, head_sha, merge_base = _resolve_compare(repo, base_ref, head_ref)
    return _diff_one_file(repo, merge_base, head_sha, changed_files(repo, head_sha, merge_base), path)
