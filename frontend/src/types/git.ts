export type RefKind = 'head' | 'branch' | 'remote' | 'tag'

export interface RepositoryInfo {
  name: string
  path: string
  is_bare: boolean
  is_empty: boolean
  is_detached: boolean
  current_branch: string | null
  head_sha: string | null
  remote_url: string | null
}
export interface RefLabel { name: string; kind: RefKind }
export interface Commit {
  sha: string
  short_sha: string
  parents: string[]
  author: string
  email: string
  timestamp: number
  subject: string
  refs: RefLabel[]
}
export interface CommitPage { commits: Commit[]; offset: number; has_more: boolean }

export type FileStatus = 'added' | 'modified' | 'deleted' | 'renamed' | 'copied' | 'other'
export interface FileChange {
  path: string
  old_path: string | null
  status: FileStatus
  additions: number | null
  deletions: number | null
  binary: boolean
}
export interface CommitDetails {
  sha: string
  parents: string[]
  author: string
  author_email: string
  author_date: number
  committer: string
  committer_email: string
  commit_date: number
  message: string
  files: FileChange[]
  files_truncated: boolean
  total_additions: number
  total_deletions: number
  diff_base: string | null
  diff_base_note: string
}
export interface FileDiff {
  path: string
  binary: boolean
  diff: string
  truncated: boolean
  diff_base: string | null
}

export interface Comparison {
  kind: 'upstream' | 'default' | 'none'
  base: string | null
  ahead: number | null
  behind: number | null
  note: string | null
}
export interface Branch {
  name: string
  full_ref: string
  is_remote: boolean
  is_current: boolean
  sha: string
  last_commit_date: number
  comparison: Comparison
}
export interface BranchList { branches: Branch[]; default_branch: string | null }
export interface Reachable { full_ref: string; shas: string[]; truncated: boolean }

export interface Contributor { name: string; email: string; commits: number }
export interface WeekBucket { week_start: string; commits: number; additions: number; deletions: number }
export interface Analytics {
  total_commits: number
  contributor_count: number
  local_branches: number
  remote_branches: number
  first_commit: number | null
  latest_commit: number | null
  top_contributor: Contributor | null
  contributors: Contributor[]
  weekly_commits: WeekBucket[]
  weekly_changes: WeekBucket[]
  changes_days: number
  scan_truncated: boolean
  scan_limit: number
  scope_note: string
  changes_available: boolean
}

export interface TimelineCommit {
  sha: string
  short_sha: string
  timestamp: number
  author: string
  subject: string
  file_count: number | null
}
export interface Timeline { commits: TimelineCommit[]; truncated: boolean; note: string }
export interface PathChange { path: string; old_path: string | null }
export interface Snapshot {
  sha: string
  previous_sha: string | null
  file_count: number
  files: string[]
  files_truncated: boolean
  added: PathChange[]
  deleted: PathChange[]
  modified: PathChange[]
  renamed: PathChange[]
  additions: number
  deletions: number
  changes_truncated: boolean
}

export interface Evidence { label: string; value: string; detail: string }
export interface Strategy {
  default_branch: string | null
  style: 'trunk-based' | 'feature-branch' | 'gitflow-like' | 'unclear'
  summary: string
  evidence: Evidence[]
  prefixes: { prefix: string; count: number }[]
  merged_branches: string[]
  unmerged_branches: string[]
  sampled_commits: number
}

export interface Compare {
  base: string
  head: string
  base_sha: string
  head_sha: string
  merge_base: string | null
  ahead: number
  behind: number
  commits: Commit[]
  commits_truncated: boolean
  files: FileChange[]
  files_truncated: boolean
  total_additions: number
  total_deletions: number
  note: string
}

export interface PullMeta {
  number: number
  title: string
  state: 'open' | 'closed' | 'merged' | 'unknown'
  draft: boolean
  author: string | null
  body: string
  url: string
  base_ref: string | null
  head_label: string | null
  created_at: string | null
  metadata_available: boolean
  note: string | null
}
export interface PullRequest { meta: PullMeta; compare: Compare }
