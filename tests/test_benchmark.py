"""벤치마크 재현 설정·기록 계산·실행을 검증한다. 속도 우열은 단언하지 않는다."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from benchmark_sorts import make_input, render_report, run_benchmark


class BenchmarkTests(unittest.TestCase):
    def test_input_shapes_and_seed_reproducibility(self):
        self.assertEqual(make_input(4, "ordered", 1), [0, 1, 2, 3])
        self.assertEqual(make_input(4, "reversed", 1), [3, 2, 1, 0])
        self.assertEqual(make_input(20, "random", 42), make_input(20, "random", 42))
        self.assertEqual(set(make_input(20, "random", 42)), set(range(20)))
        self.assertTrue(all(0 <= value < 8 for value in make_input(20, "duplicates", 42)))
        with self.assertRaises(ValueError):
            make_input(4, "unknown", 1)

    def test_report_has_all_cases_samples_and_matching_means(self):
        report = run_benchmark([3, 7], repeats=2, seed=42)
        self.assertEqual(len(report["results"]), 8)
        self.assertEqual(report["method"]["seed"], 42)
        for row in report["results"]:
            for algorithm in ("merge", "insertion"):
                samples = row["samples_ns"][algorithm]
                self.assertEqual(len(samples), 2)
                self.assertTrue(all(sample >= 0 for sample in samples))
                self.assertAlmostEqual(row["mean_ms"][algorithm], sum(samples) / 2 / 1_000_000)
        self.assertIn("Insertion / merge", render_report(report))

    def test_invalid_measurement_settings(self):
        for sizes, repeats in (([], 2), ([0], 2), ([-1], 2), ([4], 0)):
            with self.subTest(sizes=sizes, repeats=repeats):
                with self.assertRaises(ValueError):
                    run_benchmark(sizes, repeats)

    def test_cli_saves_raw_json_and_readable_report(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            result = subprocess.run(
                [sys.executable, "benchmark_sorts.py", "--sizes", "4", "8",
                 "--repeats", "2", "--output", str(output)],
                cwd=root, text=True, capture_output=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(report["results"]), 8)
            self.assertEqual(output.with_suffix(".md").read_text(encoding="utf-8"), render_report(report))
            self.assertIn("Sorting benchmark", result.stdout)


if __name__ == "__main__":
    unittest.main()
