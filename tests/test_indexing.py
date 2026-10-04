"""역색인 결과, 중복 제거, CLI 문법과 전체 순회 없는 조회를 검증한다."""

import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cli import execute
from indexing import InvertedIndex
from repository import Commit, MiniGitError, Repository


def make_commit(commit_hash, message, author="Alice Kim"):
    """서로 다른 작성자의 커밋을 인덱스 테스트에 제공한다."""
    return Commit(commit_hash, message, author, datetime.now(timezone.utc), ())


class DirectLookupOnly(dict):
    """전체 저장소 순회는 실패시키고 hash별 직접 조회 횟수를 기록한다."""

    def __init__(self, commits):
        super().__init__(commits)
        self.lookups = []

    def __getitem__(self, key):
        self.lookups.append(key)
        return super().__getitem__(key)

    def __iter__(self):
        raise AssertionError("Search must not iterate over all commits")

    def keys(self):
        raise AssertionError("Search must not scan all keys")

    def values(self):
        raise AssertionError("Search must not scan all values")

    def items(self):
        raise AssertionError("Search must not scan all items")


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.index = InvertedIndex()

    def test_normalization_whitespace_and_duplicate_tokens(self):
        self.index.add(make_commit("c1", "Login LOGIN\tlogin\nfeature"))
        self.assertEqual(self.index.search_keywords("LOGIN"), ["c1"])
        self.assertEqual(self.index.keywords["login"], ["c1"])
        self.assertEqual(self.index.search_keywords("login LOGIN"), ["c1"])
        self.assertEqual(self.index.search_keywords(" \tFEATURE\n login "), ["c1"])

    def test_exact_tokens_preserve_punctuation_and_korean(self):
        self.index.add(make_commit("c1", "Login, 로그인 기능"))
        self.assertEqual(self.index.search_keywords("login"), [])
        self.assertEqual(self.index.search_keywords("log"), [])
        self.assertEqual(self.index.search_keywords("LOGIN,"), ["c1"])
        self.assertEqual(self.index.search_keywords("로그인 기능"), ["c1"])

    def test_multiple_tokens_use_intersection_in_creation_order(self):
        for key, message in (("c9", "login"), ("c8", "login feature"),
                             ("c2", "feature"), ("c1", "feature login")):
            self.index.add(make_commit(key, message))
        self.assertEqual(self.index.search_keywords("login feature"), ["c8", "c1"])
        self.assertEqual(self.index.search_keywords("feature login"), ["c8", "c1"])
        self.assertEqual(self.index.search_keywords("feature missing"), [])

    def test_author_is_exact_and_separate_from_message_tokens(self):
        self.index.add(make_commit("c1", "Bob mentioned", "Alice Kim"))
        self.index.add(make_commit("c2", "Alice mentioned", "Bob"))
        self.index.add(make_commit("c3", "follow-up", "Alice Kim"))
        self.assertEqual(self.index.search_author("Alice Kim"), ["c1", "c3"])
        self.assertEqual(self.index.search_author("Bob"), ["c2"])
        self.assertEqual(self.index.search_author("alice kim"), [])
        self.assertEqual(self.index.search_author("Alice"), [])
        self.assertEqual(self.index.search_keywords("Bob"), ["c1"])

    def test_unknown_query_does_not_create_buckets_or_expose_internal_lists(self):
        self.assertEqual(self.index.search_keywords("missing"), [])
        self.assertEqual(self.index.search_keywords("  "), [])
        self.assertEqual(self.index.search_author("missing"), [])
        self.assertEqual(self.index.keywords, {})
        self.assertEqual(self.index.authors, {})
        self.index.add(make_commit("c1", "login"))
        self.index.search_keywords("login").clear()
        self.index.search_author("Alice Kim").clear()
        self.assertEqual(self.index.search_keywords("login"), ["c1"])
        self.assertEqual(self.index.search_author("Alice Kim"), ["c1"])


class SearchCommandTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()

    def test_search_requires_initialization_and_valid_arguments(self):
        for line in ("search login", "search --author=Alice"):
            with self.subTest(line=line):
                with self.assertRaisesRegex(MiniGitError, "^Repository not initialized$"):
                    execute(self.repo, line)
        execute(self.repo, "init Alice")
        for line in ("search", "search login feature", 'search ""', 'search "  "',
                     "search --author=", 'search --author="  "', "search --author Alice",
                     "search --unknown=Alice", "search --AUTHOR=Alice", 'search "login'):
            with self.subTest(line=line):
                with self.assertRaisesRegex(MiniGitError, "^Invalid args$"):
                    execute(self.repo, line)

    def test_search_empty_and_missing_results(self):
        execute(self.repo, "init Alice")
        self.assertEqual(execute(self.repo, "search login"), "No commits")
        self.assertEqual(execute(self.repo, "search --author=Alice"), "No commits")
        execute(self.repo, "commit login")
        self.assertEqual(execute(self.repo, "search missing"), "No commits")
        self.assertEqual(execute(self.repo, "search --author=Bob"), "No commits")

    def test_commit_updates_both_indexes_across_branches(self):
        for line in ('init "Alice Kim"', 'commit "Initial commit"', "branch feature",
                     "switch feature", 'commit "Add login feature"', "switch main",
                     'commit "Add payment feature"'):
            execute(self.repo, line)
        before = dict(self.repo.branches)
        result = execute(self.repo, "SeArCh LOGIN")
        self.assertIn("Found 1 commit:", result)
        self.assertIn("c000002", result)
        self.assertIn("Add login feature", result)
        self.assertNotIn("c000003", result)
        self.assertIn("Found 2 commits:", execute(self.repo, "search feature"))
        self.assertIn("Found 3 commits:", execute(self.repo, 'search --author="Alice Kim"'))
        self.assertEqual(execute(self.repo, 'search --author="alice kim"'), "No commits")
        self.assertIn("c000002", execute(self.repo, 'search "login feature"'))
        self.assertEqual(self.repo.branches, before)
        self.assertEqual(self.repo.current_branch, "main")

    def test_failed_commit_and_reinit_leave_indexes_unchanged(self):
        self.repo.initialize("Alice")
        first = self.repo.commit("login")
        with self.assertRaises(MiniGitError):
            self.repo.commit(" ")
        with self.assertRaises(MiniGitError):
            self.repo.initialize("Bob")
        self.assertEqual(self.repo.index.keywords, {"login": [first.hash]})
        self.assertEqual(self.repo.index.authors, {"Alice": [first.hash]})

    def test_keyword_and_author_search_only_lookup_matching_commits(self):
        self.repo.initialize("Alice")
        for index in range(1000):
            self.repo.commit(f"common message {index}")
        # 여러 작성자 검증용 상태 구성. CLI의 작성자 변경 명령은 추가하지 않는다.
        self.repo.user_name = "Target Author"
        target = self.repo.commit("common rare")
        guarded = DirectLookupOnly(self.repo.commits)
        self.repo.commits = guarded
        for operation in (
            lambda: self.repo.search_keywords("rare"),
            lambda: self.repo.search_keywords("common rare"),
            lambda: self.repo.search_author("Target Author"),
        ):
            guarded.lookups.clear()
            self.assertEqual(operation(), [target])
            self.assertEqual(guarded.lookups, [target.hash])
        guarded.lookups.clear()
        self.assertEqual(self.repo.search_keywords("missing"), [])
        self.assertEqual(self.repo.search_author("missing"), [])
        self.assertEqual(guarded.lookups, [])

    def test_author_value_can_contain_equals_sign(self):
        execute(self.repo, 'init "Alice=Team"')
        execute(self.repo, "commit root")
        self.assertIn("Found 1 commit:", execute(self.repo, "search --author=Alice=Team"))

    def test_entry_point_search_and_error_recovery(self):
        result = subprocess.run(
            [sys.executable, "main.py"],
            input='init "Alice Kim"\ncommit "Add Login feature"\n'
                  'commit "Add payment feature"\nsearch LOGIN\n'
                  'search --author="Alice Kim"\nsearch "login feature"\n'
                  'search --author=\nsearch missing\nquit\n',
            text=True, capture_output=True,
            cwd=Path(__file__).resolve().parents[1], timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        for expected in ("Found 1 commit:", "Found 2 commits:",
                         "Invalid args", "No commits", "Goodbye."):
            self.assertIn(expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
