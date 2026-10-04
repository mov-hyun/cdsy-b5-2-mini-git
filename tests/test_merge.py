"""실제 MERGE 명령으로 다중 부모 DAG를 만들고 기존 기능과 함께 검증한다."""

import subprocess
import sys
import unittest
from pathlib import Path

from cli import execute
from repository import MiniGitError, Repository


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()

    def diverge(self):
        """공통 루트에서 main과 feature가 각각 전진한 이력을 만든다."""
        self.repo.initialize("Alice")
        root = self.repo.commit("initial")
        self.repo.create_branch("feature")
        self.repo.switch("feature")
        feature = self.repo.commit("login feature")
        self.repo.switch("main")
        main = self.repo.commit("payment feature")
        return root, feature, main

    def snapshot(self):
        """공개 상태와 인덱스를 복사해 실패/조회가 데이터를 바꾸는지 확인한다."""
        return (
            dict(self.repo.commits), dict(self.repo.branches), self.repo.current_branch,
            self.repo.user_name,
            {key: list(values) for key, values in self.repo.index.keywords.items()},
            {key: list(values) for key, values in self.repo.index.authors.items()},
        )

    def test_two_parents_and_only_current_branch_moves(self):
        root, feature, main = self.diverge()
        merged = self.repo.merge("feature")
        self.assertEqual(merged.parents, (main.hash, feature.hash))
        self.assertEqual(merged.message, "Merge branch 'feature' into 'main'")
        self.assertEqual(merged.author, "Alice")
        self.assertIsNotNone(merged.timestamp.tzinfo)
        self.assertEqual(self.repo.branches, {"main": merged.hash, "feature": feature.hash})
        self.assertEqual(self.repo.current_branch, "main")
        self.assertEqual(self.repo.head, merged.hash)
        self.assertEqual(self.repo.commits[root.hash], root)
        self.assertEqual(self.repo.commits[main.hash], main)
        self.assertEqual(self.repo.commits[feature.hash], feature)
        self.assertEqual(len(self.repo.commits), 4)

    def test_merged_diamond_topology_ancestors_and_lexical_path(self):
        root, feature, main = self.diverge()
        merged = self.repo.merge("feature")
        before = self.snapshot()
        log = self.repo.log()
        positions = {commit.hash: index for index, commit in enumerate(log)}
        for commit in log:
            for parent in commit.parents:
                self.assertLess(positions[parent], positions[commit.hash])
        ancestors = self.repo.ancestors(merged.hash)
        self.assertEqual({commit.hash for commit in ancestors}, {root.hash, feature.hash, main.hash})
        self.assertEqual(len(ancestors), 3)
        self.assertEqual(self.repo.path(merged.hash, root.hash),
                         [merged.hash, feature.hash, root.hash])
        self.assertEqual(self.repo.path(feature.hash, main.hash),
                         [feature.hash, root.hash, main.hash])
        self.assertEqual(self.snapshot(), before)

    def test_merge_updates_both_indexes_and_sorted_logs(self):
        self.diverge()
        # 작성자 변경은 테스트 데이터 구성용이며 CLI 기능이 아니다.
        self.repo.user_name = "Merger"
        merged = self.repo.merge("feature")
        self.assertEqual(self.repo.search_keywords("MERGE"), [merged])
        self.assertEqual(self.repo.search_keywords("merge branch"), [merged])
        self.assertEqual(self.repo.search_author("Merger"), [merged])
        self.assertIn(merged, self.repo.log("date"))
        self.assertEqual(self.repo.log("author")[-1], merged)

    def test_normal_commit_after_merge_uses_merge_as_single_parent(self):
        self.diverge()
        merged = self.repo.merge("feature")
        next_commit = self.repo.commit("after merge")
        self.assertEqual(next_commit.parents, (merged.hash,))
        self.assertEqual(next_commit.hash, "c000005")
        self.assertEqual(len(self.repo.ancestors(next_commit.hash)), 4)

    def test_independent_roots_become_connected(self):
        self.repo.initialize("Alice")
        self.repo.create_branch("other")
        main = self.repo.commit("main root")
        self.repo.switch("other")
        other = self.repo.commit("other root")
        self.repo.switch("main")
        self.assertEqual(self.repo.path(main.hash, other.hash), [])
        merged = self.repo.merge("other")
        self.assertEqual(merged.parents, (main.hash, other.hash))
        self.assertEqual(self.repo.path(main.hash, other.hash),
                         [main.hash, merged.hash, other.hash])

    def test_ancestor_related_tips_still_create_two_parent_commit(self):
        for advance_feature in (False, True):
            with self.subTest(advance_feature=advance_feature):
                repo = Repository()
                repo.initialize("Alice")
                root = repo.commit("root")
                repo.create_branch("feature")
                if advance_feature:
                    repo.switch("feature")
                child = repo.commit("child")
                repo.switch("main")
                merged = repo.merge("feature")
                expected = (root.hash, child.hash) if advance_feature else (child.hash, root.hash)
                self.assertEqual(merged.parents, expected)
                self.assertEqual(len(repo.commits), 3)

    def test_invalid_merges_preserve_state_and_do_not_consume_hash(self):
        self.diverge()
        self.repo.create_branch("same")
        before = self.snapshot()
        for name, error in (
            ("missing", "Unknown branch: missing"),
            ("main", "Cannot merge current branch"),
            ("same", "Branches point to same commit"),
            ("Feature", "Unknown branch: Feature"),
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(MiniGitError, f"^{error}$"):
                    self.repo.merge(name)
                self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.repo.merge("feature").hash, "c000004")

    def test_empty_target_and_current_branch_are_rejected(self):
        self.repo.initialize("Alice")
        self.repo.create_branch("empty")
        self.repo.commit("root")
        for current, target in (("main", "empty"), ("empty", "main")):
            self.repo.switch(current)
            before = self.snapshot()
            with self.assertRaisesRegex(MiniGitError, "^Cannot merge empty branch: empty$"):
                self.repo.merge(target)
            self.assertEqual(self.snapshot(), before)

    def test_cli_initialization_arguments_and_case(self):
        with self.assertRaisesRegex(MiniGitError, "^Repository not initialized$"):
            execute(self.repo, "merge feature")
        for line in ("merge", "merge feature extra", 'merge "feature'):
            with self.subTest(line=line):
                with self.assertRaisesRegex(MiniGitError, "^Invalid args$"):
                    execute(self.repo, line)
        self.diverge()
        self.assertEqual(execute(self.repo, "MeRgE feature"),
                         "[main c000004] Merge branch 'feature' into 'main'")

    def test_real_cli_merge_graph_search_and_error_recovery(self):
        commands = [
            "init Alice", "commit root", "branch feature", "switch feature",
            "commit login", "switch main", "commit payment", "merge missing",
            "merge feature", "log", "ancestors c000004", "path c000004 c000001",
            "search merge", "log --sort-by=author", "merge main", "commit followup", "quit",
        ]
        result = subprocess.run(
            [sys.executable, "main.py"], input="\n".join(commands) + "\n",
            cwd=Path(__file__).resolve().parents[1], text=True,
            capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        output = [part.strip() for part in result.stdout.split("mini-git> ")[1:]]
        self.assertEqual(len(output), len(commands))
        self.assertEqual(output[7], "Unknown branch: missing")
        self.assertEqual(output[8], "[main c000004] Merge branch 'feature' into 'main'")
        for position in (9, 13):
            hashes = [line.split()[1] for line in output[position].splitlines()
                      if line.startswith("commit ")]
            self.assertEqual(hashes, ["c000001", "c000002", "c000003", "c000004"])
        self.assertEqual(output[11], "Path: c000004->c000002->c000001")
        self.assertTrue(output[12].startswith("Found 1 commit:"))
        self.assertEqual(output[14], "Cannot merge current branch")
        self.assertEqual(output[15], "[main c000005] followup")
        self.assertEqual(output[16], "Goodbye.")


if __name__ == "__main__":
    unittest.main()
