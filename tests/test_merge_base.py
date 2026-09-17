#!/usr/bin/env python3
"""Tests for skills/codex-base-review/scripts/merge_base.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "skills/codex-base-review/scripts/merge_base.py"


def run(cwd: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
    )


def git(cwd: Path, *args: str) -> str:
    return run(cwd, ["git", *args]).stdout.strip()


def init_repo(path: Path) -> None:
    run(path, ["git", "init", "--initial-branch=develop"])
    run(path, ["git", "config", "user.name", "Tester"])
    run(path, ["git", "config", "user.email", "test@example.com"])
    run(path, ["git", "config", "commit.gpgsign", "false"])


def helper(repo: Path, extra: list[str] | None = None) -> tuple[int, dict | str]:
    cmd = [sys.executable, str(HELPER), "--repo", str(repo)]
    if extra:
        cmd.extend(extra)
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return result.returncode, result.stderr
    return 0, json.loads(result.stdout)


class MergeBaseTests(unittest.TestCase):
    def test_checkout_of_remote_feature_skips_same_branch_reflog(self) -> None:
        """Created from origin/<same-name> is the tracking branch, not the PR base."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            origin = tmp_path / "origin.git"
            run(tmp_path, ["git", "init", "--bare", "--initial-branch=develop", str(origin)])

            seed = tmp_path / "seed"
            seed.mkdir()
            init_repo(seed)
            (seed / "app.py").write_text("safe\n", encoding="utf-8")
            run(seed, ["git", "add", "app.py"])
            run(seed, ["git", "commit", "-m", "develop: safe"])
            run(seed, ["git", "remote", "add", "origin", str(origin)])
            run(seed, ["git", "push", "-u", "origin", "develop"])
            run(seed, ["git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop"])

            run(seed, ["git", "checkout", "-b", "feature/ZFKB-529"])
            (seed / "app.py").write_text("unsafe\n", encoding="utf-8")
            run(seed, ["git", "add", "app.py"])
            run(seed, ["git", "commit", "-m", "feature: drop guard"])
            run(seed, ["git", "push", "-u", "origin", "feature/ZFKB-529"])

            work = tmp_path / "work"
            run(tmp_path, ["git", "clone", str(origin), str(work)])
            run(work, ["git", "config", "user.name", "Tester"])
            run(work, ["git", "config", "user.email", "test@example.com"])
            run(work, ["git", "checkout", "-b", "feature/ZFKB-529", "origin/feature/ZFKB-529"])

            created = git(work, "reflog", "show", "feature/ZFKB-529")
            self.assertIn("Created from", created)

            code, payload = helper(work)
            self.assertEqual(code, 0, payload)
            assert isinstance(payload, dict)
            self.assertNotEqual(
                payload["base_branch"].removeprefix("origin/"),
                "feature/ZFKB-529",
                payload,
            )
            self.assertEqual(payload["detection"], "origin-head", payload)
            self.assertFalse(payload["empty"], payload)
            self.assertIn("git diff", payload["user_prompt"])

            mb = payload["merge_base_sha"]
            diff = git(work, "diff", mb)
            self.assertIn("-safe", diff)
            self.assertIn("+unsafe", diff)

    def test_in_sync_with_default_branch_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            init_repo(repo)
            (repo / "app.py").write_text("ok\n", encoding="utf-8")
            run(repo, ["git", "add", "app.py"])
            run(repo, ["git", "commit", "-m", "develop"])

            origin = Path(tmp) / "origin.git"
            run(Path(tmp), ["git", "init", "--bare", "--initial-branch=develop", str(origin)])
            run(repo, ["git", "remote", "add", "origin", str(origin)])
            run(repo, ["git", "push", "-u", "origin", "develop"])
            run(repo, ["git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/develop"])

            code, payload = helper(repo)
            self.assertEqual(code, 0, payload)
            assert isinstance(payload, dict)
            self.assertTrue(payload["empty"], payload)
            self.assertEqual(payload["detection"], "origin-head", payload)

    def test_local_fork_without_remote_still_picks_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            run(repo, ["git", "init", "--initial-branch=main"])
            run(repo, ["git", "config", "user.name", "Tester"])
            run(repo, ["git", "config", "user.email", "test@example.com"])
            run(repo, ["git", "config", "commit.gpgsign", "false"])
            (repo / "app.py").write_text("a + b\n", encoding="utf-8")
            run(repo, ["git", "add", "app.py"])
            run(repo, ["git", "commit", "-m", "base"])
            run(repo, ["git", "checkout", "-b", "feature"])
            (repo / "app.py").write_text("a - b\n", encoding="utf-8")
            run(repo, ["git", "add", "app.py"])
            run(repo, ["git", "commit", "-m", "invert"])
            run(repo, ["git", "checkout", "main"])
            (repo / "README.md").write_text("moved\n", encoding="utf-8")
            run(repo, ["git", "add", "README.md"])
            run(repo, ["git", "commit", "-m", "main moved"])
            run(repo, ["git", "checkout", "feature"])

            code, payload = helper(repo)
            self.assertEqual(code, 0, payload)
            assert isinstance(payload, dict)
            self.assertEqual(payload["base_branch"], "main", payload)
            self.assertFalse(payload["empty"], payload)
            diff = git(repo, "diff", payload["merge_base_sha"])
            self.assertIn("a - b", diff)
            self.assertNotIn("moved", diff)


if __name__ == "__main__":
    unittest.main()
