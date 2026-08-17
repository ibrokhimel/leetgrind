from leetgrind.runner import run_tests

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
