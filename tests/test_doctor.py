import json
import subprocess

import pytest

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


@pytest.fixture(autouse=True)
def isolate_git_config(tmp_path, monkeypatch):
    """Isolate git config during tests so tests don't inherit developer's global config."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "nonexistent-global"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "nonexistent-system"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


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


def test_passes_with_globally_configured_identity(tmp_path, monkeypatch):
    """Identity set globally (not locally) should still report as SET, since git uses it."""
    init_repo(tmp_path)
    # Create a global config file with identity
    global_config = tmp_path / "global"
    global_config.write_text("[user]\n  name = Global User\n  email = global@example.com\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setattr(doctor, "github_emails", lambda: ["global@example.com"])
    monkeypatch.setattr(doctor, "code_available", lambda: True)
    check = by_name(doctor.run_checks(Config(repo_path=tmp_path)), "git identity set")
    assert check.ok is True
    assert "global@example.com" in check.detail


def test_flags_missing_vscode(tmp_path, monkeypatch):
    cfg = make_repo(tmp_path, "real@example.com")
    monkeypatch.setattr(doctor, "github_emails", lambda: ["real@example.com"])
    monkeypatch.setattr(doctor, "code_available", lambda: False)
    assert by_name(doctor.run_checks(cfg), "VS Code on PATH").ok is False


def test_handles_no_config_at_all(monkeypatch):
    monkeypatch.setattr(doctor, "github_emails", lambda: [])
    monkeypatch.setattr(doctor, "code_available", lambda: False)
    assert by_name(doctor.run_checks(None), "configured").ok is False


def test_suggests_verifying_email_when_none_verified(tmp_path, monkeypatch):
    """When authenticated but no verified emails, suggest adding one, not refreshing scope."""
    cfg = make_repo(tmp_path, "test@example.com")
    monkeypatch.setattr(doctor, "github_emails", lambda: [])
    monkeypatch.setattr(doctor, "code_available", lambda: True)
    check = by_name(doctor.run_checks(cfg), "commit email counts on GitHub")
    assert check.ok is False
    assert "github.com/settings/emails" in check.fix


def test_github_emails_returns_none_when_gh_absent(monkeypatch):
    """When gh is not installed, return None, not raise."""
    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("gh not found")
    monkeypatch.setattr(subprocess, "run", raise_file_not_found)
    result = doctor.github_emails()
    assert result is None


def test_github_emails_returns_none_on_non_zero_exit(monkeypatch):
    """When gh returns non-zero, return None."""
    class FakeResult:
        returncode = 1
        stdout = ""
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeResult())
    result = doctor.github_emails()
    assert result is None


def test_github_emails_filters_verified_only(monkeypatch):
    """Only return emails with verified: true."""
    class FakeResult:
        returncode = 0
        stdout = json.dumps([
            {"email": "verified@example.com", "verified": True},
            {"email": "unverified@example.com", "verified": False}
        ])
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeResult())
    result = doctor.github_emails()
    assert result == ["verified@example.com"]


def test_github_emails_returns_none_on_invalid_json(monkeypatch):
    """When JSON is malformed, return None, not raise."""
    class FakeResult:
        returncode = 0
        stdout = "{invalid json"
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeResult())
    result = doctor.github_emails()
    assert result is None


def test_github_emails_returns_none_when_json_not_list(monkeypatch):
    """When JSON is valid but not a list, return None, not raise."""
    class FakeResult:
        returncode = 0
        stdout = '{"email": "test@example.com"}'
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeResult())
    result = doctor.github_emails()
    assert result is None


def test_github_emails_handles_missing_email_key(monkeypatch):
    """When list elements lack 'email' key, return None, not raise."""
    class FakeResult:
        returncode = 0
        stdout = json.dumps([{"verified": True}])
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeResult())
    result = doctor.github_emails()
    assert result is None


def test_github_emails_handles_non_dict_elements(monkeypatch):
    """When list contains non-dict elements, return None, not raise."""
    class FakeResult:
        returncode = 0
        stdout = json.dumps(["string", {"verified": True}])
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: FakeResult())
    result = doctor.github_emails()
    assert result is None
