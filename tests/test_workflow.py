import shutil

import pytest
from leetgrind import workflow, leetcode, editor
from leetgrind.config import Config
from leetgrind.leetcode import LeetCodeUnavailable
from leetgrind.models import Problem
from leetgrind.repo import init_repo, git
from leetgrind.state import load_active

P = Problem(id=1, slug="two-sum", title="Two Sum", difficulty="Easy",
            tags=("array",), is_paid_only=False,
            stub="class Solution:\n    def twoSum(self, nums, target):\n        return [0,1]\n",
            content_html=None)

# A distinctive sentinel embedded in the description HTML, plus a real
# example block so extract_examples produces non-empty examples. Used to
# prove the cache never persists description text, and that a cache hit
# reproduces the same scaffold a cache miss would (examples survive).
SENTINEL = "SENTINEL_MUST_NEVER_BE_WRITTEN_TO_THE_CACHE_FILE"
CONTENT_WITH_EXAMPLE = f"""<p>{SENTINEL}</p>
<p><strong>Example 1:</strong></p>
<pre><strong>Input:</strong> nums = [2,7,11,15], target = 9
<strong>Output:</strong> [0,1]</pre>"""

P2 = Problem(id=7, slug="two-sum", title="Two Sum", difficulty="Easy",
             tags=("array",), is_paid_only=False,
             stub="class Solution:\n    def twoSum(self, nums, target):\n        return [0,1]\n",
             content_html=CONTENT_WITH_EXAMPLE)


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    repo = tmp_path / "solutions"
    init_repo(repo)
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    monkeypatch.setattr(leetcode, "fetch_problem", lambda slug, **kw: P)
    monkeypatch.setattr(workflow, "fetch_problem", lambda slug, **kw: P)
    monkeypatch.setattr(editor, "open_problem", lambda folder: True)
    monkeypatch.setattr(editor, "close_window", lambda name: True)
    return Config(repo_path=repo, auto_push=False)


def test_start_creates_folder_files_and_commit(cfg):
    active = workflow.start_problem(cfg, "https://leetcode.com/problems/two-sum/")
    folder = cfg.repo_path / "0001-two-sum"
    assert active.folder == "0001-two-sum"
    assert (folder / "solution.py").exists()
    assert (folder / "test_solution.py").exists()
    assert (folder / "README.md").exists()
    assert git(cfg.repo_path, "log", "-1", "--pretty=%s") == "Start 1: Two Sum (Easy)"
    assert load_active(cfg.repo_path) == active


def test_finish_commits_and_clears_state(cfg):
    workflow.start_problem(cfg, "two-sum")
    subject = workflow.finish_problem(cfg, "hash map", "O(n)", "O(n)")
    assert subject == "Solve 1: Two Sum (hash map, O(n))"
    assert git(cfg.repo_path, "log", "-1", "--pretty=%s") == subject
    assert load_active(cfg.repo_path) is None


def test_finish_writes_approach_into_the_problem_readme(cfg):
    workflow.start_problem(cfg, "two-sum")
    workflow.finish_problem(cfg, "hash map", "O(n)", "O(n)")
    text = (cfg.repo_path / "0001-two-sum" / "README.md").read_text()
    assert "hash map" in text
    assert "fill in when solved" not in text


def test_finish_regenerates_the_root_readme(cfg):
    workflow.start_problem(cfg, "two-sum")
    workflow.finish_problem(cfg, "hash map", "O(n)", "O(n)")
    assert "[Two Sum](0001-two-sum/)" in (cfg.repo_path / "README.md").read_text()


def test_park_records_an_unsolved_attempt(cfg):
    workflow.start_problem(cfg, "two-sum")
    subject = workflow.park_problem(cfg)
    assert subject == "Park 1: Two Sum (unsolved)"
    assert load_active(cfg.repo_path) is None


def test_start_refuses_when_a_problem_is_already_active(cfg):
    workflow.start_problem(cfg, "two-sum")
    with pytest.raises(workflow.ProblemActive):
        workflow.start_problem(cfg, "three-sum")


def test_fallback_problem_builds_usable_metadata():
    p = workflow.fallback_problem("trapping-rain-water", 42)
    assert p.id == 42
    assert p.title == "Trapping Rain Water"
    assert p.stub is None


# --- Ruling 1: start_problem owns the response cache (429 mitigation) ---

def test_start_caches_the_fetch_response_and_reuses_it(cfg, monkeypatch):
    calls = []

    def counting_fetch(slug, **kw):
        calls.append(slug)
        return P

    monkeypatch.setattr(workflow, "fetch_problem", counting_fetch)
    workflow.start_problem(cfg, "two-sum")
    workflow.park_problem(cfg)
    workflow.start_problem(cfg, "two-sum")
    assert calls == ["two-sum"]


def test_start_never_writes_description_text_to_the_cache_file(cfg, monkeypatch):
    monkeypatch.setattr(workflow, "fetch_problem", lambda slug, **kw: P2)
    workflow.start_problem(cfg, "two-sum")
    cache_file = cfg.repo_path / ".lc" / "cache" / "two-sum.json"
    assert cache_file.exists()
    raw = cache_file.read_text(encoding="utf-8")
    assert SENTINEL not in raw


def test_cache_hit_produces_the_same_scaffold_as_a_cache_miss(cfg, monkeypatch):
    monkeypatch.setattr(workflow, "fetch_problem", lambda slug, **kw: P2)
    active = workflow.start_problem(cfg, "two-sum")
    miss_test = (cfg.repo_path / active.folder / "test_solution.py").read_text()
    assert "test_examples" in miss_test
    assert "pytest.skip" not in miss_test
    workflow.park_problem(cfg)

    # Force a fresh render on the next start: without this, start_problem's
    # "only write if missing" guard would just leave the first render in
    # place and this test would pass even if the cache hit degraded to ().
    shutil.rmtree(cfg.repo_path / active.folder)

    def fail_fetch(slug, **kw):
        raise AssertionError("fetch_problem must not be called on a cache hit")

    monkeypatch.setattr(workflow, "fetch_problem", fail_fetch)
    workflow.start_problem(cfg, "two-sum")
    hit_test = (cfg.repo_path / active.folder / "test_solution.py").read_text()
    assert hit_test == miss_test


# --- Ruling 2: .gitignore / .gitattributes must be committed with the first start ---

def test_start_commits_gitignore_and_gitattributes(cfg):
    workflow.start_problem(cfg, "two-sum")
    assert git(cfg.repo_path, "status", "--porcelain") == ""
    tracked = git(cfg.repo_path, "ls-files").splitlines()
    assert ".gitignore" in tracked
    assert ".gitattributes" in tracked


# --- Exception precision (robustness note) ---

def test_start_falls_back_when_number_given_and_leetcode_unavailable(cfg, monkeypatch):
    def unavailable(slug, **kw):
        raise LeetCodeUnavailable("rate limited")

    monkeypatch.setattr(workflow, "fetch_problem", unavailable)
    active = workflow.start_problem(cfg, "trapping-rain-water", number=42)
    assert active.id == 42
    assert active.title == "Trapping Rain Water"


def test_start_reraises_leetcode_unavailable_when_no_number_given(cfg, monkeypatch):
    def unavailable(slug, **kw):
        raise LeetCodeUnavailable("rate limited")

    monkeypatch.setattr(workflow, "fetch_problem", unavailable)
    with pytest.raises(LeetCodeUnavailable):
        workflow.start_problem(cfg, "two-sum")


def test_start_does_not_swallow_a_programming_error_as_unavailable(cfg, monkeypatch):
    def buggy(slug, **kw):
        raise TypeError("boom")

    monkeypatch.setattr(workflow, "fetch_problem", buggy)
    with pytest.raises(TypeError):
        workflow.start_problem(cfg, "two-sum", number=999)


# --- _patch_readme silent-no-op guard ---

def test_finish_raises_when_readme_markers_are_missing(cfg):
    active = workflow.start_problem(cfg, "two-sum")
    readme = cfg.repo_path / active.folder / "README.md"
    readme.write_text("no markers in here\n", encoding="utf-8")
    with pytest.raises(workflow.ReadmeUnpatched):
        workflow.finish_problem(cfg, "hash map", "O(n)", "O(n)")


# --- No active problem ---

def test_finish_raises_without_an_active_problem(cfg):
    with pytest.raises(workflow.NoActiveProblem):
        workflow.finish_problem(cfg, "hash map", "O(n)", "O(n)")


def test_park_raises_without_an_active_problem(cfg):
    with pytest.raises(workflow.NoActiveProblem):
        workflow.park_problem(cfg)
