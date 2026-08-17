import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1


@dataclass
class ActiveProblem:
    id: int
    slug: str
    title: str
    difficulty: str
    folder: str
    started_at: str
    schema: int = SCHEMA


def _dir(repo: Path) -> Path:
    path = repo / ".lc"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_file(repo: Path) -> Path:
    return _dir(repo) / "state.json"


def load_active(repo: Path) -> ActiveProblem | None:
    path = _state_file(repo)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA:
            return None
        return ActiveProblem(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def save_active(repo: Path, active: ActiveProblem) -> None:
    _state_file(repo).write_text(json.dumps(asdict(active), indent=2), encoding="utf-8")


def clear_active(repo: Path) -> None:
    _state_file(repo).unlink(missing_ok=True)


def elapsed_minutes(active: ActiveProblem) -> int:
    started = datetime.fromisoformat(active.started_at)
    delta = datetime.now(timezone.utc) - started
    return max(0, int(delta.total_seconds() // 60))


def cache_get(repo: Path, slug: str) -> dict | None:
    path = _dir(repo) / "cache" / f"{slug}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def cache_put(repo: Path, slug: str, payload: dict) -> None:
    path = _dir(repo) / "cache" / f"{slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
