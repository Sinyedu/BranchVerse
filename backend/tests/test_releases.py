import pytest

from app.services import git_service, release_service

from .conftest import git

DAY = 86400
BASE = 1_700_000_000


def commit(repo, name, author, when, filename):
    (repo / filename).write_text(name)
    git(repo, "add", filename)
    stamp = f"{when} +0000"
    git(repo, "commit", "-q", "-m", name, env={
        "GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": f"{author}@x.test", "GIT_AUTHOR_DATE": stamp,
        "GIT_COMMITTER_NAME": author, "GIT_COMMITTER_EMAIL": f"{author}@x.test", "GIT_COMMITTER_DATE": stamp,
    })


@pytest.fixture()
def tagged(tmp_path):
    repo = tmp_path / "tagged"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    commit(repo, "one", "Ann", BASE, "a.txt")
    commit(repo, "two", "Ann", BASE + DAY, "b.txt")
    git(repo, "tag", "v1.0.0")  # lightweight
    commit(repo, "three", "Bob", BASE + 3 * DAY, "c.txt")
    commit(repo, "four", "Cy", BASE + 4 * DAY, "d.txt")
    commit(repo, "five", "Bob", BASE + 5 * DAY, "e.txt")
    tag_env = {"GIT_COMMITTER_NAME": "Ann", "GIT_COMMITTER_EMAIL": "a@x.test",
               "GIT_COMMITTER_DATE": f"{BASE + 6 * DAY} +0000"}
    git(repo, "tag", "-a", "v1.1.0", "-m", "Second release", env=tag_env)  # annotated
    git(repo, "tag", "tree-tag", "HEAD^{tree}")  # not a commit: must be ignored
    return git_service.open_repository(str(repo))


def test_release_ranges_and_metadata(tagged):
    result = release_service.get_releases(tagged)
    assert [r.name for r in result.releases] == ["v1.0.0", "v1.1.0"]
    first, second = result.releases
    assert (first.previous, first.commits, first.contributors, first.annotated) == (None, 2, 1, False)
    assert first.days_since_previous is None and first.message is None
    assert (second.previous, second.commits, second.contributors) == ("v1.0.0", 3, 2)
    assert second.annotated and second.message == "Second release"
    assert second.days_since_previous == 5.0
    assert second.short_sha == second.sha[:7] and len(second.sha) == 40
    assert result.total_tags == 2 and not result.truncated


def test_no_tags_message(demo, empty_repo):
    empty = git_service.open_repository(str(empty_repo))
    result = release_service.get_releases(empty)
    assert result.releases == [] and "no tags" in result.note


def test_demo_repo_has_single_release(demo):
    result = release_service.get_releases(demo)
    assert [r.name for r in result.releases] == ["v0.1.0"]
    assert result.releases[0].commits and result.releases[0].commits > 0


def test_truncation_keeps_newest_and_links_previous(tagged, monkeypatch):
    monkeypatch.setattr(release_service, "MAX_RELEASES", 1)
    result = release_service.get_releases(tagged)
    assert result.truncated and result.total_tags == 2
    (only,) = result.releases
    assert only.name == "v1.1.0" and only.previous == "v1.0.0" and only.commits == 3
    assert "newest 1 of 2" in result.note


def test_releases_endpoint(open_client):
    body = open_client.get("/api/releases").json()
    assert body["releases"][0]["name"] == "v0.1.0"
    assert set(body) == {"releases", "total_tags", "truncated", "note"}


def test_releases_requires_open_repository_and_token(client):
    assert client.get("/api/releases").status_code in (400, 404, 409)
    no_token = client.__class__(client.app, headers={})
    assert no_token.get("/api/releases").status_code == 401
