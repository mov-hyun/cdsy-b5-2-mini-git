"""브랜치 분기, 부모 연결, 실패 시 상태 보존을 검증한다."""

import unittest
from dataclasses import FrozenInstanceError

from repository import MiniGitError, Repository


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()

    def test_commands_require_initialization(self):
        for operation in (
            lambda: self.repo.head,
            lambda: self.repo.commit("first"),
            lambda: self.repo.create_branch("feature"),
            lambda: self.repo.switch("main"),
        ):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(MiniGitError, "^Repository not initialized$"):
                    operation()
        self.assertEqual(self.repo.commits, {})

    def test_init_creates_empty_main_and_preserves_author(self):
        self.repo.initialize("Alice Kim")
        self.assertEqual(self.repo.branches, {"main": None})
        self.assertEqual(self.repo.current_branch, "main")
        self.assertEqual(self.repo.user_name, "Alice Kim")
        self.assertIsNone(self.repo.head)

    def test_invalid_author_leaves_repository_uninitialized(self):
        with self.assertRaisesRegex(MiniGitError, "^Invalid args$"):
            self.repo.initialize("  ")
        self.assertEqual(self.repo.branches, {})
        self.repo.initialize("Alice")

    def test_reinitialization_preserves_history(self):
        self.repo.initialize("Alice")
        first = self.repo.commit("first")
        with self.assertRaisesRegex(MiniGitError, "^Repository already initialized$"):
            self.repo.initialize("Bob")
        self.assertEqual(self.repo.user_name, "Alice")
        self.assertEqual(self.repo.head, first.hash)
        self.assertEqual(self.repo.commits, {first.hash: first})

    def test_first_commit_metadata_and_immutability(self):
        self.repo.initialize("Alice")
        first = self.repo.commit("Initial commit")
        self.assertEqual(first.parents, ())
        self.assertEqual(first.author, "Alice")
        self.assertEqual(first.message, "Initial commit")
        self.assertIsNotNone(first.timestamp.tzinfo)
        self.assertEqual(self.repo.head, first.hash)
        with self.assertRaises(FrozenInstanceError):
            first.message = "changed"

    def test_branching_and_switching_preserve_shared_history(self):
        self.repo.initialize("Alice")
        root = self.repo.commit("initial")
        self.repo.create_branch("feature")
        self.assertEqual(self.repo.current_branch, "main")
        self.assertEqual(self.repo.branches["feature"], root.hash)
        self.repo.switch("feature")
        feature = self.repo.commit("login")
        self.repo.switch("main")
        main = self.repo.commit("payment")
        self.assertEqual(feature.parents, (root.hash,))
        self.assertEqual(main.parents, (root.hash,))
        self.assertEqual(self.repo.branches, {"main": main.hash, "feature": feature.hash})
        self.assertEqual(self.repo.head, main.hash)
        self.assertEqual(len(self.repo.commits), 3)

    def test_branch_before_first_commit_can_form_separate_roots(self):
        self.repo.initialize("Alice")
        self.repo.create_branch("empty")
        first = self.repo.commit("main root")
        self.repo.switch("empty")
        self.assertIsNone(self.repo.head)
        second = self.repo.commit("other root")
        self.assertEqual(first.parents, ())
        self.assertEqual(second.parents, ())
        self.assertNotEqual(first.hash, second.hash)

    def test_invalid_operations_preserve_head_and_branches(self):
        self.repo.initialize("Alice")
        first = self.repo.commit("first")
        for operation, error in (
            (lambda: self.repo.create_branch("main"), "Branch already exists: main"),
            (lambda: self.repo.create_branch("bad name"), "Invalid args"),
            (lambda: self.repo.create_branch(""), "Invalid args"),
            (lambda: self.repo.switch("missing"), "Unknown branch: missing"),
            (lambda: self.repo.commit("  "), "Invalid args"),
        ):
            with self.subTest(error=error):
                with self.assertRaisesRegex(MiniGitError, f"^{error}$"):
                    operation()
                self.assertEqual(self.repo.branches, {"main": first.hash})
                self.assertEqual(len(self.repo.commits), 1)

    def test_ids_unique_and_every_parent_already_exists(self):
        self.repo.initialize("Alice")
        seen = set()
        previous = None
        for index in range(1000):
            commit = self.repo.commit(f"commit {index}")
            self.assertNotIn(commit.hash, seen)
            self.assertEqual(commit.parents, () if previous is None else (previous,))
            self.assertTrue(all(parent in seen for parent in commit.parents))
            seen.add(commit.hash)
            previous = commit.hash


if __name__ == "__main__":
    unittest.main()
