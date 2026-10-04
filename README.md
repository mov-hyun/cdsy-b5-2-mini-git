# Mini Git

Codyssey B5-2 자료구조와 알고리즘 과제. Python CLI에서 커밋 메타데이터와 브랜치를 관리하고, 그래프 탐색·역색인 검색·직접 구현한 정렬을 단계별로 추가한다.

## 현재 진행 상태

**1단계: 커밋 모델, 브랜치 관리, 기본 CLI 구현. 전체 과제는 진행 중이다.**

- [x] INIT / BRANCH / SWITCH / COMMIT
- [x] 따옴표 인자, 명령어 대소문자 무시, 오류 복구, exit / quit
- [ ] 부모가 먼저 출력되는 LOG
- [ ] 무방향 최단 경로 PATH 및 사전순 동률 처리
- [ ] 모든 조상 탐색 ANCESTORS
- [ ] keyword / author 역색인과 SEARCH
- [ ] 직접 구현한 정렬과 LOG --sort-by=date|author
- [ ] 전체 요구사항 검증 및 알고리즘 복잡도 설명

보너스 후보: 줄 단위 diff, 두 부모를 갖는 merge, 정렬 알고리즘 성능 비교.

## 실행

Python 3.10 이상. 외부 패키지 설치 없이 표준 라이브러리만 사용한다.

```sh
python main.py
```

```text
mini-git> init "Alice Kim"
Initialized repository.
Current branch: main
Current user: Alice Kim
mini-git> commit "Initial commit"
[main c000001] Initial commit
mini-git> branch feature
Created branch: feature
mini-git> switch feature
Switched to branch: feature
mini-git> commit "Add login feature"
[feature c000002] Add login feature
mini-git> switch main
Switched to branch: main
mini-git> commit "Add payment feature"
[main c000003] Add payment feature
mini-git> quit
Goodbye.
```

`help`로 현재 구현한 명령을 확인한다. 공백이 포함된 작성자·메시지는 따옴표로 감싼다. 명령 이름만 대소문자를 무시하며, 작성자·메시지·브랜치 이름은 입력을 유지한다.

## 1단계 구조

| 파일 | 역할 |
| --- | --- |
| `main.py` | 실행 진입점 |
| `cli.py` | 문자열 파싱, 명령 전달, 출력과 REPL |
| `repository.py` | Commit 모델, 저장소, 브랜치와 HEAD 관리 |
| `tests/` | 모델 동작, 잘못된 입력, 실제 CLI 실행 검증 |

`commits`는 `hash -> Commit`, `branches`는 `branch_name -> commit_hash` 형태의 dict다. 첫 커밋 전 브랜치 값은 `None`이다. `current_branch`가 HEAD의 브랜치 이름을 보관하고, `head` 속성이 그 브랜치의 끝 커밋 hash를 반환한다.

커밋은 hash, message, author, timestamp, parents를 가진다. 변경 불가능한 dataclass와 부모 tuple을 사용한다. 생성 시각은 시간대가 명시된 UTC다. hash는 세션 내 증가 카운터(`c000001`, `c000002`, ...)로 만들며, 6자리는 최소 숫자 폭이다. 숫자가 커져도 잘라내지 않는다.

예시 실행 후 부모 연결은 다음과 같다. 화살표는 자식에서 부모 방향이다.

```text
c000002 -> c000001 <- c000003
feature -> c000002
main    -> c000003
HEAD    -> main
```

새 커밋은 이미 존재하는 현재 HEAD만 부모로 삼는다. 기존 커밋의 부모는 바꾸지 않으므로 이 명령들로 순환을 만들 수 없다. 브랜치를 만들 때 커밋을 복사하지 않으며 현재 브랜치도 바뀌지 않는다. COMMIT은 현재 브랜치만 새 커밋으로 옮긴다.

## 현재 적용한 입력·상태 정책

- INIT 전 저장소 명령: `Repository not initialized`.
- 반복 INIT: `Repository already initialized`. 기존 이력을 보존한다.
- 비어 있거나 공백뿐인 작성자·메시지: `Invalid args`.
- 브랜치명: 공백 없는 비어 있지 않은 문자열. 중복 생성은 `Branch already exists: <name>`.
- 없는 브랜치 전환: `Unknown branch: <name>`.
- 인자 개수 오류·닫히지 않은 따옴표: `Invalid args`.
- 알 수 없는 명령: `Unknown command: <name>`.
- 첫 커밋 전 브랜치 생성 허용. 각 빈 브랜치에서 첫 커밋을 만들면 서로 연결되지 않은 루트가 생긴다.
- exit / quit, EOF, 입력 대기 중 Ctrl+C로 종료한다.
- 메모리에서만 동작한다. 실제 파일 내용 추적, 원격 통신, 데이터 영속성은 구현하지 않는다.

## 다음 단계

1. 그래프 탐색: 전체 저장소의 부모 우선 LOG, PATH, ANCESTORS.
2. 검색: 메시지 `split()` + `lower()` 토큰과 작성자 역색인을 커밋 생성에 연결.
3. 정렬: 정렬 알고리즘을 직접 구현하고 날짜·작성자 기준 로그에 연결.
4. 통합 검증: DAG, 최단 경로 동률, 검색 결과, 정렬 안정성·복잡도 설명.

아직 구현하지 않은 명령은 사용할 수 없다. 현재 COMMIT에는 역색인 갱신이 포함되지 않았으며 검색 단계에서 추가한다. 그래프 전용 라이브러리와 표준 정렬 API는 사용하지 않는다.

## 테스트

```sh
python -m unittest discover -s tests -v
```

공통 조상에서 브랜치가 분기하는 시나리오, 빈 브랜치의 독립 루트, 오류 시 상태 보존, 1,000개 커밋의 hash 유일성과 부모 연결, 실제 `main.py` 프로세스의 오류 복구·종료를 검증한다.

1단계 검증 결과: Python 3.12.14에서 테스트 15개 통과. Python 3.10 환경의 실제 실행은 아직 검증하지 않았다.
