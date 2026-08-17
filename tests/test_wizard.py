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
