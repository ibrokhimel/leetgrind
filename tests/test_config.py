import pytest

from pathlib import Path
from leetgrind.config import (Config, config_path, describe, load_config,
                              save_config, set_repo_path)

def test_save_then_load_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    cfg = Config(repo_path=Path("C:/repos/leetcode-solutions"), auto_push=False)
    save_config(cfg)
    assert load_config() == cfg

def test_load_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert load_config() is None

def test_defaults_are_applied_for_missing_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from leetgrind.config import config_path
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text('repo_path = "C:/x"\n', encoding="utf-8")
    cfg = load_config()
    assert cfg.language == "python"
    assert cfg.auto_close is True
    assert cfg.gate_on_tests is True


# --- A broken config must not crash EVERY command, least of all `lc doctor`,
#     the one tool meant to diagnose it. None hits the "Not configured" path. ---

@pytest.mark.parametrize("body", [
    'repo_path = "C:/x',          # truncated string - TOMLDecodeError
    'auto_push = true\n',         # no repo_path at all - KeyError
    'repo_path = 42\n',           # wrong type - TypeError from Path(42)
    '',                           # empty file
])
def test_a_broken_config_loads_as_none_rather_than_raising(tmp_path, monkeypatch, body):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(body, encoding="utf-8")
    assert load_config() is None


def test_set_repo_path_preserves_other_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    save_config(Config(repo_path=Path("C:/old"), auto_push=False, auto_close=False))
    cfg = set_repo_path("C:/new")
    assert cfg.repo_path == Path("C:/new")
    assert cfg.auto_push is False and cfg.auto_close is False
    assert load_config() == cfg


def test_set_repo_path_works_from_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert set_repo_path("C:/new").repo_path == Path("C:/new")
    assert load_config().repo_path == Path("C:/new")


def test_describe_lists_every_field(tmp_path):
    text = describe(Config(repo_path=tmp_path))
    assert "repo_path" in text and "auto_push" in text and "gate_on_tests" in text
