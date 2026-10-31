"""Describe a repository's branching strategy from measurable evidence.

This is a heuristic summary of what the history *looks like*, not a verdict.
"""

from __future__ import annotations

from collections import Counter

from ..core.cache import cached
from ..core.git_runner import run_git
from ..schemas.git import BranchPrefix, Evidence, Strategy
from .git_service import Repo, get_branches

SAMPLE = 1000
GITFLOW_PREFIXES = {"feature", "release", "hotfix", "bugfix"}


def get_strategy(repo: Repo) -> Strategy:
    return cached(repo, "strategy", lambda: _compute_strategy(repo))


def _compute_strategy(repo: Repo) -> Strategy:
    result = get_branches(repo)
    local = [b for b in result.branches if not b.is_remote]
    default = next((b for b in result.branches if b.name == result.default_branch), None)
    if default is None:
        return Strategy(
            default_branch=None, style="unclear", sampled_commits=0, prefixes=[],
            merged_branches=[], unmerged_branches=[],
            summary="No default branch could be identified, so no strategy is inferred.",
            evidence=[Evidence(label="Default branch", value="unknown",
                               detail="No origin/HEAD, and not exactly one of main/master.")],
        )

    log = run_git(
        repo.root,
        ["log", "--first-parent", f"--max-count={SAMPLE}", "--format=%P", default.full_ref],
    ).text().splitlines()
    sampled = len(log)
    merges = sum(1 for line in log if len(line.split()) > 1)
    merge_ratio = merges / sampled if sampled else 0.0

    merged_out = run_git(
        repo.root, ["for-each-ref", f"--merged={default.full_ref}",
                    "--format=%(refname:short)", "refs/heads"]
    ).text().split()
    others = [b.name for b in local if b.name != default.name]
    merged = sorted(n for n in others if n in set(merged_out))
    unmerged = sorted(n for n in others if n not in set(merged_out))

    prefix_counts: Counter[str] = Counter(
        n.split("/", 1)[0] for n in others if "/" in n
    )
    names = {b.name for b in local}
    has_develop = bool(names & {"develop", "dev", "development"})
    flow_prefixes = {p for p in prefix_counts if p in GITFLOW_PREFIXES}

    if has_develop and ({"release", "hotfix"} & flow_prefixes or len(flow_prefixes) >= 2):
        style = "gitflow-like"
        summary = "Long-lived develop branch plus feature/release/hotfix branches."
    elif merge_ratio >= 0.2 or (merged and merge_ratio > 0):
        style = "feature-branch"
        summary = ("Work happens on short-lived branches that are merged back into "
                   f"{default.name} with merge commits.")
    elif sampled >= 5 and not others:
        style = "trunk-based"
        summary = f"Commits land directly on {default.name}; there are no side branches."
    elif sampled >= 5 and merge_ratio == 0:
        style = "trunk-based"
        summary = (f"{default.name}'s history is linear (no merge commits), consistent with "
                   "trunk-based development or squash/rebase merging.")
    else:
        style, summary = "unclear", "Not enough history to describe a branching strategy."

    evidence = [
        Evidence(label="Default branch", value=default.name,
                 detail="Identified from origin/HEAD, or the only main/master branch."),
        Evidence(label="Merge commits on the default branch",
                 value=f"{merges} of {sampled} ({merge_ratio:.0%})",
                 detail=f"First-parent history of {default.name}, newest {SAMPLE} commits. "
                        "High values suggest merge-based integration; zero suggests linear history."),
        Evidence(label="Other local branches", value=str(len(others)),
                 detail=f"{len(merged)} already merged into {default.name}, "
                        f"{len(unmerged)} not merged."),
        Evidence(label="Long-lived develop branch", value="yes" if has_develop else "no",
                 detail="A develop/dev branch is a common GitFlow signal."),
    ]
    if prefix_counts:
        evidence.append(Evidence(
            label="Branch naming", value=", ".join(f"{p}/ ×{c}" for p, c in prefix_counts.most_common(4)),
            detail="Prefixes such as feature/, release/, hotfix/ indicate a naming convention."))
    return Strategy(
        default_branch=default.name, style=style, summary=summary, evidence=evidence,
        prefixes=[BranchPrefix(prefix=p, count=c) for p, c in prefix_counts.most_common()],
        merged_branches=merged, unmerged_branches=unmerged, sampled_commits=sampled,
    )
