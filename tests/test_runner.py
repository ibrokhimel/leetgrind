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
