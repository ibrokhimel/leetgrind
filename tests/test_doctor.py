from pathlib import Path
from leetgrind import doctor
from leetgrind.config import Config
from leetgrind.repo import init_repo, git


def by_name(checks, name):
    return next(c for c in checks if c.name == name)


def make_repo(tmp_path, email):
    init_repo(tmp_path)
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", email)
    return Config(repo_path=tmp_path)


def test_flags_email_not_on_the_github_account(tmp_path, monkeypatch):
    cfg = make_repo(tmp_path, "wrong@example.com")
    monkeypatch.setattr(doctor, "github_emails", lambda: ["real@example.com"])
    monkeypatch.setattr(doctor, "code_available", lambda: True)
    check = by_name(doctor.run_checks(cfg), "commit email counts on GitHub")
    assert check.ok is False
    assert "wrong@example.com" in check.detail


def test_passes_when_email_is_on_the_account(tmp_path, monkeypatch):
    cfg = make_repo(tmp_path, "real@example.com")
    monkeypatch.setattr(doctor, "github_emails", lambda: ["real@example.com"])
    monkeypatch.setattr(doctor, "code_available", lambda: True)
    assert by_name(doctor.run_checks(cfg), "commit email counts on GitHub").ok is True


def test_reports_when_the_scope_is_missing(tmp_path, monkeypatch):
    cfg = make_repo(tmp_path, "real@example.com")
    monkeypatch.setattr(doctor, "github_emails", lambda: None)
    monkeypatch.setattr(doctor, "code_available", lambda: True)
    check = by_name(doctor.run_checks(cfg), "commit email counts on GitHub")
    assert check.ok is False
    assert "gh auth refresh" in check.fix


def test_flags_missing_git_identity(tmp_path, monkeypatch):
    init_repo(tmp_path)
    monkeypatch.setattr(doctor, "github_emails", lambda: [])
    monkeypatch.setattr(doctor, "code_available", lambda: True)
    assert by_name(doctor.run_checks(Config(repo_path=tmp_path)), "git identity set").ok is False


def test_flags_missing_vscode(tmp_path, monkeypatch):
    cfg = make_repo(tmp_path, "real@example.com")
    monkeypatch.setattr(doctor, "github_emails", lambda: ["real@example.com"])
    monkeypatch.setattr(doctor, "code_available", lambda: False)
    assert by_name(doctor.run_checks(cfg), "VS Code on PATH").ok is False


def test_handles_no_config_at_all(monkeypatch):
    monkeypatch.setattr(doctor, "github_emails", lambda: [])
    monkeypatch.setattr(doctor, "code_available", lambda: False)
    assert by_name(doctor.run_checks(None), "configured").ok is False
