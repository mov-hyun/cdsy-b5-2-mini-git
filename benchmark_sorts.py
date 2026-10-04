"""같은 입력에서 두 정렬을 측정하고 원시 표본과 Markdown 표를 저장한다."""

import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import random
from time import perf_counter_ns

from sorting import insertion_sort, merge_sort


SHAPES = ("random", "ordered", "reversed", "duplicates")
ALGORITHMS = (("merge", merge_sort), ("insertion", insertion_sort))


def make_input(size: int, shape: str, seed: int) -> list[int]:
    """정렬 API 없이 입력을 생성한다. 같은 인자는 같은 데이터를 만든다."""
    rng = random.Random(seed)
    if shape == "ordered":
        return list(range(size))
    if shape == "reversed":
        return list(range(size - 1, -1, -1))
    if shape == "random":
        values = list(range(size))
        rng.shuffle(values)
        return values
    if shape == "duplicates":
        return [rng.randrange(8) for _ in range(size)]
    raise ValueError(f"Unknown input shape: {shape}")


def run_benchmark(sizes: list[int], repeats: int = 5, seed: int = 20261004) -> dict:
    """입력 생성·결과 검증·출력을 제외한 정렬 호출 시간만 측정한다."""
    if not sizes or any(size <= 0 for size in sizes) or repeats <= 0:
        raise ValueError("Sizes and repeats must be positive")
    rows = []
    for shape in SHAPES:
        for size in sizes:
            values = make_input(size, shape, seed + size)
            original = list(values)
            expected = Counter(values)
            samples = {name: [] for name, _ in ALGORITHMS}

            def check(result):
                if values != original or Counter(result) != expected:
                    raise AssertionError("Sort modified its input or lost elements")
                if any(left > right for left, right in zip(result, result[1:])):
                    raise AssertionError("Sort returned an unordered result")

            def key(value):
                return value

            # 각 입력·알고리즘을 한 번 예열한 뒤 측정한다.
            for _, algorithm in ALGORITHMS:
                check(algorithm(values, key=key))
            for repeat in range(repeats):
                # 먼저 실행되는 알고리즘을 번갈아 배치한다.
                order = ALGORITHMS if repeat % 2 == 0 else ALGORITHMS[::-1]
                for name, algorithm in order:
                    start = perf_counter_ns()
                    result = algorithm(values, key=key)
                    elapsed = perf_counter_ns() - start
                    samples[name].append(elapsed)
                    check(result)
                    del result  # 반환 목록 해제 비용도 다음 측정 구간에서 제외한다.
            rows.append({
                "shape": shape, "size": size, "samples_ns": samples,
                "mean_ms": {name: sum(times) / len(times) / 1_000_000
                            for name, times in samples.items()},
            })
    return {
        "environment": {"python": platform.python_version(),
                        "implementation": platform.python_implementation(),
                        "system": platform.system(), "architecture": platform.machine()},
        "method": {"seed": seed, "sizes": sizes, "repeats": repeats,
                   "warmups_per_case": 1, "timer": "perf_counter_ns",
                   "statistic": "arithmetic_mean", "input": "integer lists",
                   "execution_order": "alternating", "output_validation": "every run"},
        "results": rows,
    }


def render_report(report: dict) -> str:
    """측정값으로 사람이 읽을 수 있는 표를 만든다. 표준 정렬 API는 쓰지 않는다."""
    env, method = report["environment"], report["method"]
    lines = [
        "# Sorting benchmark", "",
        f"Environment: {env['implementation']} {env['python']}, {env['system']} {env['architecture']}.",
        f"Seed: {method['seed']}. Warmups per case: {method['warmups_per_case']}. "
        f"Measured runs per algorithm and case: {method['repeats']}.",
        "Timing: arithmetic mean in milliseconds; perf_counter_ns; alternating algorithm order.",
        "Inputs: integer lists. Data generation, output validation and I/O are outside timing.",
        "Each timed call includes input copying, key calculation and sorting.", "",
        "| Input | n | Merge mean (ms) | Insertion mean (ms) | Insertion / merge |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in report["results"]:
        merge, insertion = row["mean_ms"]["merge"], row["mean_ms"]["insertion"]
        ratio = f"{insertion / merge:.2f}x" if merge else "n/a"
        lines.append(f"| {row['shape']} | {row['size']} | {merge:.6f} | {insertion:.6f} | {ratio} |")
    lines.extend(["", "Raw samples are stored in the adjacent JSON file.",
                  "These are local measurements, not general performance guarantees or full LOG timings.", ""])
    return "\n".join(lines)


def positive_int(value: str) -> int:
    """CLI의 입력 크기와 반복 횟수는 양수로 제한한다."""
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main() -> None:
    """예: python benchmark_sorts.py --sizes 100 500 1000 2000 4000 --repeats 5."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=positive_int, nargs="+", default=[100, 500, 1000, 2000, 4000])
    parser.add_argument("--repeats", type=positive_int, default=5)
    parser.add_argument("--seed", type=int, default=20261004)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/sort_results.json"))
    args = parser.parse_args()
    if args.output.suffix.lower() != ".json":
        parser.error("--output must end in .json")
    report = run_benchmark(args.sizes, args.repeats, args.seed)
    markdown = render_report(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
