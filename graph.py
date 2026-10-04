"""커밋 그래프의 위상 정렬, 무방향 최단 경로, 조상 탐색."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repository import Commit


def _children(commits: dict[str, Commit]) -> dict[str, list[str]]:
    """부모 -> 자식 연결을 만든다. 저장된 자식 -> 부모 연결의 역방향이다."""
    children = {commit_hash: [] for commit_hash in commits}
    for commit_hash, commit in commits.items():
        for parent in commit.parents:
            if parent not in commits:
                raise ValueError(f"Invalid commit graph: unknown parent {parent}")
            children[parent].append(commit_hash)
    return children


def topological_order(commits: dict[str, Commit]) -> list[str]:
    """Kahn 알고리즘으로 모든 부모가 자식보다 먼저 나오는 순서를 만든다."""
    children = _children(commits)
    remaining = {key: len(commit.parents) for key, commit in commits.items()}
    ready = [key for key in commits if remaining[key] == 0]
    cursor = 0
    while cursor < len(ready):
        current = ready[cursor]
        cursor += 1
        for child in children[current]:
            remaining[child] -= 1
            if remaining[child] == 0:
                ready.append(child)
    if len(ready) != len(commits):
        raise ValueError("Invalid commit graph: cycle")
    return ready


def shortest_path(commits: dict[str, Commit], start: str, end: str) -> list[str]:
    """BFS 거리에서 최단 경로를 복원한다. hash는 저장소의 c+숫자 형식이다.

    남은 거리가 1 감소하는 이웃만 선택하고, 다음 'hash->' 토큰을
    비교한다. hash에 구분자 '->'가 없으므로 첫 상이한 토큰의 순서가
    전체 경로 문자열의 순서다. 모든 경로를 열거할 필요가 없다.
    """
    # 조회는 start == end인 경우에도 두 hash의 존재를 확인한다.
    commits[start]
    commits[end]
    if start == end:
        return [start]

    neighbors = _children(commits)
    for key, commit in commits.items():
        neighbors[key].extend(commit.parents)

    distance = {end: 0}
    queue = [end]
    cursor = 0
    while cursor < len(queue):
        current = queue[cursor]
        cursor += 1
        for neighbor in neighbors[current]:
            if neighbor not in distance:
                distance[neighbor] = distance[current] + 1
                queue.append(neighbor)
    if start not in distance:
        return []

    path = [start]
    current = start
    while current != end:
        next_commit = None
        next_token = None
        for neighbor in neighbors[current]:
            if distance.get(neighbor) != distance[current] - 1:
                continue
            token = neighbor if neighbor == end else neighbor + "->"
            if next_token is None or token < next_token:
                next_commit = neighbor
                next_token = token
        # BFS로 도달 가능함을 확인했으므로 거리가 1 작은 이웃이 반드시 있다.
        assert next_commit is not None
        path.append(next_commit)
        current = next_commit
    return path


def ancestors(commits: dict[str, Commit], commit_hash: str) -> list[str]:
    """반복형 DFS로 모든 조상을 한 번씩 찾는다. 시작 커밋은 제외한다."""
    stack = [commit_hash]
    visited = {commit_hash}
    result = []
    while stack:
        current = stack.pop()
        for parent in commits[current].parents:
            if parent not in visited:
                visited.add(parent)
                result.append(parent)
                stack.append(parent)
    return result
