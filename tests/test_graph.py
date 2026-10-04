"""삽입 순서와 무관한 위상 정렬, 최단 경로 동률, 다중 부모를 검증한다."""

import random
import unittest
from datetime import datetime, timezone

import graph
from cli import execute
from repository import Commit, MiniGitError, Repository


def make_commits(parents):
    """명령으로 아직 만들 수 없는 다중 부모 DAG도 테스트용으로 구성한다."""
    return {
        key: Commit(key, f"message {key}", "Alice",
                    datetime(2026, 1, 1, tzinfo=timezone.utc), tuple(values))
        for key, values in parents.items()
    }


def exhaustive_path(parents, start, end):
    """작은 그래프의 모든 단순 경로를 열거하는 독립 비교 기준."""
    neighbors = {key: set(values) for key, values in parents.items()}
    for key, values in parents.items():
        for parent in values:
            neighbors[parent].add(key)
    best = []
    stack = [[start]]
    while stack:
        path = stack.pop()
        if path[-1] == end:
            if not best or (len(path), "->".join(path)) < (len(best), "->".join(best)):
                best = path
            continue
        for neighbor in neighbors[path[-1]]:
            if neighbor not in path:
                stack.append(path + [neighbor])
    return best


class GraphTests(unittest.TestCase):
    def test_topology_handles_merge_and_shuffled_insertion_order(self):
        commits = make_commits({
            "c4": ["c2", "c3"], "c3": ["c1"], "c5": [],
            "c1": [], "c2": ["c1"],
        })
        result = graph.topological_order(commits)
        positions = {key: index for index, key in enumerate(result)}
        self.assertEqual(set(result), set(commits))
        self.assertEqual(len(result), len(commits))
        for key, commit in commits.items():
            for parent in commit.parents:
                self.assertLess(positions[parent], positions[key])

    def test_empty_topology_and_invalid_graphs(self):
        self.assertEqual(graph.topological_order({}), [])
        with self.assertRaisesRegex(ValueError, "cycle"):
            graph.topological_order(make_commits({"c1": ["c2"], "c2": ["c1"]}))
        with self.assertRaisesRegex(ValueError, "unknown parent"):
            graph.topological_order(make_commits({"c1": ["missing"]}))

    def test_path_travels_up_and_down_between_branches(self):
        commits = make_commits({"c1": [], "c2": ["c1"], "c3": ["c1"]})
        self.assertEqual(graph.shortest_path(commits, "c2", "c3"), ["c2", "c1", "c3"])
        self.assertEqual(graph.shortest_path(commits, "c3", "c2"), ["c3", "c1", "c2"])

    def test_path_prefers_shorter_route_before_lexical_order(self):
        commits = make_commits({
            "c0": [], "c1": ["c0"], "c2": ["c1"], "c9": ["c0", "c2"],
        })
        self.assertEqual(graph.shortest_path(commits, "c0", "c9"), ["c0", "c9"])

    def test_lexical_tie_ignores_parent_and_insertion_order(self):
        commits = make_commits({
            "c0": [], "c9": ["c0"], "c1": ["c0"], "c8": ["c9", "c1"],
        })
        self.assertEqual(graph.shortest_path(commits, "c0", "c8"), ["c0", "c1", "c8"])
        self.assertEqual(graph.shortest_path(commits, "c8", "c0"), ["c8", "c1", "c0"])

    def test_lexical_tie_with_shared_prefix_and_variable_length_ids(self):
        commits = make_commits({
            "c0": [], "c8": ["c0"], "c10": ["c8"], "c1": ["c8"],
            "c9": ["c10", "c1"],
        })
        self.assertEqual(graph.shortest_path(commits, "c0", "c9"),
                         ["c0", "c8", "c1", "c9"])

    def test_same_commit_and_disconnected_roots(self):
        commits = make_commits({"c1": [], "c2": []})
        self.assertEqual(graph.shortest_path(commits, "c1", "c1"), ["c1"])
        self.assertEqual(graph.shortest_path(commits, "c1", "c2"), [])

    def test_ancestors_deduplicates_merge_and_excludes_siblings(self):
        commits = make_commits({
            "c1": [], "c2": ["c1"], "c3": ["c1"],
            "c4": ["c2", "c3"], "c5": ["c1"],
        })
        result = graph.ancestors(commits, "c4")
        self.assertEqual(set(result), {"c1", "c2", "c3"})
        self.assertEqual(len(result), 3)
        self.assertEqual(graph.ancestors(commits, "c1"), [])

    def test_deep_history_avoids_python_recursion_limit(self):
        parents = {f"c{index}": [] if index == 0 else [f"c{index - 1}"]
                   for index in range(2500)}
        commits = make_commits(parents)
        self.assertEqual(len(graph.topological_order(commits)), 2500)
        self.assertEqual(len(graph.ancestors(commits, "c2499")), 2499)
        self.assertEqual(len(graph.shortest_path(commits, "c0", "c2499")), 2500)

    def test_seeded_dags_match_exhaustive_shortest_path_reference(self):
        rng = random.Random(20261004)
        names = ["c9", "c1", "c10", "c2", "c8", "c0"]
        for case in range(25):
            parents = {name: [previous for previous in names[:index] if rng.random() < 0.4]
                       for index, name in enumerate(names)}
            commits = make_commits(parents)
            for start in names:
                for end in names:
                    with self.subTest(case=case, start=start, end=end):
                        self.assertEqual(graph.shortest_path(commits, start, end),
                                         exhaustive_path(parents, start, end))


class GraphCommandTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repository()

    def test_graph_commands_before_init_and_bad_argument_counts(self):
        for line in ("log", "path c1 c2", "ancestors c1"):
            with self.subTest(line=line):
                with self.assertRaisesRegex(MiniGitError, "^Repository not initialized$"):
                    execute(self.repo, line)
        for line in ("log extra", "path", "path c1", "path c1 c2 c3",
                     "ancestors", "ancestors c1 c2"):
            with self.subTest(line=line):
                with self.assertRaisesRegex(MiniGitError, "^Invalid args$"):
                    execute(self.repo, line)

    def test_empty_log_unknown_hashes_and_root_ancestors(self):
        execute(self.repo, "init Alice")
        self.assertEqual(execute(self.repo, "log"), "No commits")
        execute(self.repo, "commit root")
        self.assertEqual(execute(self.repo, "ancestors c000001"), "No ancestors")
        for line in ("path missing c000001", "path c000001 missing",
                     "path missing missing", "ancestors missing"):
            with self.subTest(line=line):
                with self.assertRaisesRegex(MiniGitError, "^Unknown commit: missing$"):
                    execute(self.repo, line)

    def test_log_covers_all_branches_and_queries_do_not_move_head(self):
        for line in ("init Alice", "commit root", "branch feature", "switch feature",
                     "commit login", "switch main", "commit payment"):
            execute(self.repo, line)
        before = dict(self.repo.branches)
        output = execute(self.repo, "LOG")
        for key in ("c000001", "c000002", "c000003"):
            self.assertIn(key, output)
        self.assertLess(output.index("c000001"), output.index("c000002"))
        self.assertLess(output.index("c000001"), output.index("c000003"))
        self.assertIn("Alice", output)
        self.assertIn(self.repo.commits["c000001"].timestamp.isoformat(), output)
        self.assertEqual(execute(self.repo, "PATH c000002 c000003"),
                         "Path: c000002->c000001->c000003")
        ancestors = execute(self.repo, "ANCESTORS c000003")
        self.assertIn("c000001", ancestors)
        self.assertNotIn("c000002", ancestors)
        self.assertEqual(self.repo.branches, before)
        self.assertEqual(self.repo.current_branch, "main")

    def test_disconnected_branches_print_no_path(self):
        for line in ("init Alice", "branch empty", "commit root", "switch empty",
                     "commit other"):
            execute(self.repo, line)
        self.assertEqual(execute(self.repo, "path c000001 c000002"), "No path")


if __name__ == "__main__":
    unittest.main()
