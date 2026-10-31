import type { Commit, RefKind } from '../types/git'

/** An illustrative commit. Lessons are teaching examples, never repository data. */
interface Node { id: string; parents: string[]; subject: string; author: string }
type Refs = Record<string, [name: string, kind: RefKind][]>
interface Step { caption: string; count: number; refs: Refs }

export interface Lesson {
  id: string
  title: string
  summary: string
  body: string[]
  nodes: Node[] // chronological: parents always come before children
  steps: Step[]
  takeaway: string
}

const n = (id: string, subject: string, author: string, ...parents: string[]): Node => ({ id, parents, subject, author })
const H = (name: string): [string, RefKind] => [name, 'head']
const B = (name: string): [string, RefKind] => [name, 'branch']

/** Newest-first commits for the first `count` nodes, in the shape the real graph expects. */
export function lessonCommits(lesson: Lesson, step: number): Commit[] {
  const s = lesson.steps[step]
  const base = 1_700_000_000
  return lesson.nodes
    .slice(0, s.count)
    .map((node, i): Commit => ({
      sha: node.id,
      short_sha: node.id.slice(0, 7),
      parents: node.parents,
      author: node.author,
      email: '',
      timestamp: base + i * 86400,
      subject: node.subject,
      refs: (s.refs[node.id] ?? []).map(([name, kind]) => ({ name, kind })),
    }))
    .reverse()
}

export const LESSONS: Lesson[] = [
  {
    id: 'commits',
    title: '1 · Commits form a chain',
    summary: 'A commit is a snapshot that remembers its parent.',
    body: [
      'Every commit stores a snapshot of your project and a pointer to its parent — the commit it was built on top of. Follow the parents backwards and you walk the whole history.',
      'The very first commit (a root commit) has no parent. In the graph, time runs downwards: the newest commit is at the top.',
    ],
    nodes: [n('a1f3c20', 'Initial commit', 'Ada'), n('b72e9d1', 'Add login page', 'Ada', 'a1f3c20'), n('c9d04ab', 'Fix typo', 'Linus', 'b72e9d1')],
    steps: [
      { caption: 'The first commit has no parent — it is a root commit.', count: 1, refs: { a1f3c20: [H('main')] } },
      { caption: 'Each new commit points back at the one before it.', count: 2, refs: { b72e9d1: [H('main')] } },
      { caption: 'History is just this chain of parent pointers.', count: 3, refs: { c9d04ab: [H('main')] } },
    ],
    takeaway: 'Commits never change. A new commit always points at an existing one.',
  },
  {
    id: 'branches',
    title: '2 · Branches are just labels',
    summary: 'A branch is a movable name that points at one commit.',
    body: [
      'Creating a branch does not copy any files. It adds a new name that points at a commit. When you commit while on a branch, only that name moves forward.',
      'When two branches each get their own new commits, the history diverges — which is exactly what the lanes in the graph show.',
    ],
    nodes: [
      n('a1f3c20', 'Initial commit', 'Ada'), n('b72e9d1', 'Add login page', 'Ada', 'a1f3c20'),
      n('c9d04ab', 'Start search feature', 'Linus', 'b72e9d1'), n('d41b7e8', 'Update README', 'Ada', 'b72e9d1'),
    ],
    steps: [
      { caption: 'One branch, main, pointing at the latest commit.', count: 2, refs: { b72e9d1: [H('main')] } },
      { caption: 'Create "feature/search": a second label on the same commit. Nothing is copied.', count: 2, refs: { b72e9d1: [H('main'), B('feature/search')] } },
      { caption: 'Commit on the feature branch: only that label moves.', count: 3, refs: { b72e9d1: [H('main')], c9d04ab: [B('feature/search')] } },
      { caption: 'Meanwhile main gets its own commit. The history has diverged into two lanes.', count: 4, refs: { d41b7e8: [H('main')], c9d04ab: [B('feature/search')] } },
    ],
    takeaway: 'Branching is cheap because a branch is only a pointer.',
  },
  {
    id: 'merge',
    title: '3 · Merging brings lines of work together',
    summary: 'A merge commit has two parents.',
    body: [
      'Merging joins diverged work. Git creates a merge commit that has two parents: the branch you were on (the first parent) and the branch you merged in.',
      'In the graph, a merge commit is drawn as a hollow ring with lines to both parents. This is why BranchVerse compares merge commits against their first parent when showing file changes.',
    ],
    nodes: [
      n('a1f3c20', 'Initial commit', 'Ada'), n('b72e9d1', 'Add login page', 'Ada', 'a1f3c20'),
      n('c9d04ab', 'Start search feature', 'Linus', 'b72e9d1'), n('d41b7e8', 'Update README', 'Ada', 'b72e9d1'),
      n('e55a1f0', "Merge branch 'feature/search'", 'Ada', 'd41b7e8', 'c9d04ab'),
    ],
    steps: [
      { caption: 'Two branches have diverged.', count: 4, refs: { d41b7e8: [H('main')], c9d04ab: [B('feature/search')] } },
      { caption: "Merge feature/search into main: a new commit with two parents joins the lanes.", count: 5, refs: { e55a1f0: [H('main')], c9d04ab: [B('feature/search')] } },
    ],
    takeaway: 'The feature branch label stays where it was; main moved to the merge commit.',
  },
  {
    id: 'fast-forward',
    title: '4 · Fast-forward merges',
    summary: 'Sometimes a merge needs no merge commit.',
    body: [
      'If main has not moved since the branch was created, merging simply slides the main label forward along the branch. No new commit is made, and the history stays a straight line.',
      'Teams that want an explicit record of every merge disable this (git merge --no-ff); teams that want linear history prefer it, or squash/rebase.',
    ],
    nodes: [
      n('a1f3c20', 'Initial commit', 'Ada'), n('b72e9d1', 'Add login page', 'Ada', 'a1f3c20'),
      n('c9d04ab', 'Add search', 'Linus', 'b72e9d1'), n('d41b7e8', 'Polish search', 'Linus', 'c9d04ab'),
    ],
    steps: [
      { caption: 'feature/search is ahead of main. Main has no new commits of its own.', count: 4, refs: { b72e9d1: [H('main')], d41b7e8: [B('feature/search')] } },
      { caption: 'Fast-forward: main just moves to the same commit. No merge commit exists.', count: 4, refs: { d41b7e8: [H('main'), B('feature/search')] } },
    ],
    takeaway: 'No divergence, no merge commit — only a label moved.',
  },
  {
    id: 'trunk',
    title: '5 · Strategy: trunk-based',
    summary: 'Small changes, straight to main, many times a day.',
    body: [
      'Everyone integrates into one main line in small steps. Branches, if any, live for hours rather than weeks, and unfinished work is hidden behind feature flags.',
      'Strengths: little merge pain, fast feedback. Needs: strong automated tests and a culture of small commits.',
      'In BranchVerse a trunk-based project looks like a single straight lane.',
    ],
    nodes: [
      n('a1f3c20', 'Add health check', 'Ada'), n('b72e9d1', 'Handle empty input', 'Linus', 'a1f3c20'),
      n('c9d04ab', 'Add feature flag for search', 'Ada', 'b72e9d1'), n('d41b7e8', 'Search behind flag', 'Linus', 'c9d04ab'),
    ],
    steps: [{ caption: 'One lane. Every commit lands directly on main.', count: 4, refs: { d41b7e8: [H('main')] } }],
    takeaway: 'Look for: a single lane, very few side branches.',
  },
  {
    id: 'feature',
    title: '6 · Strategy: feature branches',
    summary: 'One short-lived branch per change, merged back.',
    body: [
      'Each change gets its own branch, is reviewed (often via a pull request) and is merged into main. Main always holds reviewed work.',
      'Strengths: isolation and review. Watch out for: branches that live too long and become painful to merge.',
      'In BranchVerse this shows up as short side lanes that rejoin main through merge commits.',
    ],
    nodes: [
      n('a1f3c20', 'Initial commit', 'Ada'), n('b72e9d1', 'Add login', 'Linus', 'a1f3c20'),
      n('c9d04ab', 'Add search', 'Grace', 'a1f3c20'), n('d41b7e8', "Merge 'feature/login'", 'Ada', 'a1f3c20', 'b72e9d1'),
      n('e55a1f0', "Merge 'feature/search'", 'Ada', 'd41b7e8', 'c9d04ab'),
    ],
    steps: [{
      caption: 'Two short branches, each merged back into main.', count: 5,
      refs: { e55a1f0: [H('main')], b72e9d1: [B('feature/login')], c9d04ab: [B('feature/search')] },
    }],
    takeaway: 'Look for: short side lanes, merge commits on main.',
  },
  {
    id: 'gitflow',
    title: '7 · Strategy: GitFlow',
    summary: 'main, develop, feature, release and hotfix branches.',
    body: [
      'GitFlow keeps a long-lived develop branch where features are integrated, cuts release branches to stabilise, and merges them into main (tagged) for production. Hotfixes branch from main.',
      'Strengths: clear release process for versioned software. Cost: many long-lived branches and merges; usually too heavy for continuously deployed services.',
      'In BranchVerse this shows up as a develop branch and branch names with feature/, release/ and hotfix/ prefixes.',
    ],
    nodes: [
      n('a1f3c20', 'Initial commit', 'Ada'),
      n('b72e9d1', 'Start develop', 'Ada', 'a1f3c20'),
      n('c9d04ab', 'Add search', 'Linus', 'b72e9d1'),
      n('d41b7e8', "Merge 'feature/search'", 'Ada', 'b72e9d1', 'c9d04ab'),
      n('e55a1f0', 'Bump version to 1.0', 'Ada', 'd41b7e8'),
      n('f60c2b3', "Release 1.0", 'Ada', 'a1f3c20', 'e55a1f0'),
    ],
    steps: [{
      caption: 'Feature merged into develop, stabilised on a release branch, then merged into main.', count: 6,
      refs: { f60c2b3: [H('main'), ['v1.0', 'tag']], e55a1f0: [B('release/1.0'), B('develop')], c9d04ab: [B('feature/search')] },
    }],
    takeaway: 'Look for: develop plus release/ and hotfix/ branches.',
  },
]
