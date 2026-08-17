import pytest
from typer.testing import CliRunner

from leetgrind import cli, workflow, doctor
from leetgrind.config import Config
from leetgrind.leetcode import LeetCodeUnavailable
from leetgrind.repo import GitError
from leetgrind.state import ActiveProblem

runner = CliRunner()


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    c = Config(repo_path=tmp_path)
    monkeypatch.setattr(cli, "load_config", lambda: c)
    return c


def test_new_calls_start_problem(cfg, monkeypatch):
    seen = {}
    monkeypatch.setattr(workflow, "start_problem",
                        lambda c, t, **k: seen.update(text=t) or
                        ActiveProblem(1, "two-sum", "Two Sum", "Easy", "0001-two-sum", "x"))
    result = runner.invoke(cli.app, ["new", "https://leetcode.com/problems/two-sum/"])
    assert result.exit_code == 0
    assert seen["text"] == "https://leetcode.com/problems/two-sum/"


def test_done_passes_prompts_through(cfg, monkeypatch):
    seen = {}
    monkeypatch.setattr(workflow, "finish_problem",
                        lambda c, a, t, s: seen.update(a=a, t=t, s=s) or "Solve 1: Two Sum (x, O(n))")
    result = runner.invoke(cli.app, ["done", "--approach", "hash map",
                                     "--time", "O(n)", "--space", "O(n)", "--force"])
    assert result.exit_code == 0
    assert seen == {"a": "hash map", "t": "O(n)", "s": "O(n)"}


def test_done_blocks_when_tests_fail_without_force(cfg, monkeypatch):
    from leetgrind.runner import TestOutcome
    from leetgrind.state import ActiveProblem, save_active
    save_active(cfg.repo_path, ActiveProblem(1, "two-sum", "Two Sum", "Easy", "0001-two-sum", "x"))
    monkeypatch.setattr(cli, "run_tests",
                        lambda folder: TestOutcome(False, "1 failed", "assert 7 == 9", False))
    result = runner.invoke(cli.app, ["done", "--approach", "x",
                                     "--time", "O(n)", "--space", "O(1)"])
    assert result.exit_code == 1
    assert "1 failed" in result.stdout


def test_doctor_exits_nonzero_when_a_check_fails(cfg, monkeypatch):
    monkeypatch.setattr(doctor, "run_checks",
                        lambda c: [doctor.Check("x", False, "broken", "fix it")])
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 1
    assert "broken" in result.stdout


def test_doctor_exits_zero_when_all_pass(cfg, monkeypatch):
    monkeypatch.setattr(doctor, "run_checks", lambda c: [doctor.Check("x", True, "fine")])
    assert runner.invoke(cli.app, ["doctor"]).exit_code == 0


def test_new_reports_an_already_active_problem(cfg, monkeypatch):
    def boom(*a, **k): raise workflow.ProblemActive("park it first")
    monkeypatch.setattr(workflow, "start_problem", boom)
    result = runner.invoke(cli.app, ["new", "two-sum"])
    assert result.exit_code == 1
    assert "park" in result.stdout.lower()


# --- Ruling 1: `lc new` must catch LeetCodeUnavailable and degrade, never traceback. ---

def test_new_degrades_when_leetcode_unavailable(cfg, monkeypatch):
    def boom(*a, **k): raise LeetCodeUnavailable("timeout")
    monkeypatch.setattr(workflow, "start_problem", boom)
    result = runner.invoke(cli.app, ["new", "two-sum"])
    assert result.exit_code == 1
    # A real traceback leaves result.exception as the raw LeetCodeUnavailable;
    # a clean typer.Exit(1) leaves it as SystemExit(1). Only the latter proves
    # the exception was actually caught, not merely of the "wrong type".
    assert isinstance(result.exception, SystemExit)
    assert "--number" in result.stdout


def test_daily_degrades_when_leetcode_unavailable(cfg, monkeypatch):
    def boom(*a, **k): raise LeetCodeUnavailable("timeout")
    monkeypatch.setattr(cli, "fetch_daily", boom)
    result = runner.invoke(cli.app, ["daily"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)


# --- Robustness note: `done` reads active before running tests; missing active
#     must be a clean message, never an AttributeError on None. ---

def test_done_reports_nothing_in_progress_when_none_active(cfg, monkeypatch):
    result = runner.invoke(cli.app, ["done", "--approach", "x",
                                     "--time", "O(n)", "--space", "O(1)"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "nothing in progress" in result.stdout.lower()


def test_done_force_flag_actually_skips_test_execution(cfg, monkeypatch):
    from leetgrind.state import ActiveProblem, save_active
    save_active(cfg.repo_path, ActiveProblem(1, "two-sum", "Two Sum", "Easy", "0001-two-sum", "x"))

    def must_not_run(folder):
        raise AssertionError("run_tests should not be called when --force is passed")
    monkeypatch.setattr(cli, "run_tests", must_not_run)
    monkeypatch.setattr(workflow, "finish_problem",
                        lambda c, a, t, s: "Solve 1: Two Sum (x, O(n))")
    result = runner.invoke(cli.app, ["done", "--approach", "x", "--time", "O(n)",
                                     "--space", "O(1)", "--force"])
    assert result.exit_code == 0


# --- Ruling 3: ReadmeUnpatched must be caught and presented cleanly in both
#     `lc done` and `lc park`. ---

def test_done_reports_readme_unpatched_cleanly(cfg, monkeypatch):
    def boom(*a, **k): raise workflow.ReadmeUnpatched("expected README markers missing: X/README.md")
    monkeypatch.setattr(workflow, "finish_problem", boom)
    result = runner.invoke(cli.app, ["done", "--approach", "x", "--time", "O(n)",
                                     "--space", "O(1)", "--force"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "README.md" in result.stdout


def test_park_reports_readme_unpatched_cleanly(cfg, monkeypatch):
    def boom(*a, **k): raise workflow.ReadmeUnpatched("expected README markers missing: X/README.md")
    monkeypatch.setattr(workflow, "park_problem", boom)
    result = runner.invoke(cli.app, ["park"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "README.md" in result.stdout


def test_park_reports_no_active_problem(cfg, monkeypatch):
    def boom(*a, **k): raise workflow.NoActiveProblem("nothing in progress")
    monkeypatch.setattr(workflow, "park_problem", boom)
    result = runner.invoke(cli.app, ["park"])
    assert result.exit_code == 1
    assert "nothing in progress" in result.stdout.lower()


# --- undo: git failure (e.g. no commits yet) must degrade cleanly, not traceback. ---

def test_undo_reports_git_error_cleanly(cfg, monkeypatch):
    def boom(repo):
        raise GitError("no commits yet")
    monkeypatch.setattr(cli, "undo_last", boom)
    result = runner.invoke(cli.app, ["undo"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "no commits yet" in result.stdout.lower()
