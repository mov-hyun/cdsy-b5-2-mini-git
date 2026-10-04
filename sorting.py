"""표준 정렬 API 없이 구현한 안정 병합 정렬."""

from typing import Any, Callable, TypeVar


T = TypeVar("T")


def merge_sort(items: list[T], key: Callable[[T], Any]) -> list[T]:
    """key 오름차순의 새 목록을 반환한다. 동률은 입력 순서를 유지한다.

    길이 1인 구간부터 인접 구간을 병합하며 길이를 두 배씩 늘린다.
    시간은 평균/최악 O(n log n), 보조 공간은 O(n)이다.
    비교 키는 항목당 한 번 계산하며 입력 목록은 변경하지 않는다.
    """
    source = [(key(item), item) for item in items]
    target = list(source)
    size = len(source)
    width = 1
    while width < size:
        for start in range(0, size, width * 2):
            middle = min(start + width, size)
            end = min(start + width * 2, size)
            left, right = start, middle
            for output in range(start, end):
                # 오른쪽 키가 더 작을 때만 오른쪽을 먼저 쓴다.
                # 동률이면 왼쪽을 선택하므로 기존 순서가 유지된다.
                if right < end and (left >= middle or source[right][0] < source[left][0]):
                    target[output] = source[right]
                    right += 1
                else:
                    target[output] = source[left]
                    left += 1
        source, target = target, source
        width *= 2
    return [item for _, item in source]
