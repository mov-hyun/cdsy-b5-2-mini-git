"""따옴표 인자 파싱, 명령 실행, REPL 입출력."""

import shlex

from repository import MiniGitError, Repository


HELP = """Available commands (stage 1):
  INIT <user_name>
  BRANCH <branch_name>
  SWITCH <branch_name>
  COMMIT <message>
  HELP
  EXIT / QUIT
Use quotes for arguments containing spaces."""


def execute(repository: Repository, line: str) -> str | None:
    """한 명령을 실행한다. 문자열은 출력, None은 정상 종료를 의미한다."""
    try:
        tokens = shlex.split(line)
    except ValueError as error:
        raise MiniGitError("Invalid args") from error
    if not tokens:
        return ""

    command = tokens[0].lower()
    args = tokens[1:]
    if command in ("exit", "quit", "help"):
        if args:
            raise MiniGitError("Invalid args")
        return HELP if command == "help" else None
    if command not in ("init", "branch", "switch", "commit"):
        raise MiniGitError(f"Unknown command: {tokens[0]}")
    if len(args) != 1:
        raise MiniGitError("Invalid args")

    value = args[0]
    if command == "init":
        repository.initialize(value)
        return (
            "Initialized repository.\n"
            "Current branch: main\n"
            f"Current user: {repository.user_name}"
        )
    if command == "branch":
        repository.create_branch(value)
        return f"Created branch: {value}"
    if command == "switch":
        repository.switch(value)
        return f"Switched to branch: {value}"

    new_commit = repository.commit(value)
    return f"[{repository.current_branch} {new_commit.hash}] {new_commit.message}"


def run() -> None:
    """오류가 나면 메시지를 출력하고 다음 명령을 계속 받는다."""
    repository = Repository()
    print("Mini Git - type HELP for commands, QUIT to exit.")
    while True:
        try:
            line = input("mini-git> ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        try:
            result = execute(repository, line)
        except MiniGitError as error:
            print(error)
            continue
        if result is None:
            print("Goodbye.")
            break
        if result:
            print(result)
