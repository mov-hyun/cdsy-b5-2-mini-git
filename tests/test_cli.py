"""명령 문법과 실제 진입점의 오류 복구/종료를 검증한다."""

import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from cli import execute, run
from repository import MiniGitError, Repository


class CliTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()

    def test_case_insensitive_commands_and_quoted_arguments(self):
        execute(self.repo, 'iNiT "Alice Kim"')
        output = execute(self.repo, 'CoMmIt "로그인 기능 추가"')
        self.assertEqual(output, "[main c000001] 로그인 기능 추가")
        self.assertEqual(self.repo.commits[self.repo.head].author, "Alice Kim")

    def test_branch_names_are_case_sensitive(self):
        execute(self.repo, "init Alice")
        execute(self.repo, "branch Feature")
        with self.assertRaisesRegex(MiniGitError, "^Unknown branch: feature$"):
            execute(self.repo, "switch feature")
        execute(self.repo, "switch Feature")
        self.assertEqual(self.repo.current_branch, "Feature")

    def test_invalid_arguments_and_unclosed_quotes(self):
        for line in (
            "init", "init Alice Bob", 'init ""', 'init "Alice',
            "commit", "commit unquoted message", "branch", "switch",
            "quit extra", "help extra",
        ):
            with self.subTest(line=line):
                with self.assertRaisesRegex(MiniGitError, "^Invalid args$"):
                    execute(self.repo, line)

    def test_blank_help_exit_and_unknown_command(self):
        self.assertEqual(execute(self.repo, "  "), "")
        self.assertIn("INIT", execute(self.repo, "help"))
        self.assertIsNone(execute(self.repo, "EXIT"))
        self.assertIsNone(execute(self.repo, "quit"))
        with self.assertRaisesRegex(MiniGitError, "^Unknown command: nonsense$"):
            execute(self.repo, "nonsense")

    def test_entry_point_recovers_from_errors_and_quits(self):
        result = subprocess.run(
            [sys.executable, "main.py"],
            input='commit early\ninit "Alice Kim"\ncommit "Initial commit"\n'
                  'branch feature\nswitch missing\nswitch feature\n'
                  'commit "Add login"\nswitch main\ncommit "Add payment"\nquit\n',
            text=True,
            capture_output=True,
            cwd=Path(__file__).resolve().parents[1],
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        for expected in (
            "Repository not initialized", "Current user: Alice Kim",
            "Unknown branch: missing", "[feature c000002] Add login",
            "[main c000003] Add payment", "Goodbye.",
        ):
            self.assertIn(expected, result.stdout)

    def test_eof_and_keyboard_interrupt_exit_cleanly(self):
        for signal in (EOFError, KeyboardInterrupt):
            with self.subTest(signal=signal):
                output = StringIO()
                with patch("builtins.input", side_effect=signal), redirect_stdout(output):
                    run()
                self.assertIn("Goodbye.", output.getvalue())

    def test_entry_point_graph_commands_and_error_recovery(self):
        result = subprocess.run(
            [sys.executable, "main.py"],
            input='init Alice\ncommit root\nbranch feature\nswitch feature\n'
                  'commit login\nswitch main\ncommit payment\nlog\n'
                  'path c000002 c000003\nancestors c000003\n'
                  'path c000001 missing\npath c000001 c000001\nquit\n',
            text=True, capture_output=True,
            cwd=Path(__file__).resolve().parents[1], timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        for expected in ("commit c000001 (Alice,", "commit c000002 (Alice,",
                         "commit c000003 (Alice,", "Path: c000002->c000001->c000003",
                         "Unknown commit: missing", "Path: c000001", "Goodbye."):
            self.assertIn(expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
