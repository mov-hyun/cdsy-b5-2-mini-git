"""메시지 토큰과 작성자를 커밋 hash 목록에 연결하는 역색인."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from repository import Commit


class InvertedIndex:
    """커밋 생성 순서를 유지하는 keyword/author 인덱스."""

    def __init__(self) -> None:
        self.keywords: dict[str, list[str]] = {}
        self.authors: dict[str, list[str]] = {}

    def add(self, commit: Commit) -> None:
        """새 커밋을 한 번 등록한다. 메시지의 중복 토큰은 한 번만 기록한다."""
        for token in dict.fromkeys(commit.message.lower().split()):
            self.keywords.setdefault(token, []).append(commit.hash)
        self.authors.setdefault(commit.author, []).append(commit.hash)

    def search_keywords(self, query: str) -> list[str]:
        """질의의 모든 토큰이 있는 커밋을 생성 순서로 반환한다(AND 검색)."""
        tokens = list(dict.fromkeys(query.lower().split()))
        if not tokens:
            return []

        postings = []
        for token in tokens:
            posting = self.keywords.get(token)
            if posting is None:
                return []
            postings.append(posting)
        if len(postings) == 1:
            return list(postings[0])

        # 가장 짧은 후보 목록을 순회하며 나머지 토큰의 후보 집합과 교차한다.
        smallest = 0
        for index in range(1, len(postings)):
            if len(postings[index]) < len(postings[smallest]):
                smallest = index
        other_sets = [set(posting) for index, posting in enumerate(postings)
                      if index != smallest]
        return [commit_hash for commit_hash in postings[smallest]
                if all(commit_hash in candidates for candidates in other_sets)]

    def search_author(self, name: str) -> list[str]:
        """작성자 이름이 정확히 일치하는 커밋을 반환한다."""
        return list(self.authors.get(name, []))
