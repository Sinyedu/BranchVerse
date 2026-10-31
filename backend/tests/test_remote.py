"""GitHub-URL support. Clone tests use a local file:// source so they run offline."""

import pytest

from app.core import git_runner
from app.core.errors import Busy, GitTimeout, InvalidInput
from app.core.security import parse_github_url
from app.services import analytics_service, git_service, strategy_service

from .conftest import TOKEN, git


# ------------------------------------------------------------- URL parsing


@pytest.mark.parametrize("raw,expected", [
    ("https://github.com/octocat/Hello-World", ("octocat", "Hello-World")),
    ("https://github.com/octocat/Hello-World.git", ("octocat", "Hello-World")),
    ("https://github.com/octocat/Hello-World/", ("octocat", "Hello-World")),
    ("  https://github.com/octocat/Hello-World  ", ("octocat", "Hello-World")),
    ("https://github.com/octocat/Hello-World/tree/main/src", ("octocat", "Hello-World")),
    ("https://github.com/octocat/Hello-World?tab=readme#top", ("octocat", "Hello-World")),
    ("github.com/octocat/Hello-World", ("octocat", "Hello-World")),
    ("https://github.com/octocat/.github", ("octocat", ".github")),
    ("https://github.com/octocat/a.b_c-d", ("octocat", "a.b_c-d")),
])
def test_parse_accepts_public_repo_urls(raw, expected):
    assert parse_github_url(raw) == expected


@pytest.mark.parametrize("bad", [
    "", "   ", "octocat/Hello-World", "http://github.com/o/r", "ftp://github.com/o/r",
    "https://gitlab.com/o/r", "https://github.com/o", "https://github.com/",
    "https://github.com.evil.com/o/r", "https://evil.com/github.com/o/r",
    "https://user:pw@github.com/o/r", "https://github.com:8443/o/r",
    "https://github.com/-bad/r", "https://github.com/o/..", "https://github.com/o/.",
    "https://github.com/o/r r", "https://github.com/o/r\nhttps://evil.com",
    "https://github.com/o/--upload-pack=touch x", "file:///etc/passwd",
    "https://github.com/o/r\x00", "https://github.com/" + "a" * 50 + "/r",
    "https://github.com/o/" + "r" * 101, "-c core.sshCommand=evil", "ext::sh -c evil",
    "https://github.com/o/r%00", "https://github.com/o%2f/r",
])
def test_parse_rejects_everything_else(bad):
    with pytest.raises(InvalidInput):
        parse_github_url(bad)


def test_rebuilt_url_never_contains_extra_input():
    owner, repo = parse_github_url("https://github.com/o/r/tree/main?x=$(touch)&y=;rm")
    assert f"https://github.com/{owner}/{repo}.git" == "https://github.com/o/r.git"


# ------------------------------------------------------------ clone + open


@pytest.fixture()
def remote(tmp_path, demo_path, monkeypatch):
    """A file:// 'remote' that supports blobless clones, wired in as the cache."""
    src = tmp_path / "remote.git"
    git(tmp_path, "clone", "-q", "--bare", str(demo_path), str(src))
    git(src, "config", "uploadpack.allowFilter", "true")
    git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    monkeypatch.setattr(git_runner, "CACHE_ROOT", (tmp_path / "cache").resolve())
    monkeypatch.setattr(git_runner, "ALLOWED_REMOTE_PROTOCOL", "file")
    return "file:///" + str(src).replace("\\", "/").lstrip("/")


def test_blobless_clone_opens_and_works(remote):
    repo = git_service._clone_and_open(remote, "octo", "demo")
    assert repo.is_bare and repo.remote_url == remote
    assert git_runner.is_cached_repo(repo.root)
    info = git_service.repository_info(repo)
    assert info.remote_url == remote and info.current_branch == "main" and not info.is_empty

    commits = git_service.get_commits(repo, 200, 0).commits
    assert len(commits) == 14 and sum(len(c.parents) == 2 for c in commits) == 2
    names = {b.name for b in git_service.get_branches(repo).branches}
    assert {"main", "feature/login", "fix/typo"} <= names
    assert git_service.get_branches(repo).default_branch == "main"  # from the clone's HEAD
    assert strategy_service.get_strategy(repo).style == "feature-branch"


def test_clone_is_blobless_and_diffs_fetch_lazily(remote):
    repo = git_service._clone_and_open(remote, "octo", "demo")
    cfg = git(repo.root, "config", "--get", "remote.origin.partialclonefilter")
    assert cfg == "blob:none"
    sha = next(c.sha for c in git_service.get_commits(repo, 200, 0).commits if c.subject == "Greet by name")
    d = git_service.get_commit_details(repo, sha)  # fetches the needed blobs on demand
    assert d.files[0].additions and d.files[0].deletions
    assert "+def main(name='world')" in git_service.get_file_diff(repo, sha, "src/app.py").diff


def test_analytics_flags_missing_line_changes(remote):
    repo = git_service._clone_and_open(remote, "octo", "demo")
    a = analytics_service.get_analytics(repo)
    assert a.total_commits == 14 and a.contributor_count == 3
    assert a.changes_available is False and a.weekly_changes == []
    assert "unavailable" in a.scope_note


def test_reopening_replaces_previous_download(remote):
    first = git_service._clone_and_open(remote, "octo", "demo")
    second = git_service._clone_and_open(remote, "octo", "demo")
    assert first.root != second.root
    assert not first.root.exists() and second.root.exists()


def test_failed_clone_leaves_nothing_behind(tmp_path, monkeypatch):
    monkeypatch.setattr(git_runner, "CACHE_ROOT", (tmp_path / "cache").resolve())
    monkeypatch.setattr(git_runner, "ALLOWED_REMOTE_PROTOCOL", "file")
    missing = "file:///" + str(tmp_path / "nope.git").replace("\\", "/").lstrip("/")
    with pytest.raises(Exception):
        git_service._clone_and_open(missing, "o", "r")
    assert list((tmp_path / "cache" / "github").glob("*")) == []


def test_clone_timeout_is_enforced_and_cleaned_up(remote, tmp_path):
    dest = git_runner.CACHE_ROOT / "github" / "t"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with pytest.raises(GitTimeout):
        git_runner.clone_bare(remote, dest, timeout=0.001)
    assert not dest.exists()


def test_clone_refuses_destination_outside_cache(remote, tmp_path):
    with pytest.raises(InvalidInput):
        git_runner.clone_bare(remote, tmp_path / "elsewhere")


def test_only_one_clone_at_a_time(remote):
    assert git_runner._clone_lock.acquire(blocking=False)
    try:
        with pytest.raises(Busy):
            git_runner.clone_bare(remote, git_runner.CACHE_ROOT / "github" / "x")
    finally:
        git_runner._clone_lock.release()


# --------------------------------------------------- network containment


def test_only_cached_repos_get_network_access(demo_path, remote):
    local = " ".join(git_runner.build_command(demo_path, ["log"]))
    assert "protocol.allow=never" in local and "protocol.https.allow" not in local
    assert "protocol.file.allow" not in local
    assert git_runner._clean_env(False)["GIT_CONFIG_NOSYSTEM"] == "1"

    cached = git_service._clone_and_open(remote, "octo", "demo")
    flags = " ".join(git_runner.build_command(cached.root, ["log"]))
    assert "protocol.file.allow=always" in flags and "credential.helper=" in flags
    assert "GIT_CONFIG_NOSYSTEM" not in git_runner._clean_env(True)


def test_clone_command_is_hardened(monkeypatch, remote):
    captured = {}

    class Boom(Exception):
        pass

    def fake_popen(cmd, **kw):
        captured["cmd"], captured["kw"] = cmd, kw
        raise Boom

    monkeypatch.setattr(git_runner.subprocess, "Popen", fake_popen)
    with pytest.raises(Boom):
        git_runner.clone_bare("https://github.com/o/r.git", git_runner.CACHE_ROOT / "github" / "z")
    cmd = captured["cmd"]
    assert captured["kw"]["shell"] is False and isinstance(cmd, list)
    assert cmd[cmd.index("clone") :][-3:-1] == ["--", "https://github.com/o/r.git"]
    joined = " ".join(cmd)
    for needle in ["--filter=blob:none", "--bare", "protocol.allow=never", "core.hooksPath="]:
        assert needle in joined
    assert not git_runner._clone_lock.locked()


# ----------------------------------------------------------------- HTTP


def test_open_url_endpoint_validates_before_any_network(client):
    for bad in ["https://evil.com/o/r", "http://github.com/o/r", "ext::sh -c id"]:
        r = client.post("/api/repositories/open-url", json={"url": bad})
        assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_input"
    plain = type(client)(client.app)
    assert plain.post("/api/repositories/open-url", json={"url": "https://github.com/o/r"}).status_code == 401
    assert client.post("/api/repositories/open-url", json={}).status_code == 422


def test_open_url_endpoint_end_to_end(client, remote, monkeypatch):
    monkeypatch.setattr(git_service, "parse_github_url", lambda raw: ("octo", "demo"))
    monkeypatch.setattr(git_service, "_clone_and_open",
                        lambda url, o, n, _orig=git_service._clone_and_open: _orig(remote, o, n))
    r = client.post("/api/repositories/open-url", json={"url": "https://github.com/octo/demo"})
    assert r.status_code == 200 and r.json()["remote_url"] == remote
    assert client.get("/api/commits?limit=3").json()["has_more"]
    assert client.get("/api/analytics").json()["changes_available"] is False
    assert TOKEN  # header was supplied by the client fixture


def test_prune_cache_removes_only_old_downloads(remote):
    import os, time
    parent = git_runner.CACHE_ROOT / "github"
    parent.mkdir(parents=True, exist_ok=True)
    old, fresh = parent / "old__repo__1", parent / "fresh__repo__2"
    for d in (old, fresh):
        d.mkdir()
        (d / "f").write_text("x")
    ancient = time.time() - 3 * 86400
    os.utime(old, (ancient, ancient))
    assert git_runner.prune_cache(24) == 1
    assert not old.exists() and fresh.exists()
