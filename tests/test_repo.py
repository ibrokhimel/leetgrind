import subprocess

import pytest
from leetgrind.repo import (GitError, commit_paths, create_github_repo,
                            current_branch, git, identity, init_repo, push,
                            remote_url, set_remote, undo_last, unpushed_count)

@pytest.fixture
def repo(tmp_path):
    init_repo(tmp_path)
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.com")
    return tmp_path

def test_init_creates_repo_on_main(repo):
    assert (repo / ".git").is_dir()
    assert git(repo, "branch", "--show-current") == "main"

def test_init_writes_gitignore_and_gitattributes(repo):
    assert "__pycache__/" in (repo / ".gitignore").read_text()
    assert ".lc/" in (repo / ".gitignore").read_text()
    assert "text=auto" in (repo / ".gitattributes").read_text()

def test_commit_paths_creates_a_commit(repo):
    (repo / "a.txt").write_text("hello")
    assert commit_paths(repo, [repo / "a.txt"], "feat: a") is True
    assert git(repo, "log", "-1", "--pretty=%s") == "feat: a"

def test_commit_paths_returns_false_when_nothing_changed(repo):
    (repo / "a.txt").write_text("hello")
    commit_paths(repo, [repo / "a.txt"], "feat: a")
    assert commit_paths(repo, [repo / "a.txt"], "feat: again") is False

def test_undo_last_removes_the_commit_but_keeps_files(repo):
    (repo / "a.txt").write_text("hello")
    commit_paths(repo, [repo / "a.txt"], "feat: a")
    (repo / "b.txt").write_text("world")
    commit_paths(repo, [repo / "b.txt"], "feat: b")
    undo_last(repo)
    assert git(repo, "log", "-1", "--pretty=%s") == "feat: a"
    assert (repo / "b.txt").exists()

def test_identity_reads_config(repo):
    assert identity(repo) == ("Test", "test@example.com")

def test_git_raises_on_failure(repo):
    with pytest.raises(GitError):
        git(repo, "checkout", "no-such-branch")


# --- I1: `git commit` with no pathspec commits the whole index, so whatever
#     `undo`'s `reset --soft` left staged rode into the NEXT problem's commit. ---

def test_commit_paths_does_not_sweep_in_what_undo_left_staged(repo):
    (repo / "solution.py").write_text("stub")
    commit_paths(repo, [repo / "solution.py"], "Start 1")
    (repo / "solution.py").write_text("solved")
    commit_paths(repo, [repo / "solution.py"], "Solve 1")
    undo_last(repo)  # reset --soft: solution.py's solved content is now staged
    (repo / "other.py").write_text("a different problem")
    assert commit_paths(repo, [repo / "other.py"], "Start 2") is True
    named = git(repo, "show", "--pretty=", "--name-only", "HEAD").splitlines()
    assert named == ["other.py"], f"Start 2 swept in stray staged content: {named}"


def test_commit_paths_ignores_stray_staged_files_when_deciding_to_commit(repo):
    (repo / "a.txt").write_text("one")
    commit_paths(repo, [repo / "a.txt"], "c1")
    (repo / "b.txt").write_text("stray")
    git(repo, "add", "--", str(repo / "b.txt"))
    # b.txt is staged but was never handed to commit_paths, and a.txt is
    # unchanged - so there is nothing to commit under *this* message.
    assert commit_paths(repo, [repo / "a.txt"], "c2") is False


# --- C1: push() hardcoded `origin main`, so an existing master-branch repo
#     pushed nowhere, forever, silently. The "remote" here is a local bare
#     repo - no network. ---

@pytest.fixture
def origin(tmp_path):
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    return bare


def _work(tmp_path, branch):
    work = tmp_path / "work"
    init_repo(work)
    git(work, "config", "user.name", "Test")
    git(work, "config", "user.email", "test@example.com")
    if branch != "main":
        git(work, "checkout", "-q", "-b", branch)
    (work / "a.txt").write_text("hello")
    commit_paths(work, [work / "a.txt"], "c1")
    return work


@pytest.mark.parametrize("branch", ["main", "master"])
def test_push_pushes_the_current_branch(tmp_path, origin, branch):
    work = _work(tmp_path, branch)
    set_remote(work, str(origin))
    assert current_branch(work) == branch
    assert push(work) is True
    assert branch in git(work, "ls-remote", "--heads", "origin")


def test_push_returns_false_without_a_remote(tmp_path):
    work = _work(tmp_path, "main")
    assert push(work) is False


def test_remote_url_is_empty_without_an_origin(repo):
    assert remote_url(repo) == ""
    set_remote(repo, "https://example.com/x.git")
    assert remote_url(repo) == "https://example.com/x.git"


def test_unpushed_count_tracks_commits_origin_does_not_have(tmp_path, origin):
    work = _work(tmp_path, "main")
    set_remote(work, str(origin))
    assert unpushed_count(work) is None, "nothing pushed yet is not knowable as 0"
    push(work)
    assert unpushed_count(work) == 0
    (work / "b.txt").write_text("later")
    commit_paths(work, [work / "b.txt"], "c2")
    assert unpushed_count(work) == 1


def test_create_github_repo_reports_a_missing_gh_instead_of_raising(repo, monkeypatch):
    def no_gh(*a, **k):
        raise FileNotFoundError("gh")
    monkeypatch.setattr(subprocess, "run", no_gh)
    ok, detail = create_github_repo(repo)
    assert ok is False
    assert "gh" in detail


def test_create_github_repo_defaults_to_public(repo, monkeypatch):
    seen = {}

    class R:
        returncode = 0
        stderr = ""
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: seen.update(cmd=cmd) or R())
    ok, _ = create_github_repo(repo)
    assert ok is True
    # spec:165-166 - private-repo commits are anonymous squares at best.
    assert "--public" in seen["cmd"]
    assert "--private" not in seen["cmd"]
