#!/usr/bin/env python3
"""Resolve a Codex-style merge-base vs a base branch. Prints one JSON object."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

USER_PROMPT = (
    "Review the code changes against the base branch '{base_branch}'. "
    "The merge base commit for this comparison is {merge_base_sha}. "
    "Run `git diff {merge_base_sha}` to inspect the changes relative to {base_branch}. "
    "Provide prioritized, actionable findings."
)
USER_PROMPT_BACKUP = (
    "Review the code changes against the base branch '{branch}'. "
    "Start by finding the merge diff between the current branch and {branch}'s upstream "
    'e.g. (`git merge-base HEAD "$(git rev-parse --abbrev-ref \'{branch}@{{upstream}}\')"`, '
    "then run `git diff` against that SHA to see what changes we would merge into the "
    "{branch} branch. Provide prioritized, actionable findings."
)


def git(repo: Path, args: list[str], timeout: float | None = None) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def current_branch(repo: Path) -> str | None:
    name = git(repo, ["branch", "--show-current"])
    return name or None


def resolve_ref(repo: Path, ref: str) -> str | None:
    return git(repo, ["rev-parse", "--verify", ref])


def preferred_base_ref(repo: Path, branch: str) -> str:
    """Match Codex merge_base_with_head: use upstream when it is ahead of the local branch."""
    local = resolve_ref(repo, branch)
    if local is None:
        raise SystemExit(f"cannot resolve base branch {branch!r}")
    upstream = git(
        repo,
        [
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            f"{branch}@{{upstream}}",
        ],
    )
    if not upstream:
        return branch
    counts = git(repo, ["rev-list", "--left-right", "--count", f"{branch}...{upstream}"])
    if not counts:
        return branch
    parts = counts.split()
    right = int(parts[1]) if len(parts) > 1 else 0
    if right > 0 and resolve_ref(repo, upstream):
        return upstream
    return branch


def merge_base_with_head(repo: Path, branch: str) -> str | None:
    head = git(repo, ["rev-parse", "HEAD"])
    if not head:
        return None
    preferred = preferred_base_ref(repo, branch)
    preferred_sha = resolve_ref(repo, preferred)
    if preferred_sha is None:
        return None
    return git(repo, ["merge-base", head, preferred_sha])


def gh_pr_base(repo: Path) -> str | None:
    try:
        result = subprocess.run(
            ["gh", "pr", "view", "--json", "baseRefName", "-q", ".baseRefName"],
            cwd=str(repo),
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    return name or None


def ref_basename(ref: str) -> str:
    name = ref.strip()
    prefixes = (
        "refs/heads/",
        "refs/remotes/origin/",
        "refs/remotes/",
        "origin/",
    )
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix) :]
                changed = True
    return name


def same_branch_name(left: str, right: str) -> bool:
    return bool(left) and bool(right) and ref_basename(left) == ref_basename(right)


def diff_is_empty(repo: Path, merge_base_sha: str) -> bool:
    diff = git(repo, ["diff", merge_base_sha])
    return not diff


def reflog_parent(repo: Path, branch: str) -> str | None:
    log = git(repo, ["reflog", "show", branch])
    if not log:
        return None
    parent = None
    for line in log.splitlines():
        if ": branch: Created from " in line:
            source = line.split(": branch: Created from ", 1)[1].strip()
            if source and source not in {"HEAD", "refs/heads/HEAD"}:
                parent = source
        elif ": checkout: moving from " in line and f" to {branch}" in line:
            source = line.split(": checkout: moving from ", 1)[1]
            source = source.split(" to ", 1)[0].strip()
            if source and source != branch:
                parent = source
    if parent is None:
        return None
    parent = parent.removeprefix("refs/heads/").removeprefix("refs/remotes/")
    if same_branch_name(parent, branch):
        return None
    if resolve_ref(repo, parent) or resolve_ref(repo, f"origin/{parent}"):
        return parent
    return None


def origin_head(repo: Path) -> str | None:
    ref = git(repo, ["symbolic-ref", "refs/remotes/origin/HEAD"])
    if not ref:
        return None
    short = ref.removeprefix("refs/remotes/")
    return short or None


def other_branches(repo: Path, current: str) -> list[str]:
    # Local heads only. Scanning every remote ref on a large clone is too slow
    # for a fallback path; origin/HEAD is handled earlier.
    raw = git(repo, ["for-each-ref", "--format=%(refname:short)", "refs/heads"])
    if not raw:
        return []
    skip = {current, "HEAD"}
    out = []
    for name in raw.splitlines():
        name = name.strip()
        if not name or name in skip:
            continue
        out.append(name)
    return out


def closest_cut_parent(repo: Path, current: str) -> str | None:
    """Branch that shares the nearest fork point with HEAD (fewest commits unique to us)."""
    best: tuple[int, int, str] | None = None
    for name in other_branches(repo, current):
        mb = git(repo, ["merge-base", "HEAD", name])
        if not mb:
            continue
        ours = git(repo, ["rev-list", "--count", f"{mb}..HEAD"])
        theirs = git(repo, ["rev-list", "--count", f"{mb}..{name}"])
        if ours is None or theirs is None:
            continue
        ours_n = int(ours)
        if ours_n < 1:
            continue
        theirs_n = int(theirs)
        # Prefer fewer unique-to-us commits, then fewer unique-to-them (closer tip).
        key = (ours_n, theirs_n, name)
        if best is None or key < best:
            best = key
    return None if best is None else best[2]


def detect_base_branch(repo: Path) -> tuple[str, str]:
    current = current_branch(repo) or ""
    candidates: list[tuple[str, str]] = []

    pr_base = gh_pr_base(repo)
    if pr_base and not same_branch_name(pr_base, current):
        candidates.append((pr_base, "github-pr"))
    if current:
        parent = reflog_parent(repo, current)
        if parent and not same_branch_name(parent, current):
            candidates.append((parent, "reflog"))
    remote_head = origin_head(repo)
    if remote_head:
        candidates.append((remote_head, "origin-head"))
    if current:
        closest = closest_cut_parent(repo, current)
        if closest and not same_branch_name(closest, current):
            candidates.append((closest, "nearest-fork"))

    empty_fallback: tuple[str, str] | None = None
    for branch, detection in candidates:
        if resolve_ref(repo, branch) is None:
            continue
        merge_base = merge_base_with_head(repo, branch)
        if not merge_base:
            continue
        if not diff_is_empty(repo, merge_base):
            return branch, detection
        if empty_fallback is None:
            empty_fallback = (branch, detection)

    if empty_fallback:
        return empty_fallback
    raise SystemExit(
        "could not auto-detect the base branch; pass it explicitly: "
        "/codex-base-review [model] <base-branch>"
    )


def build_user_prompt(branch: str, merge_base_sha: str | None) -> str:
    if merge_base_sha:
        return USER_PROMPT.format(base_branch=branch, merge_base_sha=merge_base_sha)
    return USER_PROMPT_BACKUP.format(branch=branch)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--branch",
        help="Base branch. If omitted, auto-detect the branch this one was cut from.",
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Git work tree (default: cwd)",
    )
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    inside = git(repo, ["rev-parse", "--is-inside-work-tree"])
    if inside != "true":
        print("cwd is not a git repository", file=sys.stderr)
        return 1
    if args.branch:
        base_branch = args.branch
        detection = "explicit"
        if resolve_ref(repo, base_branch) is None:
            remote = f"origin/{base_branch}"
            if resolve_ref(repo, remote) is None:
                print(f"cannot resolve base branch {base_branch!r}", file=sys.stderr)
                return 1
            base_branch = remote
    else:
        base_branch, detection = detect_base_branch(repo)
    merge_base_sha = merge_base_with_head(repo, base_branch)
    empty = bool(merge_base_sha) and diff_is_empty(repo, merge_base_sha)
    payload = {
        "base_branch": base_branch,
        "detection": detection,
        "merge_base_sha": merge_base_sha,
        "empty": empty,
        "user_prompt": build_user_prompt(base_branch, merge_base_sha),
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
