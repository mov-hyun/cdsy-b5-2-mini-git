"""따옴표 인자 파싱, 명령 실행, REPL 입출력."""

import shlex

from repository import Commit, MiniGitError, Repository


HELP = """Available commands:
  INIT <user_name>
  BRANCH <branch_name>
  SWITCH <branch_name>
  COMMIT <message>
  LOG
  LOG --sort-by=date|author
  PATH <commit1> <commit2>
  ANCESTORS <commit_hash>
  SEARCH <keyword>
  SEARCH --author=<name>
  HELP
  EXIT / QUIT
Use quotes for arguments containing spaces."""


def format_commits(commits: list[Commit]) -> str:
    """필수 필드인 hash, author, timestamp, message를 함께 출력한다."""
    if not commits:
        return "No commits"
    return "\n".join(
        f"commit {commit.hash} ({commit.author}, {commit.timestamp.isoformat()})\n"
        f"{commit.message}"
        for commit in commits
    )


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
    if command == "log":
        if not args:
            return format_commits(repository.log())
        if len(args) != 1 or args[0] not in ("--sort-by=date", "--sort-by=author"):
            raise MiniGitError("Invalid args")
        return format_commits(repository.log(sort_by=args[0].split("=", 1)[1]))
    arg_counts = {"init": 1, "branch": 1, "switch": 1, "commit": 1,
                  "path": 2, "ancestors": 1, "search": 1}
    if command not in arg_counts:
        raise MiniGitError(f"Unknown command: {tokens[0]}")
    if len(args) != arg_counts[command]:
        raise MiniGitError("Invalid args")

    if command == "path":
        path = repository.path(args[0], args[1])
        return "Path: " + "->".join(path) if path else "No path"
    if command == "ancestors":
        commits = repository.ancestors(args[0])
        return format_commits(commits) if commits else "No ancestors"
    if command == "search":
        query = args[0]
        if query.startswith("--author="):
            commits = repository.search_author(query.split("=", 1)[1])
        elif query.startswith("--"):
            raise MiniGitError("Invalid args")
        else:
            commits = repository.search_keywords(query)
        if not commits:
            return "No commits"
        label = "commit" if len(commits) == 1 else "commits"
        return f"Found {len(commits)} {label}:\n" + format_commits(commits)

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
