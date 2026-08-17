import pytest
from leetgrind.repo import init_repo, commit_paths, git, undo_last, identity, GitError

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
