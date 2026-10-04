"""LCS 기반 diff의 복원·최소 편집 수, 파일 입력, REPL 오류 복구를 검증한다."""

from itertools import product
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from cli import execute, parse_tokens
from diffing import DiffError, diff_files, diff_lines, read_lines
from repository import MiniGitError, Repository


def exhaustive_lcs_length(before, after):
    """작은 입력의 부분 수열을 열거하는 DP와 독립적인 검증 기준."""
    best = 0
    for mask in range(1 << len(before)):
        candidate = [value for i, value in enumerate(before) if mask & (1 << i)]
        cursor = 0
        for value in after:
            if cursor < len(candidate) and value == candidate[cursor]:
                cursor += 1
        if cursor == len(candidate):
            best = max(best, len(candidate))
    return best


class DiffAlgorithmTests(unittest.TestCase):
    def test_empty_identical_addition_and_deletion(self):
        self.assertEqual(diff_lines([], []), [])
        self.assertEqual(diff_lines(["a", ""], ["a", ""]), [(" ", "a"), (" ", "")])
        self.assertEqual(diff_lines([], ["a", "b"]), [("+", "a"), ("+", "b")])
        self.assertEqual(diff_lines(["a", "b"], []), [("-", "a"), ("-", "b")])

    def test_replacement_and_common_lines(self):
        self.assertEqual(diff_lines(["head", "old", "tail"], ["head", "new", "tail", "extra"]),
                         [(" ", "head"), ("-", "old"), ("+", "new"),
                          (" ", "tail"), ("+", "extra")])

    def test_repeated_lines_and_tie_choose_deletion_first(self):
        self.assertEqual(diff_lines(["a", "b"], ["b", "a"]),
                         [("-", "a"), (" ", "b"), ("+", "a")])
        self.assertEqual(diff_lines(["a", "a", "b"], ["a", "b", "b"]),
                         [(" ", "a"), ("-", "a"), (" ", "b"), ("+", "b")])

    def test_whitespace_and_unicode_are_significant_and_inputs_unchanged(self):
        before = ["로그인", " a", "b ", ""]
        after = ["로그인", "a", "b ", ""]
        before_copy, after_copy = list(before), list(after)
        self.assertEqual(diff_lines(before, after),
                         [(" ", "로그인"), ("-", " a"), ("+", "a"), (" ", "b "), (" ", "")])
        self.assertEqual(before, before_copy)
        self.assertEqual(after, after_copy)

    def test_exhaustive_small_inputs_reconstruct_both_files_with_minimal_edits(self):
        sequences = [list(values) for size in range(5) for values in product("ab", repeat=size)]
        for before in sequences:
            for after in sequences:
                with self.subTest(before=before, after=after):
                    changes = diff_lines(before, after)
                    self.assertEqual([line for marker, line in changes if marker != "+"], before)
                    self.assertEqual([line for marker, line in changes if marker != "-"], after)
                    edits = sum(marker != " " for marker, _ in changes)
                    self.assertEqual(edits, len(before) + len(after) - 2 * exhaustive_lcs_length(before, after))


class DiffFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.before = self.root / "before file.txt"
        self.after = self.root / "after file.txt"

    def test_bom_newline_style_and_final_newline_normalization(self):
        self.before.write_bytes(b"\xef\xbb\xbfhead\r\ntail\r\n")
        self.after.write_bytes(b"head\ntail")
        original = self.before.read_bytes(), self.after.read_bytes()
        self.assertEqual(diff_files(str(self.before), str(self.after)), [(" ", "head"), (" ", "tail")])
        self.assertEqual((self.before.read_bytes(), self.after.read_bytes()), original)

    def test_empty_file_diff_and_same_file(self):
        self.before.write_text("", encoding="utf-8")
        self.assertEqual(diff_files(str(self.before), str(self.before)), [])
        self.before.write_text("한글\n", encoding="utf-8")
        self.assertEqual(diff_files(str(self.before), str(self.before)), [(" ", "한글")])

    def test_missing_directory_encoding_and_permission_errors(self):
        with self.assertRaisesRegex(DiffError, "^File not found:"):
            read_lines(str(self.before))
        with self.assertRaisesRegex(DiffError, "^Not a file:"):
            read_lines(str(self.root))
        self.before.write_bytes(b"\xff\xfeinvalid")
        with self.assertRaisesRegex(DiffError, "^Invalid UTF-8 file:"):
            read_lines(str(self.before))
        with patch.object(Path, "read_text", side_effect=PermissionError):
            with self.assertRaisesRegex(DiffError, "^Cannot read file:"):
                read_lines(str(self.before))

    def test_missing_second_file_reports_error(self):
        self.before.write_text("a\n", encoding="utf-8")
        with self.assertRaisesRegex(DiffError, "^File not found:"):
            diff_files(str(self.before), str(self.after))

    def test_diff_without_init_with_spaced_paths_and_after_init_preserves_state(self):
        self.before.write_text("a\nold\n", encoding="utf-8")
        self.after.write_text("a\nnew\n", encoding="utf-8")
        command = f'dIfF "{self.before}" "{self.after}"'
        repo = Repository()
        self.assertEqual(execute(repo, command), "  a\n- old\n+ new")
        self.assertIsNone(repo.current_branch)
        repo.initialize("Alice")
        commit = repo.commit("root")
        self.assertEqual(execute(repo, command), "  a\n- old\n+ new")
        self.assertEqual(repo.commits, {commit.hash: commit})
        self.assertEqual(repo.branches, {"main": commit.hash})
        self.assertEqual(repo.search_keywords("root"), [commit])

    def test_invalid_arguments_and_empty_files_output(self):
        repo = Repository()
        for command in ("diff", "diff one", "diff one two three", 'diff "" two',
                        'diff one "  "', 'diff "unclosed'):
            with self.subTest(command=command):
                with self.assertRaisesRegex(MiniGitError, "^Invalid args$"):
                    execute(repo, command)
        self.before.write_text("", encoding="utf-8")
        self.assertEqual(execute(repo, f'diff "{self.before}" "{self.before}"'), "No lines")

    def test_windows_paths_keep_backslashes_and_other_command_escapes_still_work(self):
        self.assertEqual(parse_tokens(r'diff folder\before.txt folder\after.txt'),
                         ["diff", "folder\\before.txt", "folder\\after.txt"])
        self.assertEqual(parse_tokens(r'DIFF "folder name\before.txt" "folder name\after.txt"'),
                         ["DIFF", "folder name\\before.txt", "folder name\\after.txt"])
        self.assertEqual(parse_tokens(r'commit "Say \"hello\""'), ["commit", 'Say "hello"'])

    def test_real_cli_relative_paths_read_error_recovery_and_file_preservation(self):
        self.before.write_text("a\nold\n", encoding="utf-8")
        self.after.write_text("a\nnew\n", encoding="utf-8")
        original = self.before.read_bytes(), self.after.read_bytes()
        entry = Path(__file__).resolve().parents[1] / "main.py"
        result = subprocess.run(
            [sys.executable, str(entry)], cwd=self.root,
            input='diff missing.txt "after file.txt"\ndiff "before file.txt" "after file.txt"\n'
                  'init Alice\ncommit root\nquit\n',
            text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        for expected in ("File not found: missing.txt", "  a\n- old\n+ new",
                         "[main c000001] root", "Goodbye."):
            self.assertIn(expected, result.stdout)
        self.assertEqual((self.before.read_bytes(), self.after.read_bytes()), original)


if __name__ == "__main__":
    unittest.main()
