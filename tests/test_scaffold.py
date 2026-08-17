from leetgrind.scaffold import render_files
from leetgrind.examples import Example
from leetgrind.models import Problem

P = Problem(id=1, slug="two-sum", title="Two Sum", difficulty="Easy",
            tags=("array", "hash-table"), is_paid_only=False,
            stub="class Solution:\n    def twoSum(self, nums, target):\n        ",
            content_html="<p>ignored</p>")

def test_renders_three_files():
    assert set(render_files(P, ())) == {"solution.py", "test_solution.py", "README.md"}

def test_solution_uses_the_official_stub():
    assert "def twoSum" in render_files(P, ())["solution.py"]

def test_readme_has_metadata_but_not_the_description():
    out = render_files(P, ())["README.md"]
    assert "# 1. Two Sum" in out
    assert "Easy" in out and "array" in out
    assert "https://leetcode.com/problems/two-sum/" in out
    assert "ignored" not in out

def test_tests_are_generated_from_examples():
    ex = (Example(args=("[2,7,11,15]", "9"), expected="[0,1]"),)
    out = render_files(P, ex)["test_solution.py"]
    assert "twoSum" in out
    assert "([2,7,11,15], 9)" in out
    assert "[0,1]" in out
    assert "skip" not in out

def test_missing_examples_produce_a_skipped_placeholder():
    out = render_files(P, ())["test_solution.py"]
    assert "pytest.skip" in out

def test_paid_only_falls_back_to_a_generic_stub():
    paid = Problem(id=2, slug="x", title="X", difficulty="Hard", tags=(),
                   is_paid_only=True, stub=None, content_html=None)
    assert "class Solution" in render_files(paid, ())["solution.py"]

def test_single_argument_example_renders_a_real_tuple():
    ex = (Example(args=("[1,2,3]",), expected="5"),)
    out = render_files(P, ex)["test_solution.py"]
    assert "(([1,2,3],), 5)" in out
