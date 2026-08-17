import tomllib
from pathlib import Path

from leetgrind.runner import run_tests


# --- C4: run_tests shells out to `-m pytest` as the gate inside `lc done`, so
#     a plain `pip install .` without pytest yields a tool whose main command
#     always fails. It is a runtime dependency, not a dev extra. ---

def test_pytest_is_declared_as_a_runtime_dependency():
    root = Path(__file__).resolve().parent.parent
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = " ".join(data["project"]["dependencies"])
    assert "pytest" in runtime, "`lc done` cannot run its test gate without pytest"
    dev = " ".join(data["project"].get("optional-dependencies", {}).get("dev", []))
    assert "pytest" not in dev, "pytest must not be duplicated as a dev extra"


def test_no_unused_dependencies_are_declared():
    """M1: pyperclip was declared and imported nowhere."""
    root = Path(__file__).resolve().parent.parent
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    sources = "\n".join(p.read_text(encoding="utf-8")
                        for p in (root / "leetgrind").glob("*.py"))
    for dep in data["project"]["dependencies"]:
        name = dep.split(">")[0].split("=")[0].strip().replace("-", "_")
        if name == "pytest":
            continue  # invoked as a subprocess, never imported
        assert name in sources, f"{name} is declared but imported nowhere"

def scaffold(folder, solution, test):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "solution.py").write_text(solution, encoding="utf-8")
    (folder / "test_solution.py").write_text(test, encoding="utf-8")

PASSING = """import pytest
from solution import Solution
def test_ok():
    assert Solution().twoSum([2,7], 9) == [0,1]
"""

def test_passing_suite_reports_passed(tmp_path):
    scaffold(tmp_path / "p", "class Solution:\n    def twoSum(self, n, t): return [0,1]\n", PASSING)
    outcome = run_tests(tmp_path / "p")
    assert outcome.passed is True
    assert outcome.skipped is False

def test_failing_suite_reports_output(tmp_path):
    scaffold(tmp_path / "p", "class Solution:\n    def twoSum(self, n, t): return [9,9]\n", PASSING)
    outcome = run_tests(tmp_path / "p")
    assert outcome.passed is False
    assert "assert" in outcome.output

def test_skipped_suite_is_marked_skipped(tmp_path):
    scaffold(tmp_path / "p", "class Solution: pass\n",
             "import pytest\ndef test_x():\n    pytest.skip('none')\n")
    outcome = run_tests(tmp_path / "p")
    assert outcome.passed is True
    assert outcome.skipped is True

def test_skipped_with_noise_output_not_misclassified(tmp_path):
    """Regression test: output noise containing 'passed' should not flip skipped classification."""
    solution = "print('test passed')\nclass Solution: pass\n"
    test = "import pytest\ndef test_x():\n    pytest.skip('skipping')\n"
    scaffold(tmp_path / "p", solution, test)
    outcome = run_tests(tmp_path / "p")
    assert outcome.passed is True
    assert outcome.skipped is True

def test_non_ascii_output_does_not_raise(tmp_path):
    """Regression test: non-ASCII characters in output should not raise."""
    solution = "print('Solution with emoji: emoji_char')\nclass Solution: pass\n".replace("emoji_char", chr(128512))
    test = "import pytest\ndef test_x():\n    pytest.skip('skipping')\n"
    scaffold(tmp_path / "p", solution, test)
    outcome = run_tests(tmp_path / "p")
    assert isinstance(outcome, object)
    assert outcome.passed is True
    assert outcome.skipped is True
