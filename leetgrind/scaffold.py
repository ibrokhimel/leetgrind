import re

from .examples import Example
from .models import Problem

_GENERIC_STUB = "class Solution:\n    def solve(self):\n        ...\n"
_METHOD_RE = re.compile(r"def\s+(\w+)\s*\(")

_README = """# {id}. {title}

**Link:** {url}
**Difficulty:** {difficulty}
**Tags:** {tags}

**Approach:** _(fill in when solved)_
**Time:** O(?)  **Space:** O(?)
**Solved in:** _(pending)_
"""

_TEST_HEAD = """import pytest

from solution import Solution

"""

_SKIP_BODY = """

def test_examples():
    pytest.skip("no examples auto-extracted - add cases by hand")
"""

_CASE_BODY = """cases = [
{cases}]


@pytest.mark.parametrize("args,expected", cases)
def test_examples(args, expected):
    assert Solution().{method}(*args) == expected
"""


def _method_name(stub: str | None) -> str:
    if stub and (m := _METHOD_RE.search(stub)):
        return m.group(1)
    return "solve"


def url_for(slug: str) -> str:
    return f"https://leetcode.com/problems/{slug}/"


def render_files(problem: Problem, examples: tuple[Example, ...]) -> dict[str, str]:
    stub = problem.stub or _GENERIC_STUB
    if not stub.endswith("\n"):
        stub += "\n"

    readme = _README.format(
        id=problem.id, title=problem.title, url=url_for(problem.slug),
        difficulty=problem.difficulty, tags=", ".join(problem.tags) or "-")

    if examples:
        rows = "".join(
            f"    (({', '.join(e.args)}), {e.expected}),\n" for e in examples)
        tests = _TEST_HEAD + _CASE_BODY.format(
            cases=rows, method=_method_name(problem.stub))
    else:
        tests = _TEST_HEAD + _SKIP_BODY

    return {"solution.py": stub, "test_solution.py": tests, "README.md": readme}
