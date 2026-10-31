import pytest

from app.core.errors import InvalidInput, NotFound
from app.services import analytics_service, git_service, timeline_service

from .conftest import git


def sha_of(demo, subject):
    page = git_service.get_commits(demo, 200, 0)
    return next(c for c in page.commits if c.subject == subject)


# ------------------------------------------------------------- repositories


def test_open_valid_repo_with_spaces_in_path(demo_path):
    assert " " in str(demo_path)
    repo = git_service.open_repository(str(demo_path))
    info = git_service.repository_info(repo)
    assert info.name == "demo repo"
    assert info.current_branch == "main"
    assert not info.is_empty and not info.is_detached


def test_open_from_subdirectory_resolves_root(demo_path):
    repo = git_service.open_repository(str(demo_path / "src"))
    assert repo.root == demo_path.resolve()


@pytest.mark.parametrize("bad", ["", "   ", "\x00abc", "x" * 5000])
def test_open_rejects_malformed_input(bad):
    with pytest.raises(InvalidInput):
        git_service.open_repository(bad)


def test_open_rejects_missing_and_non_git(tmp_path):
    with pytest.raises(InvalidInput, match="does not exist"):
        git_service.open_repository(str(tmp_path / "nope"))
    with pytest.raises(InvalidInput, match="not a Git"):
        git_service.open_repository(str(tmp_path))
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(InvalidInput, match="not a directory"):
        git_service.open_repository(str(f))


def test_empty_repository(empty_repo):
    repo = git_service.open_repository(str(empty_repo))
    info = git_service.repository_info(repo)
    assert info.is_empty and info.head_sha is None
    assert git_service.get_commits(repo, 100, 0).commits == []
    assert timeline_service.get_timeline(repo).commits == []
    assert analytics_service.get_analytics(repo).total_commits == 0


def test_detached_head(tmp_path, demo_path):
    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(demo_path), str(clone))
    git(clone, "checkout", "-q", "--detach", "HEAD~1")
    info = git_service.repository_info(git_service.open_repository(str(clone)))
    assert info.is_detached and info.current_branch is None and info.head_sha


# ------------------------------------------------------------------ commits


def test_commit_listing_and_metadata(demo):
    page = git_service.get_commits(demo, 200, 0)
    assert len(page.commits) == 14 and not page.has_more
    root = page.commits[-1]
    assert root.subject == "Initial commit" and root.parents == []
    assert (root.author, root.email) == ("Alice Andersen", "alice@example.com")
    assert root.short_sha == root.sha[:7]


def test_pagination(demo):
    first = git_service.get_commits(demo, 5, 0)
    second = git_service.get_commits(demo, 5, 5)
    assert first.has_more and len(first.commits) == 5
    assert not {c.sha for c in first.commits} & {c.sha for c in second.commits}
    with pytest.raises(InvalidInput):
        git_service.get_commits(demo, 0, 0)
    with pytest.raises(InvalidInput):
        git_service.get_commits(demo, 1000, 0)


def test_topological_order_parents_after_children(demo):
    commits = git_service.get_commits(demo, 200, 0).commits
    index = {c.sha: i for i, c in enumerate(commits)}
    for c in commits:
        for p in c.parents:
            assert index[p] > index[c.sha]


def test_merge_commit_has_two_parents(demo):
    merges = [c for c in git_service.get_commits(demo, 200, 0).commits if len(c.parents) == 2]
    assert {m.subject for m in merges} == {
        "Merge branch 'feature/login'", "Merge branch 'feature/search'"}


def test_ref_labels(demo):
    commits = git_service.get_commits(demo, 200, 0).commits
    labels = {(r.kind, r.name) for c in commits for r in c.refs}
    assert ("head", "main") in labels and ("tag", "v0.1.0") in labels
    assert ("branch", "fix/typo") in labels and ("branch", "feature/login") in labels


# ------------------------------------------------------------------ details


def test_root_commit_details(demo):
    d = git_service.get_commit_details(demo, sha_of(demo, "Initial commit").sha)
    assert d.diff_base is None and "Root" in d.diff_base_note
    assert {f.path for f in d.files} == {"README.md", "src/app.py"}
    assert all(f.status == "added" for f in d.files)
    assert d.total_additions > 0 and d.total_deletions == 0


def test_merge_details_use_first_parent(demo):
    merge = sha_of(demo, "Merge branch 'feature/login'")
    d = git_service.get_commit_details(demo, merge.sha)
    assert d.diff_base == merge.parents[0] and "first parent" in d.diff_base_note
    assert {f.path for f in d.files} == {"src/login.py", "src/auth.py"}


def test_added_modified_deleted_statuses(demo):
    d = git_service.get_commit_details(demo, sha_of(demo, "Replace utils with config, drop old guide").sha)
    by_path = {f.path: f.status for f in d.files}
    assert by_path == {"src/utils.py": "deleted", "docs/guide.md": "deleted", "src/config.py": "added"}
    m = git_service.get_commit_details(demo, sha_of(demo, "Greet by name").sha)
    assert m.files[0].status == "modified" and m.files[0].additions and m.files[0].deletions


def test_file_diff(demo):
    sha = sha_of(demo, "Greet by name").sha
    diff = git_service.get_file_diff(demo, sha, "src/app.py")
    assert "+def main(name='world')" in diff.diff and not diff.binary and not diff.truncated


def test_diff_rejects_unchanged_or_hostile_paths(demo):
    sha = sha_of(demo, "Greet by name").sha
    for path in ["README.md", "--output=evil", "../../etc/passwd", ":(top)*", "*"]:
        with pytest.raises(NotFound):
            git_service.get_file_diff(demo, sha, path)
    with pytest.raises(InvalidInput):
        git_service.get_file_diff(demo, sha, "a\x00b")


def test_invalid_and_unknown_shas(demo):
    for bad in ["HEAD", "main", "HEAD~1", "--all", "abc", "G" * 40, "A" * 40, "0" * 39, "$(id)"]:
        with pytest.raises(InvalidInput):
            git_service.get_commit_details(demo, bad)
    with pytest.raises(NotFound):
        git_service.get_commit_details(demo, "0" * 40)


def test_binary_and_large_diffs(tmp_path):
    repo_path = tmp_path / "bin"
    repo_path.mkdir()
    git(repo_path, "init", "-q", "-b", "main")
    (repo_path / "blob.bin").write_bytes(bytes(range(256)) * 4)
    (repo_path / "big.txt").write_text("line\n" * 100_000)
    git(repo_path, "add", "-A")
    git(repo_path, "-c", "user.name=T", "-c", "user.email=t@e.x", "commit", "-q", "-m", "x")
    repo = git_service.open_repository(str(repo_path))
    sha = git_service.get_commits(repo, 10, 0).commits[0].sha
    d = git_service.get_commit_details(repo, sha)
    assert next(f for f in d.files if f.path == "blob.bin").binary
    assert git_service.get_file_diff(repo, sha, "blob.bin").binary
    big = git_service.get_file_diff(repo, sha, "big.txt")
    assert big.truncated and len(big.diff.encode()) <= git_service.MAX_DIFF_BYTES


def test_unusual_filenames(tmp_path):
    repo_path = tmp_path / "odd"
    repo_path.mkdir()
    git(repo_path, "init", "-q", "-b", "main")
    names = ["sp ace.txt", "ünï.txt", "-dash.txt", "tab\there.txt"]
    for n in names:
        try:
            (repo_path / n).write_text("hi\n")
        except OSError:
            names.remove(n)
    git(repo_path, "add", "-A")
    git(repo_path, "-c", "user.name=T", "-c", "user.email=t@e.x", "commit", "-q", "-m", "x")
    repo = git_service.open_repository(str(repo_path))
    sha = git_service.get_commits(repo, 10, 0).commits[0].sha
    files = git_service.get_commit_details(repo, sha).files
    assert {f.path for f in files} >= {"sp ace.txt", "-dash.txt"}
    assert "+hi" in git_service.get_file_diff(repo, sha, "-dash.txt").diff


# ----------------------------------------------------------------- branches


def test_branch_discovery_and_comparisons(demo):
    result = git_service.get_branches(demo)
    names = {b.name: b for b in result.branches}
    assert set(names) == {"main", "fix/typo", "feature/login", "feature/search"}
    assert names["main"].is_current and result.default_branch == "main"
    typo = names["fix/typo"].comparison
    assert (typo.kind, typo.base, typo.ahead, typo.behind) == ("default", "main", 1, 0)
    assert names["main"].comparison.kind == "none"


def test_upstream_comparison_on_clone(tmp_path, demo_path):
    clone = tmp_path / "c"
    git(tmp_path, "clone", "-q", str(demo_path), str(clone))
    git(clone, "reset", "-q", "--hard", "HEAD~1")
    result = git_service.get_branches(git_service.open_repository(str(clone)))
    main = next(b for b in result.branches if b.name == "main")
    assert (main.comparison.kind, main.comparison.base) == ("upstream", "origin/main")
    assert main.comparison.behind == 1 and main.comparison.ahead == 0
    assert any(b.is_remote for b in result.branches)
    assert all(not b.name.endswith("/HEAD") for b in result.branches)


def test_reachable_validates_ref(demo):
    r = git_service.get_reachable(demo, "refs/heads/feature/search")
    assert len(r.shas) == 6 and not r.truncated
    for bad in ["HEAD", "main", "--all", "refs/heads/nope", "refs/tags/v0.1.0"]:
        with pytest.raises(NotFound):
            git_service.get_reachable(demo, bad)


# -------------------------------------------------------- timeline/analytics


def test_timeline_is_first_parent_chronological(demo):
    t = timeline_service.get_timeline(demo)
    subjects = [c.subject for c in t.commits]
    assert subjects[0] == "Initial commit" and subjects[-1] == "Update README"
    assert "Add login module" not in subjects  # side-branch commit is excluded
    assert "Merge branch 'feature/login'" in subjects
    assert [c.timestamp for c in t.commits] == sorted(c.timestamp for c in t.commits)


def test_timeline_file_counts_match_ls_tree(demo):
    t = timeline_service.get_timeline(demo)
    for c in t.commits:
        actual = len(git(demo.root, "ls-tree", "-r", "--name-only", c.sha).splitlines())
        assert c.file_count == actual, c.subject


def test_snapshot(demo):
    t = timeline_service.get_timeline(demo)
    sha = next(c.sha for c in t.commits if c.subject.startswith("Replace utils"))
    s = timeline_service.get_snapshot(demo, sha)
    assert [p.path for p in s.deleted] == ["docs/guide.md", "src/utils.py"] or {
        p.path for p in s.deleted} == {"docs/guide.md", "src/utils.py"}
    assert [p.path for p in s.added] == ["src/config.py"]
    assert s.file_count == len(s.files) and "src/utils.py" not in s.files
    first = timeline_service.get_snapshot(demo, t.commits[0].sha)
    assert first.previous_sha is None and first.file_count == 2


def test_snapshot_rejects_side_branch_and_bad_input(demo):
    side = sha_of(demo, "Add login module").sha
    with pytest.raises(InvalidInput):
        timeline_service.get_snapshot(demo, side)
    with pytest.raises(InvalidInput):
        timeline_service.get_snapshot(demo, "HEAD")


def test_analytics_dedupes_commits(demo):
    a = analytics_service.get_analytics(demo, days=730)
    assert a.total_commits == 14
    assert sum(w.commits for w in a.weekly_commits) == 14
    assert a.contributor_count == 3 and a.local_branches == 4 and a.remote_branches == 0
    assert sum(c.commits for c in a.contributors) == 14
    assert a.top_contributor.name == "Alice Andersen"
    assert a.first_commit < a.latest_commit
    with pytest.raises(InvalidInput):
        analytics_service.get_analytics(demo, days=0)


def test_analytics_line_changes_match_git(demo):
    a = analytics_service.get_analytics(demo, days=730)
    out = git(demo.root, "log", "--all", "--no-merges", "--numstat", "--format=")
    adds = sum(int(l.split("\t")[0]) for l in out.splitlines() if l and l.split("\t")[0] != "-")
    assert sum(w.additions for w in a.weekly_changes) == adds


def test_strategy_on_demo(demo):
    from app.services import strategy_service
    s = strategy_service.get_strategy(demo)
    assert s.default_branch == "main" and s.style == "feature-branch"
    assert s.merged_branches == ["feature/login", "feature/search"]
    assert s.unmerged_branches == ["fix/typo"]
    assert {p.prefix: p.count for p in s.prefixes} == {"feature": 2, "fix": 1}
    merge_ev = next(e for e in s.evidence if e.label.startswith("Merge commits"))
    assert merge_ev.value.startswith("2 of 8")


def test_strategy_empty_repo_is_unclear(empty_repo):
    from app.services import strategy_service
    s = strategy_service.get_strategy(git_service.open_repository(str(empty_repo)))
    assert s.style == "unclear" and s.default_branch is None
