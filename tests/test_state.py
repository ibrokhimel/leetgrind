from datetime import datetime, timedelta, timezone
import pytest
from leetgrind.state import (ActiveProblem, load_active, save_active, clear_active,
                             elapsed_minutes, cache_get, cache_put)

def make(**kw):
    base = dict(id=42, slug="trapping-rain-water", title="Trapping Rain Water",
                difficulty="Hard", folder="0042-trapping-rain-water",
                started_at=datetime.now(timezone.utc).isoformat())
    return ActiveProblem(**{**base, **kw})

def test_roundtrip(tmp_path):
    a = make()
    save_active(tmp_path, a)
    assert load_active(tmp_path) == a

def test_load_returns_none_when_absent(tmp_path):
    assert load_active(tmp_path) is None

def test_clear_removes_state(tmp_path):
    save_active(tmp_path, make())
    clear_active(tmp_path)
    assert load_active(tmp_path) is None

def test_unknown_schema_version_is_ignored_not_crashed(tmp_path):
    save_active(tmp_path, make())
    path = tmp_path / ".lc" / "state.json"
    path.write_text(path.read_text().replace('"schema": 1', '"schema": 99'))
    assert load_active(tmp_path) is None

def test_elapsed_minutes(tmp_path):
    started = (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat()
    assert elapsed_minutes(make(started_at=started)) == 12

def test_cache_roundtrip(tmp_path):
    assert cache_get(tmp_path, "two-sum") is None
    cache_put(tmp_path, "two-sum", {"a": 1})
    assert cache_get(tmp_path, "two-sum") == {"a": 1}

@pytest.mark.parametrize("raw", ["[]", "null", "42", '"x"'])
def test_non_object_state_file_returns_none(tmp_path, raw):
    path = tmp_path / ".lc" / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
    assert load_active(tmp_path) is None

def test_read_paths_do_not_create_the_lc_directory(tmp_path):
    assert load_active(tmp_path) is None
    assert cache_get(tmp_path, "two-sum") is None
    assert not (tmp_path / ".lc").exists()
