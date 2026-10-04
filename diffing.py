"""최장 공통 부분 수열(LCS)을 직접 계산하는 줄 단위 텍스트 비교."""

from pathlib import Path


class DiffError(ValueError):
    """파일 읽기에 실패했을 때 CLI에 표시할 오류."""


def diff_lines(before: list[str], after: list[str]) -> list[tuple[str, str]]:
    """공통(' '), 삭제('-'), 추가('+') 줄을 순서대로 반환한다.

    suffix별 LCS 길이를 동적 계획법으로 구한 뒤 편집 순서를 복원한다.
    삭제/추가 선택의 LCS 길이가 같으면 삭제를 먼저 선택한다.
    두 입력의 줄 수가 n, m일 때 DP 시간·공간은 O(nm)이다.
    """
    n, m = len(before), len(after)
    lengths = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if before[i] == after[j]:
                lengths[i][j] = 1 + lengths[i + 1][j + 1]
            else:
                lengths[i][j] = max(lengths[i + 1][j], lengths[i][j + 1])

    changes = []
    i = j = 0
    while i < n and j < m:
        if before[i] == after[j]:
            changes.append((" ", before[i]))
            i += 1
            j += 1
        elif lengths[i + 1][j] >= lengths[i][j + 1]:
            changes.append(("-", before[i]))
            i += 1
        else:
            changes.append(("+", after[j]))
            j += 1
    changes.extend(("-", line) for line in before[i:])
    changes.extend(("+", line) for line in after[j:])
    return changes


def read_lines(file_name: str) -> list[str]:
    """UTF-8(BOM 허용) 파일의 줄을 읽는다. 줄바꿈 문자는 비교에서 제외한다."""
    path = Path(file_name)
    try:
        if path.is_dir():
            raise DiffError(f"Not a file: {file_name}")
        return path.read_text(encoding="utf-8-sig").splitlines()
    except DiffError:
        raise
    except FileNotFoundError as error:
        raise DiffError(f"File not found: {file_name}") from error
    except UnicodeError as error:
        raise DiffError(f"Invalid UTF-8 file: {file_name}") from error
    except (OSError, ValueError) as error:
        raise DiffError(f"Cannot read file: {file_name}") from error


def diff_files(before_path: str, after_path: str) -> list[tuple[str, str]]:
    """두 파일을 읽어서 비교한다. 파일과 저장소 상태는 변경하지 않는다."""
    return diff_lines(read_lines(before_path), read_lines(after_path))
