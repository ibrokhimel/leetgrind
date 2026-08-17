import shutil
import subprocess
from pathlib import Path
from leetgrind import editor

# C3: shutil.which honours PATHEXT and resolves `code` to code.CMD on Windows,
# but CreateProcess only ever appends .exe - so the bare name "code" raises
# FileNotFoundError even though code_available() said yes. Every test here
# fakes the *resolved path*, which is what open_problem must actually launch.
CODE_CMD = r"C:\Program Files\Microsoft VS Code\bin\code.CMD"


def test_open_problem_invokes_code_with_new_window(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(shutil, "which", lambda name: CODE_CMD)
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0))
    assert editor.open_problem(tmp_path) is True
    assert ["-n", str(tmp_path)] == calls[0][1:]
    assert "-g" in calls[1]
    assert calls[1][-1].endswith("solution.py")


def test_open_problem_launches_the_resolved_path_not_the_bare_name(monkeypatch, tmp_path):
    """C3 regression: a bare "code" cannot start code.CMD via CreateProcess."""
    calls = []
    monkeypatch.setattr(shutil, "which", lambda name: CODE_CMD)
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0))
    editor.open_problem(tmp_path)
    assert [c[0] for c in calls] == [CODE_CMD, CODE_CMD]
    assert "code" not in [c[0] for c in calls]


def test_open_problem_is_a_no_op_without_code(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    def must_not_be_called(*a, **k):
        raise AssertionError("subprocess.run must not be reached")
    monkeypatch.setattr(subprocess, "run", must_not_be_called)
    assert editor.open_problem(tmp_path) is False
    assert editor.code_available() is False


def test_open_problem_never_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: CODE_CMD)
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


def test_close_window_escapes_single_quotes_and_wildcards(monkeypatch):
    seen = {}
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: seen.update(cmd=cmd) or subprocess.CompletedProcess(cmd, 0))
    editor.close_window("folder'with*wildcards?and[brackets]")
    command_str = " ".join(seen["cmd"])
    # Single quote should be doubled for PowerShell escaping
    assert "''" in command_str
    # Wildcards should be backtick-escaped
    assert "`*" in command_str
    assert "`?" in command_str
    assert "`[" in command_str
    # Verify the original unescaped characters are not present as bare metacharacters
    # (they should be escaped in the PowerShell command)
    ps_command = seen["cmd"][-1]  # The PowerShell -Command argument
    assert "folder''with" in ps_command
    assert "`*" in ps_command
    assert "`?" in ps_command
