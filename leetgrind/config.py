import os
import tomllib
from dataclasses import dataclass, asdict, fields
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
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Config)}
    data = {k: v for k, v in raw.items() if k in known}
    data["repo_path"] = Path(data["repo_path"])
    return Config(**data)


def save_config(cfg: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    data["repo_path"] = cfg.repo_path.as_posix()
    path.write_text(tomli_w.dumps(data), encoding="utf-8")
