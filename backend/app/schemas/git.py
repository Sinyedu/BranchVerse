from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RefKind = Literal["head", "branch", "remote", "tag"]


class OpenRepositoryRequest(BaseModel):
    path: str = Field(max_length=4096)


class RepositoryInfo(BaseModel):
    name: str
    path: str
    is_bare: bool
    is_empty: bool
    is_detached: bool
    current_branch: str | None
    head_sha: str | None


class RefLabel(BaseModel):
    name: str
    kind: RefKind


class Commit(BaseModel):
    sha: str
    short_sha: str
    parents: list[str]
    author: str
    email: str
    timestamp: int
    subject: str
    refs: list[RefLabel]


class CommitPage(BaseModel):
    commits: list[Commit]
    offset: int
    has_more: bool


class FileChange(BaseModel):
    path: str
    old_path: str | None = None
    status: Literal["added", "modified", "deleted", "renamed", "copied", "other"]
    additions: int | None = None
    deletions: int | None = None
    binary: bool = False


class CommitDetails(BaseModel):
    sha: str
    parents: list[str]
    author: str
    author_email: str
    author_date: int
    committer: str
    committer_email: str
    commit_date: int
    message: str
    files: list[FileChange]
    files_truncated: bool
    total_additions: int
    total_deletions: int
    diff_base: str | None
    diff_base_note: str


class FileDiff(BaseModel):
    path: str
    binary: bool
    diff: str
    truncated: bool
    diff_base: str | None


class Comparison(BaseModel):
    kind: Literal["upstream", "default", "none"]
    base: str | None
    ahead: int | None
    behind: int | None
    note: str | None = None


class Branch(BaseModel):
    name: str
    full_ref: str
    is_remote: bool
    is_current: bool
    sha: str
    last_commit_date: int
    comparison: Comparison


class BranchList(BaseModel):
    branches: list[Branch]
    default_branch: str | None


class Reachable(BaseModel):
    full_ref: str
    shas: list[str]
    truncated: bool


class Contributor(BaseModel):
    name: str
    email: str
    commits: int


class WeekBucket(BaseModel):
    week_start: str
    commits: int = 0
    additions: int = 0
    deletions: int = 0


class Analytics(BaseModel):
    total_commits: int
    contributor_count: int
    local_branches: int
    remote_branches: int
    first_commit: int | None
    latest_commit: int | None
    top_contributor: Contributor | None
    contributors: list[Contributor]
    weekly_commits: list[WeekBucket]
    weekly_changes: list[WeekBucket]
    changes_days: int
    scan_truncated: bool
    scan_limit: int
    scope_note: str


class TimelineCommit(BaseModel):
    sha: str
    short_sha: str
    timestamp: int
    author: str
    subject: str
    file_count: int | None = None


class Timeline(BaseModel):
    commits: list[TimelineCommit]
    truncated: bool
    note: str


class PathChange(BaseModel):
    path: str
    old_path: str | None = None


class Snapshot(BaseModel):
    sha: str
    previous_sha: str | None
    file_count: int
    files: list[str]
    files_truncated: bool
    added: list[PathChange]
    deleted: list[PathChange]
    modified: list[PathChange]
    renamed: list[PathChange]
    additions: int
    deletions: int
    changes_truncated: bool


class Evidence(BaseModel):
    label: str
    value: str
    detail: str


class BranchPrefix(BaseModel):
    prefix: str
    count: int


class Strategy(BaseModel):
    default_branch: str | None
    style: Literal["trunk-based", "feature-branch", "gitflow-like", "unclear"]
    summary: str
    evidence: list[Evidence]
    prefixes: list[BranchPrefix]
    merged_branches: list[str]
    unmerged_branches: list[str]
    sampled_commits: int
