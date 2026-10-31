import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fixtures"))
sys.path.insert(0, str(ROOT / "backend"))

from create_demo_repo import create_demo_repo  # noqa: E402

from app.main import create_app  # noqa: E402
from app.services import git_service  # noqa: E402

TOKEN = "test-token"


def git(repo: Path, *args: str, env: dict | None = None) -> str:
    e = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    e.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    e.update(env or {})
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", *args],
        env=e, capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture(scope="session")
def demo_path(tmp_path_factory) -> Path:
    return create_demo_repo(tmp_path_factory.mktemp("demo") / "demo repo")  # has a space


@pytest.fixture()
def demo(demo_path):
    return git_service.open_repository(str(demo_path))


@pytest.fixture()
def client():
    app = create_app(extra_hosts=frozenset({"testserver"}), token=TOKEN)
    return TestClient(app, headers={"X-BranchVerse-Token": TOKEN})


@pytest.fixture()
def open_client(client, demo_path):
    assert client.post("/api/repositories/open", json={"path": str(demo_path)}).status_code == 200
    return client


@pytest.fixture()
def empty_repo(tmp_path) -> Path:
    path = tmp_path / "empty"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    return path
