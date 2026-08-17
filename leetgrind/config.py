import os
import tomllib
from dataclasses import dataclass, asdict, fields, replace
from pathlib import Path

import tomli_w


@dataclass
class Config:
    repo_path: Path
    language: str = "python"
    auto_close: bool = True
    auto_push: bool = True
    gate_on_tests: bool = True
    open_browser: bool = False
    active_list: str = "blind75"
    clipboard_hint: bool = True


def config_path() -> Path:
    base = os.environ.get("APPDATA") or Path.home() / ".config"
    return Path(base) / "leetgrind" / "config.toml"


def load_config() -> Config | None:
    path = config_path()
    if not path.exists():
        return None
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in fields(Config)}
        data = {k: v for k, v in raw.items() if k in known}
        data["repo_path"] = Path(data["repo_path"])
        return Config(**data)
    except (tomllib.TOMLDecodeError, KeyError, OSError, TypeError, ValueError):
        # A truncated or hand-mangled config must not crash every command -
        # least of all `lc doctor`, the one tool meant to diagnose it. None
        # lands on the existing, graceful "Not configured" path.
        return None


def save_config(cfg: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    data["repo_path"] = cfg.repo_path.as_posix()
    path.write_text(tomli_w.dumps(data), encoding="utf-8")


def set_repo_path(new_path: str | Path) -> Config:
    """Repoint the solutions repo, keeping every other setting.

    Without this the only way back from a moved, renamed, or disconnected
    solutions repo is hand-editing %APPDATA%\\leetgrind\\config.toml.
    """
    cfg = load_config()
    cfg = (Config(repo_path=Path(new_path)) if cfg is None
           else replace(cfg, repo_path=Path(new_path)))
    save_config(cfg)
    return cfg


def describe(cfg: Config) -> str:
    return "\n".join(f"{f.name} = {getattr(cfg, f.name)}" for f in fields(Config))
