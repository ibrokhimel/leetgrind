from pathlib import Path
from leetgrind import wizard
from leetgrind.config import load_config

def test_first_run_creates_repo_and_config(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    repo = tmp_path / "solutions"
    cfg = wizard.first_run({"repo_path": repo, "auto_push": False})
    assert (repo / ".git").is_dir()
    assert (repo / ".gitignore").exists()
    assert (repo / ".gitattributes").exists()
    assert cfg.repo_path == repo
    assert load_config() == cfg

def test_first_run_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    repo = tmp_path / "solutions"
    wizard.first_run({"repo_path": repo, "auto_push": False})
    (repo / "0001-two-sum").mkdir()
    cfg = wizard.first_run({"repo_path": repo, "auto_push": False})
    assert (repo / "0001-two-sum").exists()
    assert cfg.repo_path == repo


# --- C1: nothing in the codebase ever created a remote, so every commit
#     stayed local and the contribution graph stayed empty. ---

def test_first_run_wires_up_the_remote_it_is_given(tmp_path, monkeypatch):
    from leetgrind.repo import remote_url
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    repo = tmp_path / "solutions"
    wizard.first_run({"repo_path": repo, "auto_push": True,
                      "remote_url": "https://github.com/u/s.git"})
    assert remote_url(repo) == "https://github.com/u/s.git"


def test_first_run_leaves_an_existing_remote_alone(tmp_path, monkeypatch):
    from leetgrind.repo import git, remote_url
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    repo = tmp_path / "solutions"
    wizard.first_run({"repo_path": repo, "auto_push": True})
    git(repo, "remote", "add", "origin", "https://github.com/u/first.git")
    wizard.first_run({"repo_path": repo, "auto_push": True,
                      "remote_url": "https://github.com/u/second.git"})
    assert remote_url(repo) == "https://github.com/u/first.git"


def test_first_run_without_a_remote_answer_adds_none(tmp_path, monkeypatch):
    from leetgrind.repo import remote_url
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    repo = tmp_path / "solutions"
    wizard.first_run({"repo_path": repo, "auto_push": False})
    assert remote_url(repo) == ""
