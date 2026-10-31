import os
import sys

import pytest

from app.core import git_runner
from app.core.errors import GitTimeout, GitUnavailable, InvalidInput
from app.core.git_runner import build_command, run_git
from app.core.security import host_allowed, origin_allowed, validate_sha
from app.services import git_service

from .conftest import TOKEN, git

HDR = {"X-BranchVerse-Token": TOKEN}


# --------------------------------------------------------------- git runner


@pytest.mark.parametrize(
    "sub", ["checkout", "switch", "merge", "rebase", "reset", "push", "pull", "fetch",
            "commit", "clone", "branch", "config", "gc", "clean", "restore", "tag", "stash"])
def test_runner_refuses_non_read_only_subcommands(demo_path, sub):
    with pytest.raises(InvalidInput):
        run_git(demo_path, [sub, "x"])


def test_runner_rejects_nul_and_empty(demo_path):
    with pytest.raises(InvalidInput):
        run_git(demo_path, ["log", "a\x00b"])
    with pytest.raises(InvalidInput):
        run_git(demo_path, [])


def test_command_is_an_argument_array_with_hardening(demo_path):
    cmd = build_command(demo_path, ["log", "--oneline"])
    assert isinstance(cmd, list) and cmd[0] == "git"
    joined = " ".join(cmd)
    for needle in ["--no-pager", "--literal-pathspecs", "core.fsmonitor=false", "diff.external="]:
        assert needle in joined


def test_user_input_stays_a_single_argument(demo_path):
    evil = "x; rm -rf / && $(touch pwned) --output=/tmp/x"
    cmd = build_command(demo_path, ["diff", "--", evil])
    assert cmd[-1] == evil and cmd[-2] == "--"


def test_timeout(demo_path):
    with pytest.raises(GitTimeout):
        run_git(demo_path, ["log", "--all"], timeout=0.001)


def test_output_cap_truncates_or_raises(demo_path):
    res = run_git(demo_path, ["log", "--all"], max_bytes=50, truncate_ok=True)
    assert res.truncated and len(res.stdout) == 50
    from app.core.errors import GitOutputTooLarge
    with pytest.raises(GitOutputTooLarge):
        run_git(demo_path, ["log", "--all"], max_bytes=50)


def test_missing_git_is_reported(monkeypatch, demo_path):
    monkeypatch.setattr(git_runner, "_clean_env", lambda: {"PATH": ""})
    monkeypatch.setattr(git_runner.subprocess, "Popen",
                        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    with pytest.raises(GitUnavailable):
        run_git(demo_path, ["log"])


def test_inherited_git_env_is_ignored(monkeypatch, demo_path):
    monkeypatch.setenv("GIT_DIR", "/definitely/not/here")
    monkeypatch.setenv("GIT_EXTERNAL_DIFF", "evil")
    assert run_git(demo_path, ["rev-parse", "--is-bare-repository"]).text().strip() == "false"


# ---------------------------------------------- hostile repository content


def test_repo_config_cannot_run_external_programs(tmp_path, demo_path):
    marker = tmp_path / "pwned.txt"
    script = tmp_path / "evil.py"
    script.write_text(f"open(r'{marker}', 'w').write('x')\n")
    clone = tmp_path / "hostile"
    git(tmp_path, "clone", "-q", str(demo_path), str(clone))
    cmd = f'"{sys.executable}" "{script}"'
    for key in ("diff.external", "core.fsmonitor", "core.pager", "diff.tool"):
        git(clone, "config", key, cmd)
    git(clone, "config", "diff.evil.textconv", cmd)
    (clone / ".gitattributes").write_text("*.py diff=evil\n")
    git(clone, "config", "core.hooksPath", str(tmp_path / "hooks"))
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "post-checkout").write_text(f"#!/bin/sh\n{cmd}\n")

    repo = git_service.open_repository(str(clone))
    commits = git_service.get_commits(repo, 50, 0).commits
    for c in commits:
        d = git_service.get_commit_details(repo, c.sha)
        for f in d.files:
            git_service.get_file_diff(repo, c.sha, f.path)
    git_service.get_branches(repo)
    assert not marker.exists()


def test_operations_do_not_mutate_repository(tmp_path, demo_path):
    def state(path):
        files = sorted(str(p.relative_to(path)) for p in path.rglob("*") if ".git" not in p.parts)
        return (git(path, "status", "--porcelain"), git(path, "for-each-ref"),
                git(path, "rev-parse", "HEAD"), files,
                (path / ".git" / "index").stat().st_mtime_ns)

    before = state(demo_path)
    repo = git_service.open_repository(str(demo_path))
    from app.services import analytics_service, timeline_service
    for c in git_service.get_commits(repo, 50, 0).commits:
        git_service.get_commit_details(repo, c.sha)
    git_service.get_branches(repo)
    analytics_service.get_analytics(repo)
    t = timeline_service.get_timeline(repo)
    for c in t.commits:
        timeline_service.get_snapshot(repo, c.sha)
    assert state(demo_path) == before


# -------------------------------------------------------------- validation


def test_validate_sha():
    assert validate_sha("a" * 40)
    for bad in ["", "a" * 39, "a" * 41, "A" * 40, "HEAD", "-" * 40, "a" * 39 + "\n", None]:
        with pytest.raises(InvalidInput):
            validate_sha(bad)


def test_host_checks():
    assert host_allowed("localhost:8000") and host_allowed("127.0.0.1") and host_allowed("[::1]:80")
    for bad in [None, "", "evil.com", "localhost.evil.com", "127.0.0.1.evil.com:8000", "evil.com:8000"]:
        assert not host_allowed(bad)


def test_origin_checks():
    allowed = ("http://localhost:5173",)
    assert origin_allowed(None, allowed) and origin_allowed("http://localhost:5173", allowed)
    for bad in ["http://evil.com", "https://localhost:5173", "http://localhost:5174", "null"]:
        assert not origin_allowed(bad, allowed)


# ------------------------------------------------------------- HTTP layer


def test_requests_without_token_are_rejected(client, demo_path):
    plain = type(client)(client.app)
    assert plain.get("/api/health").status_code == 200
    assert plain.get("/api/commits").status_code == 401
    r = plain.post("/api/repositories/open", json={"path": str(demo_path)})
    assert r.status_code == 401
    assert plain.get("/api/commits", headers={"X-BranchVerse-Token": "wrong"}).status_code == 401


def test_rebinding_host_is_rejected(client):
    r = client.get("/api/health", headers={"Host": "attacker.example:8000"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "bad_host"


def test_foreign_origin_is_rejected(client, demo_path):
    r = client.post("/api/repositories/open", json={"path": str(demo_path)},
                    headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    assert client.get("/api/session", headers={"Origin": "http://evil.example"}).status_code == 403


def test_allowed_origin_gets_cors_headers(client):
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert client.options(
        "/api/commits", headers={"Origin": "http://evil.example",
                                 "Access-Control-Request-Method": "GET"}
    ).headers.get("access-control-allow-origin") is None


def test_no_repository_selected(client):
    r = client.get("/api/commits")
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_repository"


def test_session_endpoint_returns_token(client):
    assert client.get("/api/session").json() == {"token": TOKEN}


def test_open_errors_are_clean(client, tmp_path):
    r = client.post("/api/repositories/open", json={"path": str(tmp_path)})
    assert r.status_code == 400
    assert "Traceback" not in r.text and "stderr" not in r.text
    assert client.post("/api/repositories/open", json={}).status_code == 422


def test_api_end_to_end(open_client):
    c = open_client
    assert c.get("/api/repositories/current").json()["current_branch"] == "main"
    commits = c.get("/api/commits?limit=3").json()
    assert len(commits["commits"]) == 3 and commits["has_more"]
    sha = commits["commits"][0]["sha"]
    assert c.get(f"/api/commits/{sha}").json()["files"]
    assert c.get(f"/api/commits/{sha}/diff", params={"path": "README.md"}).json()["diff"]
    assert c.get("/api/commits/HEAD").status_code == 400
    assert c.get("/api/commits/" + "0" * 40).status_code == 404
    assert c.get(f"/api/commits/{sha}/diff", params={"path": "nope"}).status_code == 404
    assert c.get("/api/commits?limit=99999").status_code == 400
    assert c.get("/api/branches").json()["default_branch"] == "main"
    assert c.get("/api/branches/reachable", params={"ref": "refs/heads/main"}).status_code == 200
    assert c.get("/api/analytics").json()["total_commits"] == 14
    assert c.get("/api/strategy").json()["style"] == "feature-branch"
    tl = c.get("/api/timeline").json()
    assert c.get(f"/api/timeline/{tl['commits'][0]['sha']}").json()["file_count"] == 2
