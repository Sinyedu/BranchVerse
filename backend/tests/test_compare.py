import pytest

from app.core.errors import InvalidInput, NotFound
from app.services import git_service

MAIN, LOGIN, SEARCH, TYPO = (f"refs/heads/{n}" for n in ("main", "feature/login", "feature/search", "fix/typo"))


def test_unmerged_branch_compares_like_a_pull_request(demo):
    c = git_service.get_compare(demo, MAIN, TYPO)
    assert (c.base, c.head) == ("main", "fix/typo")
    assert (c.ahead, c.behind) == (1, 0)
    assert [x.subject for x in c.commits] == ["Fix typo in README"]
    assert [f.path for f in c.files] == ["README.md"] and c.files[0].status == "modified"
    assert c.merge_base and "fast-forward" in c.note
    assert c.total_additions == 2 and c.total_deletions == 0


def test_diverged_branches_count_only_their_own_work(demo):
    # login and search each forked from main at different points and both were merged later.
    c = git_service.get_compare(demo, LOGIN, SEARCH)
    assert (c.ahead, c.behind) == (3, 3)
    assert {x.subject for x in c.commits} == {
        "Greet by name", "Add search module", "Make search case-insensitive"}
    assert "merge base" in c.note and c.merge_base not in (c.base_sha, c.head_sha)
    merged = git_service.get_compare(demo, MAIN, SEARCH)
    assert merged.ahead == 0 and "already contained" in merged.note


def test_three_dot_semantics_ignore_base_only_changes(demo):
    c = git_service.get_compare(demo, LOGIN, MAIN)
    paths = {f.path for f in c.files}
    # main's own changes since the split appear; login's later salted-hash commit does not.
    assert "src/search.py" in paths and "src/config.py" in paths
    assert not any(f.path == "src/auth.py" and f.status == "modified" and f.additions == 4 for f in c.files)


def test_compare_file_diff(demo):
    d = git_service.get_compare_file_diff(demo, MAIN, TYPO, "README.md")
    assert "+Thanks!" in d.diff and not d.binary


def test_compare_rejects_unknown_or_hostile_refs(demo):
    for bad in ["main", "HEAD", "--all", "refs/tags/v0.1.0", "refs/heads/nope", "refs/heads/main..HEAD", ""]:
        with pytest.raises(NotFound):
            git_service.get_compare(demo, bad, TYPO)
        with pytest.raises(NotFound):
            git_service.get_compare(demo, MAIN, bad)


def test_compare_diff_requires_a_file_in_the_comparison(demo):
    for path in ["src/app.py", "--output=x", "../x", "*"]:
        with pytest.raises(NotFound):
            git_service.get_compare_file_diff(demo, MAIN, TYPO, path)
    with pytest.raises(InvalidInput):
        git_service.get_compare_file_diff(demo, MAIN, TYPO, "a\x00b")


def test_same_branch_compare_is_empty(demo):
    c = git_service.get_compare(demo, MAIN, MAIN)
    assert c.ahead == 0 and c.behind == 0 and c.commits == [] and c.files == []


def test_compare_http(open_client):
    r = open_client.get("/api/compare", params={"base": MAIN, "head": TYPO})
    assert r.status_code == 200 and r.json()["ahead"] == 1
    r = open_client.get("/api/compare/diff", params={"base": MAIN, "head": TYPO, "path": "README.md"})
    assert r.status_code == 200 and "+Thanks!" in r.json()["diff"]
    assert open_client.get("/api/compare", params={"base": "HEAD", "head": TYPO}).status_code == 404
    assert open_client.get("/api/compare", params={"base": MAIN}).status_code == 422
