"""정렬의 순서·보존·안정성 및 날짜/작성자 로그 연결을 검증한다."""

import random
import unittest
from collections import Counter
from datetime import datetime, timezone
from unittest.mock import patch

from cli import execute
from repository import MiniGitError, Repository
from sorting import merge_sort


class MergeSortTests(unittest.TestCase):
    def test_empty_single_sorted_reverse_and_duplicates(self):
        cases = [([], []), ([7], [7]), ([1, 2, 3], [1, 2, 3]),
                 ([5, 4, 3, 2, 1], [1, 2, 3, 4, 5]),
                 ([3, -1, 3, 0, -1], [-1, -1, 0, 3, 3])]
        for original, expected in cases:
            with self.subTest(original=original):
                before = list(original)
                result = merge_sort(original, key=lambda value: value)
                self.assertEqual(result, expected)
                self.assertEqual(original, before)
                self.assertIsNot(result, original)

    def test_equal_keys_preserve_order_across_merge_boundaries(self):
        rows = [{"group": group, "id": index}
                for index, group in enumerate([2, 1, 2, 1, 1, 2, 1])]
        result = merge_sort(rows, key=lambda row: row["group"])
        self.assertEqual([row["id"] for row in result], [1, 3, 4, 6, 0, 2, 5])
        self.assertIs(result[0], rows[1])
        self.assertEqual([row["id"] for row in rows], list(range(7)))

    def test_key_changes_comparison_and_is_evaluated_once_per_item(self):
        values = ["bbb", "a", "cc", "d"]
        calls = []

        def length(value):
            calls.append(value)
            return len(value)

        self.assertEqual(merge_sort(values, key=length), ["a", "d", "cc", "bbb"])
        self.assertEqual(calls, values)
        self.assertEqual(merge_sort(values, key=lambda value: value),
                         ["a", "bbb", "cc", "d"])

    def test_seeded_inputs_preserve_elements_order_and_stability(self):
        rng = random.Random(20261004)
        for size in (0, 1, 2, 3, 7, 16, 31, 100, 257, 2049):
            with self.subTest(size=size):
                rows = [(rng.randrange(-10, 11), index) for index in range(size)]
                result = merge_sort(rows, key=lambda row: row[0])
                self.assertEqual(Counter(result), Counter(rows))
                for previous, current in zip(result, result[1:]):
                    self.assertLessEqual(previous[0], current[0])
                    if previous[0] == current[0]:
                        self.assertLess(previous[1], current[1])


class SortedLogTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()

    def build_history(self):
        """테스트에서 작성자/시각을 제어해 생성 순서와 정렬 순서를 다르게 한다."""
        self.repo.initialize("Zoe")
        commits = []
        with patch("repository.datetime") as clock:
            for author, day, message in (
                ("Zoe", 2, "root"), ("Bob", 1, "login feature"),
                ("Alice", 1, "payment feature"), ("Bob", 3, "login fix"),
            ):
                self.repo.user_name = author
                clock.now.return_value = datetime(2026, 1, day, tzinfo=timezone.utc)
                commits.append(self.repo.commit(message))
        return commits

    def test_dates_use_timestamp_and_preserve_equal_date_creation_order(self):
        commits = self.build_history()
        self.assertEqual(self.repo.log("date"), [commits[1], commits[2], commits[0], commits[3]])

    def test_authors_preserve_equal_author_creation_order(self):
        commits = self.build_history()
        self.assertEqual(self.repo.log("author"), [commits[2], commits[1], commits[3], commits[0]])

    def test_sort_queries_preserve_graph_search_and_default_log(self):
        commits = self.build_history()
        original_branches = dict(self.repo.branches)
        original_commits = dict(self.repo.commits)
        for option in ("date", "author"):
            self.repo.log(option).clear()
        self.assertEqual(self.repo.log(), commits)
        self.assertEqual(self.repo.commits, original_commits)
        self.assertEqual(self.repo.branches, original_branches)
        self.assertEqual(self.repo.current_branch, "main")
        self.assertEqual(self.repo.search_keywords("login"), [commits[1], commits[3]])
        self.assertEqual(self.repo.search_author("Bob"), [commits[1], commits[3]])
        self.assertEqual(self.repo.path(commits[0].hash, commits[3].hash),
                         [commit.hash for commit in commits])
        self.assertEqual({commit.hash for commit in self.repo.ancestors(commits[3].hash)},
                         {commit.hash for commit in commits[:3]})

    def test_cli_dispatches_both_sort_options(self):
        commits = self.build_history()
        for option, expected in (("date", [1, 2, 0, 3]), ("author", [2, 1, 3, 0])):
            output = execute(self.repo, f"LoG --sort-by={option}")
            hashes = [line.split()[1] for line in output.splitlines()
                      if line.startswith("commit ")]
            self.assertEqual(hashes, [commits[index].hash for index in expected])

    def test_sorted_log_includes_other_branches_and_independent_roots(self):
        self.repo.initialize("Zoe")
        self.repo.create_branch("other")
        first = self.repo.commit("first root")
        self.repo.switch("other")
        self.repo.user_name = "Alice"
        second = self.repo.commit("second root")
        self.assertEqual(self.repo.log("author"), [second, first])

    def test_author_order_is_case_sensitive_unicode_order(self):
        self.repo.initialize("a")
        commits = []
        for name in ("a", "Z", "가", "A"):
            self.repo.user_name = name
            commits.append(self.repo.commit(name))
        self.assertEqual(self.repo.log("author"), [commits[3], commits[1], commits[0], commits[2]])

    def test_empty_logs_initialization_and_invalid_options(self):
        for option in ("date", "author"):
            with self.assertRaisesRegex(MiniGitError, "^Repository not initialized$"):
                execute(self.repo, f"log --sort-by={option}")
        self.repo.initialize("Alice")
        for option in ("date", "author"):
            self.assertEqual(execute(self.repo, f"log --sort-by={option}"), "No commits")
        for line in ("log --sort-by=", "log --sort-by=hash", "log --sort-by=DATE",
                     "log --SORT-BY=date", "log --sort-by date",
                     "log --sort-by=date extra", "log --sort-by=date --sort-by=author"):
            with self.subTest(line=line):
                with self.assertRaisesRegex(MiniGitError, "^Invalid args$"):
                    execute(self.repo, line)
        with self.assertRaisesRegex(MiniGitError, "^Invalid args$"):
            self.repo.log("unknown")


if __name__ == "__main__":
    unittest.main()
