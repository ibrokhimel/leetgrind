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
    monkeypatch.setattr(cli, "last_subject", boom)
    result = runner.invoke(cli.app, ["undo"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "no commits yet" in result.stdout.lower()


# --- I1: `new` -> `undo` would delete the Start but leave state.json pointing at
#     the problem, so the next `done` yields a Solve with no Start. Refuse. ---

def test_undo_refuses_to_delete_the_active_problems_start_commit(cfg, monkeypatch):
    from leetgrind.state import save_active
    save_active(cfg.repo_path,
                ActiveProblem(1, "two-sum", "Two Sum", "Easy", "0001-two-sum", "x"))
    monkeypatch.setattr(cli, "last_subject", lambda repo: "Start 1: Two Sum (Easy)")
    def must_not_run(repo):
        raise AssertionError("undo_last must not run on the active Start commit")
    monkeypatch.setattr(cli, "undo_last", must_not_run)
    result = runner.invoke(cli.app, ["undo"])
    assert result.exit_code == 1
    assert "lc park" in result.stdout


def test_undo_still_works_on_an_unrelated_commit(cfg, monkeypatch):
    from leetgrind.state import save_active
    save_active(cfg.repo_path,
                ActiveProblem(2, "add-two", "Add Two", "Easy", "0002-add-two", "x"))
    monkeypatch.setattr(cli, "last_subject", lambda repo: "Start 1: Two Sum (Easy)")
    monkeypatch.setattr(cli, "undo_last", lambda repo: "Start 1: Two Sum (Easy)")
    assert runner.invoke(cli.app, ["undo"]).exit_code == 0


# --- C2: `lc` with no arguments must open the menu. The desktop shortcut runs
#     exactly this; without a callback Typer falls through to Click's help. ---

def test_no_arguments_opens_the_menu(monkeypatch):
    from leetgrind import menu
    opened = []
    monkeypatch.setattr(menu, "main", lambda: opened.append(True))
    result = runner.invoke(cli.app, [])
    assert opened == [True], "`lc` with no args must invoke menu.main()"
    assert result.exit_code == 0
    assert "Usage:" not in result.stdout


def test_subcommands_still_bypass_the_menu(cfg, monkeypatch):
    from leetgrind import menu
    def must_not_open():
        raise AssertionError("a subcommand must not open the menu")
    monkeypatch.setattr(menu, "main", must_not_open)
    monkeypatch.setattr(doctor, "run_checks", lambda c: [doctor.Check("x", True, "fine")])
    assert runner.invoke(cli.app, ["doctor"]).exit_code == 0


# --- I4: GitError must be rendered, never tracebacked, at every entry point. ---

@pytest.mark.parametrize("target,args", [
    ("start_problem", ["new", "two-sum"]),
    ("finish_problem", ["done", "--approach", "x", "--time", "O(n)",
                        "--space", "O(1)", "--force"]),
    ("park_problem", ["park"]),
])
def test_git_failures_are_reported_not_tracebacked(cfg, monkeypatch, target, args):
    def boom(*a, **k): raise GitError("fatal: Unable to create '.git/index.lock'")
    monkeypatch.setattr(workflow, target, boom)
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit), "GitError escaped as a traceback"
    assert "index.lock" in result.stdout


# --- M5: an empty approach must not produce `Solve 1: Two Sum (, O(n))`. ---

def test_done_substitutes_na_for_an_empty_approach(cfg, monkeypatch):
    seen = {}
    monkeypatch.setattr(workflow, "finish_problem",
                        lambda c, a, t, s: seen.update(a=a, t=t, s=s) or "Solve 1: x")
    result = runner.invoke(cli.app, ["done", "--approach", "", "--time", "",
                                     "--space", "", "--force"])
    assert result.exit_code == 0
    assert seen == {"a": "n/a", "t": "n/a", "s": "n/a"}


# --- I5: `lc config` is the only way back from a moved solutions repo. ---

def test_config_shows_settings(cfg):
    result = runner.invoke(cli.app, ["config"])
    assert result.exit_code == 0
    assert "repo_path" in result.stdout


def test_config_repoints_repo_path(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    from leetgrind.config import load_config
    moved = tmp_path / "moved"
    result = runner.invoke(cli.app, ["config", "--repo-path", str(moved)])
    assert result.exit_code == 0
    assert load_config().repo_path == moved


def test_config_reports_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    result = runner.invoke(cli.app, ["config"])
    assert result.exit_code == 1
    assert "not configured" in result.stdout.lower()
