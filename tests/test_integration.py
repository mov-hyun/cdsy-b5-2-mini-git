"""필수 명령의 실제 실행 흐름과 과제의 코드 제약을 확인한다."""

import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def test_all_required_commands_in_one_real_cli_session(self):
        commands = [
            'init "Alice Kim"', 'commit "Initial commit"', 'branch feature',
            'switch feature', 'commit "Add login feature"', 'switch main',
            'commit "Add payment feature"', 'log', 'path c000002 c000003',
            'ancestors c000003', 'search login', 'search --author="Alice Kim"',
            'log --sort-by=date', 'log --sort-by=author', 'log --sort-by=unknown',
            'search "login feature"', 'quit',
        ]
        result = subprocess.run(
            [sys.executable, "main.py"], input="\n".join(commands) + "\n",
            cwd=ROOT, text=True, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        output = [part.strip() for part in result.stdout.split("mini-git> ")[1:]]
        self.assertEqual(len(output), len(commands))
        self.assertIn("Current user: Alice Kim", output[0])
        self.assertEqual(output[8], "Path: c000002->c000001->c000003")
        self.assertIn("commit c000001", output[9])
        self.assertNotIn("commit c000002", output[9])
        self.assertNotIn("commit c000003", output[9])
        for position in (7, 12, 13):
            hashes = [line.split()[1] for line in output[position].splitlines()
                      if line.startswith("commit ")]
            self.assertEqual(hashes, ["c000001", "c000002", "c000003"])
        for position in (10, 15):
            self.assertTrue(output[position].startswith("Found 1 commit:"))
            self.assertIn("commit c000002", output[position])
        self.assertTrue(output[11].startswith("Found 3 commits:"))
        self.assertEqual(output[14], "Invalid args")
        self.assertEqual(output[16], "Goodbye.")

    def test_unicode_cli_with_utf8_pipes_and_eof(self):
        result = subprocess.run(
            [sys.executable, "main.py"],
            input='init "김 개발"\ncommit "로그인 기능 추가"\n'
                  'search "로그인 기능"\nsearch --author="김 개발"\nlog --sort-by=author\n',
            cwd=ROOT, text=True, encoding="utf-8", capture_output=True, timeout=10,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("김 개발", result.stdout)
        self.assertIn("로그인 기능 추가", result.stdout)
        self.assertEqual(result.stdout.count("Found 1 commit:"), 2)
        self.assertIn("Goodbye.", result.stdout)

    def test_source_constraints_and_python_310_syntax(self):
        sources = list(ROOT.glob("*.py"))
        allowed_imports = sys.stdlib_module_names | {path.stem for path in sources}
        for path in sources:
            with self.subTest(file=path.name):
                # 문법 호환 확인이며 Python 3.10의 실제 실행 검증은 아니다.
                tree = ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 10))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name):
                            self.assertNotEqual(node.func.id, "sorted")
                        elif isinstance(node.func, ast.Attribute):
                            self.assertNotIn(node.func.attr, {"sort", "sorted"})
                    if isinstance(node, ast.Import):
                        modules = [alias.name.split(".")[0] for alias in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        modules = [node.module.split(".")[0]]
                    else:
                        modules = []
                    for module in modules:
                        self.assertIn(module, allowed_imports)
                        self.assertNotIn(module, {"graphlib", "heapq", "bisect"})


if __name__ == "__main__":
    unittest.main()
