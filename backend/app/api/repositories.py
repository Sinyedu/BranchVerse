from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ..core.errors import NoRepository
from ..schemas import git as s
from ..services import analytics_service, git_service, strategy_service, timeline_service
from ..services.git_service import Repo

router = APIRouter(prefix="/api")


def _repo(request: Request) -> Repo:
    repo = getattr(request.app.state, "repo", None)
    if repo is None:
        raise NoRepository("No repository is open.")
    return repo


# All handlers are plain `def`: FastAPI runs them in its thread pool, so
# blocking Git subprocesses never stall the event loop.


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/session")
def session(request: Request) -> dict[str, str]:
    return {"token": request.app.state.token}


@router.post("/repositories/open", response_model=s.RepositoryInfo)
def open_repository(body: s.OpenRepositoryRequest, request: Request):
    repo = git_service.open_repository(body.path)
    request.app.state.repo = repo
    return git_service.repository_info(repo)


@router.get("/repositories/current", response_model=s.RepositoryInfo)
def current(request: Request):
    return git_service.repository_info(_repo(request))


@router.get("/commits", response_model=s.CommitPage)
def commits(request: Request, limit: int = Query(100), offset: int = Query(0)):
    return git_service.get_commits(_repo(request), limit, offset)


@router.get("/commits/{sha}", response_model=s.CommitDetails)
def commit(sha: str, request: Request):
    return git_service.get_commit_details(_repo(request), sha)


@router.get("/commits/{sha}/diff", response_model=s.FileDiff)
def commit_diff(sha: str, request: Request, path: str = Query(max_length=4096)):
    return git_service.get_file_diff(_repo(request), sha, path)


@router.get("/branches", response_model=s.BranchList)
def branches(request: Request):
    return git_service.get_branches(_repo(request))


@router.get("/branches/reachable", response_model=s.Reachable)
def reachable(request: Request, ref: str = Query(max_length=1024)):
    return git_service.get_reachable(_repo(request), ref)


@router.get("/analytics", response_model=s.Analytics)
def analytics(request: Request, days: int = Query(180)):
    return analytics_service.get_analytics(_repo(request), days)


@router.get("/timeline", response_model=s.Timeline)
def timeline(request: Request):
    return timeline_service.get_timeline(_repo(request))


@router.get("/timeline/{sha}", response_model=s.Snapshot)
def snapshot(sha: str, request: Request):
    return timeline_service.get_snapshot(_repo(request), sha)


@router.get("/strategy", response_model=s.Strategy)
def strategy(request: Request):
    return strategy_service.get_strategy(_repo(request))
