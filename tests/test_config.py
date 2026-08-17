from pathlib import Path
from leetgrind.config import Config, load_config, save_config

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
