import subprocess
from pathlib import Path
from leetgrind import editor


def test_open_problem_invokes_code_with_new_window(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(editor, "code_available", lambda: True)
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0))
    assert editor.open_problem(tmp_path) is True
    assert ["-n", str(tmp_path)] == calls[0][1:]
    assert "-g" in calls[1]
    assert calls[1][-1].endswith("solution.py")


def test_open_problem_is_a_no_op_without_code(monkeypatch, tmp_path):
    monkeypatch.setattr(editor, "code_available", lambda: False)
    assert editor.open_problem(tmp_path) is False


def test_open_problem_never_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(editor, "code_available", lambda: True)
    def boom(*a, **k): raise OSError("nope")
    monkeypatch.setattr(subprocess, "run", boom)
    assert editor.open_problem(tmp_path) is False


def test_close_window_never_raises(monkeypatch):
    def boom(*a, **k): raise OSError("nope")
    monkeypatch.setattr(subprocess, "run", boom)
    assert editor.close_window("0042-trapping-rain-water") is False


def test_close_window_passes_the_folder_name_to_powershell(monkeypatch):
    seen = {}
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: seen.update(cmd=cmd) or subprocess.CompletedProcess(cmd, 0))
    editor.close_window("0042-trapping-rain-water")
    assert "0042-trapping-rain-water" in " ".join(seen["cmd"])
