import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "collect_pr_context.py"
SPEC = importlib.util.spec_from_file_location("collect_pr_context", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
collect_pr_context = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collect_pr_context)


def run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


class CollectPrContextTests(unittest.TestCase):
    def init_repo(self, root: Path, branch: str = "main") -> None:
        run(["git", "init", "-q", "-b", branch], cwd=root)
        run(["git", "config", "user.email", "test@example.com"], cwd=root)
        run(["git", "config", "user.name", "Test User"], cwd=root)

    def commit_file(self, root: Path, relative_path: str, content: str, message: str) -> None:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        run(["git", "add", relative_path], cwd=root)
        run(["git", "commit", "-qm", message], cwd=root)

    def test_resolve_auto_base_falls_back_to_head_without_parent_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            self.init_repo(repo, branch="feature")
            self.commit_file(repo, "README.md", "hello\n", "init")

            self.assertEqual(collect_pr_context.resolve_auto_base(repo), "HEAD")
            self.assertEqual(
                collect_pr_context.resolve_range_commit_spec(repo, "HEAD", "HEAD"),
                ("HEAD", "HEAD"),
            )
            self.assertEqual(
                collect_pr_context.collect_changed_files(repo, "range", "HEAD"),
                [
                    {
                        "status": "A",
                        "status_code": "A",
                        "path": "README.md",
                        "additions": 1,
                        "deletions": 0,
                        "category": "docs",
                    }
                ],
            )

    def test_resolve_auto_base_prefers_common_default_branch_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            self.init_repo(repo, branch="develop")
            self.commit_file(repo, "README.md", "base\n", "init")
            run(["git", "checkout", "-qb", "feature/review-helper"], cwd=repo)
            self.commit_file(repo, "src/tool.py", "print('tool')\n", "add tool")

            self.assertEqual(collect_pr_context.resolve_auto_base(repo), "develop")

    def test_resolve_auto_base_raises_when_branch_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            self.init_repo(repo, branch="release")
            self.commit_file(repo, "README.md", "base\n", "init")
            run(["git", "checkout", "-qb", "feature/review-helper"], cwd=repo)
            self.commit_file(repo, "src/tool.py", "print('tool')\n", "add tool")
            run(["git", "checkout", "-qb", "staging", "release"], cwd=repo)
            run(["git", "checkout", "feature/review-helper"], cwd=repo)

            with self.assertRaisesRegex(RuntimeError, "pass --base explicitly"):
                collect_pr_context.resolve_auto_base(repo)

    def test_working_tree_mode_includes_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            self.init_repo(repo)
            self.commit_file(repo, "tracked.txt", "tracked\n", "init")
            (repo / "new_file.py").write_text("print('hi')\nprint('bye')\n")

            changed_files = collect_pr_context.collect_changed_files(repo, "working-tree", None)

            self.assertIn(
                {
                    "status": "?",
                    "status_code": "??",
                    "path": "new_file.py",
                    "additions": 2,
                    "deletions": 0,
                    "category": "source",
                },
                changed_files,
            )
            payload = collect_pr_context.build_payload(
                repo_root=repo,
                mode="working-tree",
                base_ref="INDEX",
                head_ref="WORKTREE",
                merge_base=None,
                commit_range=None,
                max_commits=10,
                max_hotspots=10,
            )
            self.assertEqual(payload["diff_stats"]["additions"], 2)
            self.assertEqual(payload["hotspots"][0]["path"], "new_file.py")

    def test_matches_test_requires_path_component_match_for_parent_name(self) -> None:
        self.assertFalse(
            collect_pr_context.matches_test("src/auth/login.py", "tests/oauth/test_flow.py")
        )
        self.assertFalse(
            collect_pr_context.matches_test("src/user.py", "tests/test_superuser.py")
        )
        self.assertTrue(
            collect_pr_context.matches_test("src/auth/login.py", "tests/auth/test_flow.py")
        )
        self.assertTrue(
            collect_pr_context.matches_test("src/user.ts", "tests/user.test.ts")
        )


if __name__ == "__main__":
    unittest.main()
