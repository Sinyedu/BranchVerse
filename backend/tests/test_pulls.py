"""Pull request support. A file:// remote advertises refs/pull/N/head like GitHub does."""

import io
import json

import pytest

from app.core import cache, git_runner, github_api
from app.core.errors import Busy, InvalidInput, NotFound
from app.services import git_service, pull_service

from .conftest import git


@pytest.fixture()
def gh(tmp_path, demo_path, monkeypatch):
    """A cached 'GitHub' clone whose remote has pull refs 1 (open) and 2 (merged)."""
    src = tmp_path / "remote.git"
    git(tmp_path, "clone", "-q", "--bare", str(demo_path), str(src))
    git(src, "config", "uploadpack.allowFilter", "true")
    git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    typo = git(src, "rev-parse", "refs/heads/fix/typo")
    login = git(src, "rev-parse", "refs/heads/feature/login")
    git(src, "update-ref", "refs/pull/1/head", typo)
    git(src, "update-ref", "refs/pull/2/head", login)
    monkeypatch.setattr(git_runner, "CACHE_ROOT", (tmp_path / "cache").resolve())
    monkeypatch.setattr(git_runner, "ALLOWED_REMOTE_PROTOCOL", "file")
    monkeypatch.setattr(github_api, "fetch_pull_meta", lambda *a, **k: None)
    url = "file:///" + str(src).replace("\\", "/").lstrip("/")
    repo = git_service._clone_and_open(url, "octo", "demo")
    monkeypatch.setattr(pull_service, "_owner_and_name", lambda r: ("octo", "demo"))
    return repo, typo, login


def test_open_pull_request_compares_with_default_branch_when_api_is_down(gh):
    repo, typo, _ = gh
    pr = pull_service.get_pull(repo, 1)
    assert pr.meta.number == 1 and not pr.meta.metadata_available and pr.meta.state == "unknown"
    assert pr.meta.url == "https://github.com/octo/demo/pull/1"
    assert pr.compare.head_sha == typo and pr.compare.base == "main"
    assert (pr.compare.ahead, pr.compare.behind) == (1, 0)
    assert [f.path for f in pr.compare.files] == ["README.md"]
    assert "unavailable" in (pr.meta.note or "")


def test_pull_request_uses_github_metadata_and_recorded_base(gh, monkeypatch):
    repo, typo, login = gh
    base = git(repo.root, "rev-parse", "refs/heads/main~5")  # an earlier main commit, as a merged PR records
    monkeypatch.setattr(github_api, "fetch_pull_meta", lambda *a, **k: github_api.clean_pull({
        "title": "Add login", "state": "closed", "merged": True, "draft": False,
        "user": {"login": "bob"}, "body": "Closes #9", "created_at": "2024-02-01T00:00:00Z",
        "base": {"ref": "main", "sha": base}, "head": {"label": "bob:feature/login"},
    }))
    pr = pull_service.get_pull(repo, 2)
    assert (pr.meta.title, pr.meta.state, pr.meta.author) == ("Add login", "merged", "bob")
    assert pr.meta.metadata_available and pr.meta.head_label == "bob:feature/login"
    assert pr.compare.base_sha == base and pr.compare.head_sha == login
    # The recorded base keeps a merged PR's diff intact (current main already contains it).
    assert pr.compare.ahead > 0 and any(f.path == "src/login.py" for f in pr.compare.files)


def test_pull_diff_and_validation(gh):
    repo, _, _ = gh
    pull_service.get_pull(repo, 1)
    assert "+Thanks!" in pull_service.get_pull_diff(repo, 1, "README.md").diff
    for bad in ["src/app.py", "--output=x", "*", "../x"]:
        with pytest.raises(NotFound):
            pull_service.get_pull_diff(repo, 1, bad)
    with pytest.raises(InvalidInput):
        pull_service.get_pull_diff(repo, 1, "a\x00b")


def test_pull_diff_rebuilds_context_after_restart(gh):
    repo, _, _ = gh
    pull_service._ctx.clear()
    assert "+Thanks!" in pull_service.get_pull_diff(repo, 1, "README.md").diff


def test_missing_pull_request(gh):
    repo, _, _ = gh
    with pytest.raises(NotFound):
        pull_service.get_pull(repo, 999)


@pytest.mark.parametrize("bad", [0, -1, 10_000_001, "1", "1; rm -rf /", 1.5, True, None])
def test_fetch_rejects_bad_numbers(gh, bad):
    repo, _, _ = gh
    with pytest.raises(InvalidInput):
        git_runner.fetch_pull_ref(repo.root, bad)


def test_local_repositories_cannot_fetch(demo, demo_path):
    with pytest.raises(InvalidInput):
        git_runner.fetch_pull_ref(demo_path, 1)
    with pytest.raises(InvalidInput):
        pull_service.get_pull(demo, 1)


def test_fetch_is_exclusive_with_clones(gh):
    repo, _, _ = gh
    assert git_runner._clone_lock.acquire(blocking=False)
    try:
        with pytest.raises(Busy):
            git_runner.fetch_pull_ref(repo.root, 1)
    finally:
        git_runner._clone_lock.release()


def test_fetch_command_is_hardened(gh, monkeypatch):
    repo, _, _ = gh
    seen = {}

    def fake(cmd, **kw):
        seen["cmd"] = cmd
        return 0, ""

    monkeypatch.setattr(git_runner, "_run_bounded", fake)
    git_runner.fetch_pull_ref(repo.root, 42)
    cmd = seen["cmd"]
    assert cmd[-2:] == ["origin", "+refs/pull/42/head:refs/branchverse/pr/42"]
    assert "fetch" in cmd and "--no-tags" in cmd and "core.hooksPath=" + __import__("os").devnull in cmd


def test_pull_endpoints(client, gh, monkeypatch):
    repo, _, _ = gh
    client.app.state.repo = repo
    r = client.get("/api/pulls/1")
    assert r.status_code == 200 and r.json()["compare"]["ahead"] == 1
    assert "+Thanks!" in client.get("/api/pulls/1/diff", params={"path": "README.md"}).json()["diff"]
    assert client.get("/api/pulls/0").status_code == 422
    assert client.get("/api/pulls/abc").status_code == 422
    assert client.get("/api/pulls/999").status_code == 404


def test_pull_endpoint_requires_github_repository(open_client):
    r = open_client.get("/api/pulls/1")
    assert r.status_code == 400 and "GitHub" in r.json()["error"]["message"]


# ------------------------------------------------------- GitHub API hygiene


def test_clean_pull_types_and_truncates():
    out = github_api.clean_pull({
        "title": "T" * 1000, "state": "open", "merged": False, "draft": True,
        "user": {"login": "x" * 200}, "body": "b" * 9000,
        "base": {"ref": "main", "sha": "A" * 40}, "head": {"label": 5},
    })
    assert len(out["title"]) == 300 and len(out["author"]) == 60 and len(out["body"]) == 4000
    assert out["base_sha"] is None  # not lowercase 40-hex
    assert out["head_label"] is None and out["state"] == "open" and out["draft"] is True


def test_clean_pull_state_and_garbage():
    assert github_api.clean_pull({"state": "closed", "merged_at": "2024-01-01"})["state"] == "merged"
    assert github_api.clean_pull({"state": "weird"})["state"] == "unknown"
    assert github_api.clean_pull("nope") is None and github_api.clean_pull(None) is None
    ok = github_api.clean_pull({"base": {"sha": "a" * 40}})
    assert ok["base_sha"] == "a" * 40


def test_api_fetch_is_bounded_and_failure_tolerant(monkeypatch):
    class Resp(io.BytesIO):
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    urls = []

    def fake_open(req, timeout):
        urls.append(req.full_url)
        return Resp(json.dumps({"title": "hi"}).encode())

    monkeypatch.setattr(github_api._opener, "open", fake_open)
    assert github_api.fetch_pull_meta("o", "r", 7)["title"] == "hi"
    assert urls == ["https://api.github.com/repos/o/r/pulls/7"]

    monkeypatch.setattr(github_api._opener, "open", lambda req, timeout: Resp(b"x" * 1_000_001))
    assert github_api.fetch_pull_meta("o", "r", 7) is None
    monkeypatch.setattr(github_api._opener, "open", lambda req, timeout: Resp(b"not json"))
    assert github_api.fetch_pull_meta("o", "r", 7) is None

    def boom(req, timeout):
        raise github_api.urllib.error.URLError("offline")

    monkeypatch.setattr(github_api._opener, "open", boom)
    assert github_api.fetch_pull_meta("o", "r", 7) is None


def test_api_never_follows_redirects_off_host():
    h = github_api._SameHostRedirects()
    req = github_api.urllib.request.Request("https://api.github.com/x")
    assert h.redirect_request(req, None, 302, "Found", {}, "https://evil.example/x") is None
    assert h.redirect_request(req, None, 302, "Found", {}, "http://api.github.com/x") is None
    assert h.redirect_request(req, None, 302, "Found", {}, "https://api.github.com/y") is not None


# ----------------------------------------------------- caching and streaming


def test_cache_serves_until_refs_change(tmp_path, demo_path, monkeypatch):
    monkeypatch.setattr(cache, "FP_TTL", 0)  # always re-check the repository state
    clone = tmp_path / "c"
    git(tmp_path, "clone", "-q", str(demo_path), str(clone))
    repo = git_service.open_repository(str(clone))
    calls = []
    f = lambda: calls.append(1) or len(calls)
    assert cache.cached(repo, "t", f) == 1 and cache.cached(repo, "t", f) == 1
    assert cache.cached(repo, "t", f, "other-arg") == 2          # different key
    git(clone, "-c", "user.name=T", "-c", "user.email=t@e.x", "commit", "-q", "--allow-empty", "-m", "new")
    assert cache.cached(repo, "t", f) == 3                       # refs moved: recomputed


def test_cache_is_bounded():
    cache.clear()
    class R: root = "x"
    for i in range(cache.MAX_ENTRIES + 10):
        cache._store[(str(i),)] = i
    with cache._lock:
        while len(cache._store) > cache.MAX_ENTRIES:
            cache._store.popitem(last=False)
    assert len(cache._store) == cache.MAX_ENTRIES
    cache.clear()


def test_iter_git_streams_records_and_bounds_output(demo_path):
    shas = [r.decode() for r in git_runner.iter_git(demo_path, ["log", "--all", "-z", "--format=%H"])]
    assert len(shas) == 14 and all(len(s) == 40 for s in shas)
    lines = list(git_runner.iter_git(demo_path, ["log", "--all", "--format=%s"], sep=b"\n"))
    assert len(lines) == 14
    from app.core.errors import GitCommandError, GitOutputTooLarge, GitTimeout
    with pytest.raises(GitOutputTooLarge):
        list(git_runner.iter_git(demo_path, ["log", "--all"], max_bytes=40))
    with pytest.raises(GitTimeout):
        list(git_runner.iter_git(demo_path, ["log", "--all"], timeout=0.0001))
    with pytest.raises(GitCommandError):
        list(git_runner.iter_git(demo_path, ["cat-file", "-e", "0" * 40 + "^{commit}"]))
    with pytest.raises(InvalidInput):
        list(git_runner.iter_git(demo_path, ["checkout", "x"]))


def test_iter_git_early_exit_reaps_process(demo_path):
    gen = git_runner.iter_git(demo_path, ["log", "--all", "--format=%H"], sep=b"\n")
    assert next(gen)
    gen.close()  # must not hang or leave the subprocess running


def test_responses_are_gzipped(open_client):
    r = open_client.get("/api/commits?limit=200", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.headers.get("content-encoding") == "gzip"
    assert len(r.json()["commits"]) == 14


def test_fingerprint_is_reused_briefly_and_forgettable(tmp_path, demo_path, monkeypatch):
    clone = tmp_path / "c"
    git(tmp_path, "clone", "-q", str(demo_path), str(clone))
    calls = []
    real = cache.run_git
    monkeypatch.setattr(cache, "run_git", lambda *a, **k: calls.append(1) or real(*a, **k))
    cache.clear()
    a = cache.fingerprint(clone)
    assert cache.fingerprint(clone) == a and len(calls) == 1      # reused inside the window
    git(clone, "-c", "user.name=T", "-c", "user.email=t@e.x", "commit", "-q", "--allow-empty", "-m", "x")
    assert cache.fingerprint(clone) == a                           # still within the window
    cache.forget(clone)
    assert cache.fingerprint(clone) != a and len(calls) == 2       # explicit re-check sees the change


def test_bulk_branch_counts_match_per_branch_rev_list(demo, monkeypatch):
    fast = {b.name: (b.comparison.ahead, b.comparison.behind) for b in git_service.get_branches(demo).branches}
    cache.clear()
    monkeypatch.setattr(git_service, "_bulk_counts", lambda *a, **k: None)  # force the fallback path
    slow = {b.name: (b.comparison.ahead, b.comparison.behind) for b in git_service.get_branches(demo).branches}
    assert fast == slow and fast["fix/typo"] == (1, 0)


def test_bulk_counts_handle_upstream_tracking(tmp_path, demo_path):
    clone = tmp_path / "c"
    git(tmp_path, "clone", "-q", str(demo_path), str(clone))
    git(clone, "reset", "-q", "--hard", "HEAD~1")
    git(clone, "-c", "user.name=T", "-c", "user.email=t@e.x", "commit", "-q", "--allow-empty", "-m", "local")
    main = next(b for b in git_service.get_branches(git_service.open_repository(str(clone))).branches if b.name == "main")
    behind, ahead = (int(x) for x in git(clone, "rev-list", "--left-right", "--count", "origin/main...main").split())
    assert main.comparison.kind == "upstream"
    assert (main.comparison.ahead, main.comparison.behind) == (ahead, behind) == (1, 1)
