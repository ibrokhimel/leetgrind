import shutil
import subprocess
from pathlib import Path

_CLOSE_PS = (
    "Get-Process code -ErrorAction SilentlyContinue | "
    "Where-Object {{ $_.MainWindowTitle -like '*{name}*' }} | "
    "ForEach-Object {{ $_.CloseMainWindow() }} | Out-Null"
)


def _escape_powershell_string(s: str) -> str:
    """Escape a string for safe use in PowerShell -like pattern matching."""
    # Escape single quotes by doubling them
    s = s.replace("'", "''")
    # Escape wildcard metacharacters with backticks
    s = s.replace("*", "`*")
    s = s.replace("?", "`?")
    s = s.replace("[", "`[")
    return s


def code_available() -> bool:
    try:
        return shutil.which("code") is not None
    except Exception:
        return False


def open_problem(folder: Path) -> bool:
    """Open a new VS Code window on `folder` with solution.py focused."""
    if not code_available():
        return False
    try:
        subprocess.run(["code", "-n", str(folder)], check=False)
        subprocess.run(["code", "-g", str(folder / "solution.py")], check=False)
        return True
    except OSError:
        return False


def close_window(folder_name: str) -> bool:
    """Best-effort graceful close of the VS Code window for `folder_name`."""
    try:
        escaped_name = _escape_powershell_string(folder_name)
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             _CLOSE_PS.format(name=escaped_name)],
            check=False, capture_output=True)
        return result.returncode == 0
    except OSError:
        return False
