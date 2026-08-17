import subprocess
from pathlib import Path
import os

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
        # Create empty commit to establish HEAD, using env vars for identity
        env = os.environ.copy()
        env.update({
            "GIT_AUTHOR_NAME": "LeetGrind",
            "GIT_AUTHOR_EMAIL": "leetgrind@local",
            "GIT_COMMITTER_NAME": "LeetGrind",
            "GIT_COMMITTER_EMAIL": "leetgrind@local",
        })
        result = subprocess.run(["git", "-C", str(repo), "commit", "--allow-empty", "-q", "-m", "Initial commit"],
                                env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise GitError(result.stderr.strip() or "Failed to create initial commit")
    (repo / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (repo / ".gitattributes").write_text(GITATTRIBUTES, encoding="utf-8")


def identity(repo: Path) -> tuple[str, str]:
    try:
        return git(repo, "config", "user.name"), git(repo, "config", "user.email")
    except GitError:
        return "", ""


def commit_paths(repo: Path, paths: list[Path], message: str) -> bool:
    for path in paths:
        git(repo, "add", "--", str(path))
    if not git(repo, "diff", "--cached", "--name-only"):
        return False
    git(repo, "commit", "-q", "-m", message)
    return True


def push(repo: Path) -> bool:
    """Push if a remote exists. Never raises - a failed push must not lose work."""
    try:
        if not git(repo, "remote"):
            return False
        git(repo, "push", "-q", "-u", "origin", "main")
        return True
    except GitError:
        return False


def undo_last(repo: Path) -> str:
    subject = git(repo, "log", "-1", "--pretty=%s")
    git(repo, "reset", "--soft", "HEAD~1")
    return subject
