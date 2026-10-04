"""커밋과 브랜치를 메모리에서 관리하는 Mini Git의 핵심 모델."""

from dataclasses import dataclass
from datetime import datetime, timezone

import graph
from indexing import InvertedIndex
from sorting import merge_sort


class MiniGitError(ValueError):
    """CLI에 그대로 표시할 수 있는 사용자 입력/상태 오류."""


@dataclass(frozen=True)
class Commit:
    """한 번 생성하면 바뀌지 않는 커밋 메타데이터와 부모 연결."""

    hash: str
    message: str
    author: str
    timestamp: datetime
    parents: tuple[str, ...]


class Repository:
    """커밋은 hash로 찾고, 브랜치는 자신의 마지막 커밋 hash를 가리킨다."""

    def __init__(self) -> None:
        self.commits: dict[str, Commit] = {}
        self.branches: dict[str, str | None] = {}
        self.current_branch: str | None = None
        self.user_name: str | None = None
        self.index = InvertedIndex()
        self._next_id = 1

    def _require_initialized(self) -> None:
        """INIT 이전의 저장소 작업을 거부한다."""
        if self.current_branch is None:
            raise MiniGitError("Repository not initialized")

    @property
    def head(self) -> str | None:
        """현재 브랜치의 끝 커밋. 첫 커밋 전에는 None이다."""
        self._require_initialized()
        return self.branches[self.current_branch]

    def initialize(self, user_name: str) -> None:
        """main 브랜치와 작성자를 설정한다. 재초기화는 기존 기록을 보호한다."""
        if not user_name.strip():
            raise MiniGitError("Invalid args")
        if self.current_branch is not None:
            raise MiniGitError("Repository already initialized")
        self.user_name = user_name
        self.branches["main"] = None
        self.current_branch = "main"

    def create_branch(self, name: str) -> None:
        """현재 커밋을 가리키는 브랜치를 만든다. 작업 브랜치는 유지한다."""
        self._require_initialized()
        if not name or any(character.isspace() for character in name):
            raise MiniGitError("Invalid args")
        if name in self.branches:
            raise MiniGitError(f"Branch already exists: {name}")
        self.branches[name] = self.head

    def switch(self, name: str) -> None:
        """존재하는 브랜치를 현재 작업 위치로 선택한다."""
        self._require_initialized()
        if name not in self.branches:
            raise MiniGitError(f"Unknown branch: {name}")
        self.current_branch = name

    def commit(self, message: str) -> Commit:
        """현재 HEAD를 부모로 커밋을 만들고 현재 브랜치만 전진시킨다."""
        self._require_initialized()
        if not message.strip():
            raise MiniGitError("Invalid args")
        parent = self.head
        commit_hash = f"c{self._next_id:06d}"
        new_commit = Commit(
            hash=commit_hash,
            message=message,
            author=self.user_name,
            timestamp=datetime.now(timezone.utc),
            parents=() if parent is None else (parent,),
        )
        self.commits[commit_hash] = new_commit
        self.index.add(new_commit)
        self.branches[self.current_branch] = commit_hash
        self._next_id += 1
        return new_commit

    def get_commit(self, commit_hash: str) -> Commit:
        """초기화 여부와 hash를 검사하고 커밋을 반환한다."""
        self._require_initialized()
        if commit_hash not in self.commits:
            raise MiniGitError(f"Unknown commit: {commit_hash}")
        return self.commits[commit_hash]

    def log(self, sort_by: str | None = None) -> list[Commit]:
        """기본은 부모 우선, 옵션 지정 시 해당 키의 안정 오름차순이다."""
        self._require_initialized()
        if sort_by is None:
            return [self.commits[key] for key in graph.topological_order(self.commits)]
        if sort_by == "date":
            key = lambda commit: commit.timestamp
        elif sort_by == "author":
            key = lambda commit: commit.author
        else:
            raise MiniGitError("Invalid args")
        # dict의 삽입 순서가 커밋 생성 순서이며, 동률에서는 이 순서를 유지한다.
        return merge_sort(list(self.commits.values()), key=key)

    def path(self, start: str, end: str) -> list[str]:
        """존재하는 두 커밋의 무방향 최단 경로를 반환한다."""
        self.get_commit(start)
        self.get_commit(end)
        return graph.shortest_path(self.commits, start, end)

    def ancestors(self, commit_hash: str) -> list[Commit]:
        """시작 커밋을 제외한 모든 조상을 반환한다."""
        self.get_commit(commit_hash)
        return [self.commits[key] for key in graph.ancestors(self.commits, commit_hash)]

    def search_keywords(self, query: str) -> list[Commit]:
        """메시지 역색인에서 찾은 hash만 저장소에서 조회한다."""
        self._require_initialized()
        if not query.strip():
            raise MiniGitError("Invalid args")
        return [self.commits[key] for key in self.index.search_keywords(query)]

    def search_author(self, name: str) -> list[Commit]:
        """작성자 역색인에서 찾은 hash만 저장소에서 조회한다."""
        self._require_initialized()
        if not name.strip():
            raise MiniGitError("Invalid args")
        return [self.commits[key] for key in self.index.search_author(name)]
