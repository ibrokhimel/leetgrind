import pytest
from leetgrind import workflow, editor, wizard
from leetgrind.models import Problem
from leetgrind.repo import git

P = Problem(id=1, slug="two-sum", title="Two Sum", difficulty="Easy",
            tags=("array",), is_paid_only=False,
            stub="class Solution:\n    def twoSum(self, nums, target):\n        return [0,1]\n",
            content_html="""<pre><strong>Input:</strong> nums = [2,7,11,15], target = 9
<strong>Output:</strong> [0,1]</pre>""")

def test_full_loop_produces_exactly_two_commits(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(workflow, "fetch_problem", lambda slug, **kw: P)
    monkeypatch.setattr(editor, "open_problem", lambda folder: True)
    monkeypatch.setattr(editor, "close_window", lambda name: True)

    cfg = wizard.first_run({"repo_path": tmp_path / "solutions", "auto_push": False})
    git(cfg.repo_path, "config", "user.name", "Test")
    git(cfg.repo_path, "config", "user.email", "test@example.com")

    workflow.start_problem(cfg, "https://leetcode.com/problems/two-sum/")
    workflow.finish_problem(cfg, "hash map", "O(n)", "O(n)")

    subjects = git(cfg.repo_path, "log", "--pretty=%s").splitlines()
    assert subjects[0] == "Solve 1: Two Sum (hash map, O(n))"
    assert subjects[1] == "Start 1: Two Sum (Easy)"
    assert git(cfg.repo_path, "status", "--porcelain") == ""
