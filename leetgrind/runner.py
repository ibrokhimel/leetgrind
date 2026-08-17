import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_SUMMARY_RE = re.compile(r"^=+ (.*(?:passed|failed|error|skipped).*) =+$", re.MULTILINE)


@dataclass
class TestOutcome:
    passed: bool
    summary: str
    output: str
    skipped: bool


def run_tests(folder: Path) -> TestOutcome:
    """Run the problem's tests with its own folder importable as the rootdir."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "test_solution.py", "-q",
         "-p", "no:cacheprovider", "--no-header"],
        cwd=folder, capture_output=True, text=True)
    output = result.stdout + result.stderr
    match = _SUMMARY_RE.search(output)
    if match:
        summary = match.group(1).strip()
    else:
        lines = output.strip().splitlines()
        summary = lines[-1] if lines else ""
    return TestOutcome(
        passed=result.returncode == 0,
        summary=summary,
        output=output,
        skipped="skipped" in output and "passed" not in output and "failed" not in output,
    )
