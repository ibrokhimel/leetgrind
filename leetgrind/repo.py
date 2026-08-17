import subprocess
from pathlib import Path

GITIGNORE = "__pycache__/\n.pytest_cache/\n.lc/\n*.pyc\n"
GITATTRIBUTES = "* text=auto eol=lf\n"


class GitError(Exception):
    """A git invocation failed."""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").is_dir():
        git(repo, "init", "-q", "--initial-branch", "main")
    (repo / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (repo / ".gitattributes").write_text(GITATTRIBUTES, encoding="utf-8")


def identity(repo: Path) -> tuple[str, str]:
    try:
        return git(repo, "config", "user.name"), git(repo, "config", "user.email")
    except GitError:
        return "", ""


def commit_paths(repo: Path, paths: list[Path], message: str) -> bool:
    spec = [str(p) for p in paths]
    for path in spec:
        git(repo, "add", "--", path)
    if not git(repo, "diff", "--cached", "--name-only", "--", *spec):
        return False
    # Scope the commit to the paths we just staged. `git commit` with no
    # pathspec commits the *whole* index, so anything undo_last's `reset
    # --soft` left staged would ride along into the next problem's Start
    # commit - a mislabelled commit in the user's public history.
    git(repo, "commit", "-q", "-m", message, "--", *spec)
    return True


def current_branch(repo: Path) -> str:
    """The checked-out branch, defaulting to main on a detached/empty HEAD."""
    try:
        return git(repo, "branch", "--show-current") or "main"
    except GitError:
        return "main"


def remote_url(repo: Path) -> str:
    """The URL of `origin`, or "" when no remote is configured."""
    try:
        return git(repo, "remote", "get-url", "origin")
    except GitError:
        return ""


def set_remote(repo: Path, url: str) -> None:
    git(repo, "remote", "add", "origin", url)


def create_github_repo(repo: Path, public: bool = True) -> tuple[bool, str]:
    """`gh repo create <name> --public --source . --remote origin`.

    Public is the default deliberately: private-repo commits appear on the
    contribution graph only if the user opted into private contributions, and
    then only as unlabeled squares (spec:165-166).
    """
    try:
        result = subprocess.run(
            ["gh", "repo", "create", repo.name,
             "--public" if public else "--private",
             "--source", str(repo), "--remote", "origin"],
            capture_output=True, text=True)
    except OSError:
        return False, "`gh` is not installed - paste a remote URL instead"
    if result.returncode != 0:
        return False, (result.stderr.strip() or "gh repo create failed")
    return True, f"created and linked origin for {repo.name}"


def unpushed_count(repo: Path) -> int | None:
    """Commits on the current branch that origin does not have.

    None means "cannot tell" - no remote-tracking ref exists yet, which is
    itself the common case of "you have never actually pushed".
    """
    branch = current_branch(repo)
    try:
        log = git(repo, "log", "--pretty=%H", f"origin/{branch}..{branch}")
    except GitError:
        return None
    return len(log.splitlines())


def push(repo: Path) -> bool:
    """Push if a remote exists. Never raises - a failed push must not lose work.

    Pushes the *current* branch, not a hardcoded `main`: first_run is safe to
    re-run against an existing repo, which may well be on `master`.
    """
    try:
        if not git(repo, "remote"):
            return False
        git(repo, "push", "-q", "-u", "origin", current_branch(repo))
        return True
    except GitError:
        return False


def last_subject(repo: Path) -> str:
    """Subject of HEAD, so callers can decide *before* undoing it."""
    return git(repo, "log", "-1", "--pretty=%s")


def undo_last(repo: Path) -> str:
    subject = last_subject(repo)
    git(repo, "reset", "--soft", "HEAD~1")
    return subject
