import questionary
import pytest

from leetgrind import editor, menu, workflow
from leetgrind.config import Config
from leetgrind.models import Problem
from leetgrind.repo import git, init_repo
from leetgrind.runner import TestOutcome as _Outcome
from leetgrind.state import load_active

P = Problem(id=1, slug="two-sum", title="Two Sum", difficulty="Easy",
            tags=("array",), is_paid_only=False,
            stub="class Solution:\n    def twoSum(self, nums, target):\n        return [0,1]\n",
            content_html=None)


class _Ask:
    """Fake questionary Question: .ask() returns a pre-queued value."""

    def __init__(self, value):
        self._value = value

    def ask(self):
        return self._value


def _queue(monkeypatch, name, values):
    """Monkeypatch questionary.<name> to hand back `values` in call order."""
    it = iter(values)
    monkeypatch.setattr(questionary, name, lambda *a, **kw: _Ask(next(it)))


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    repo = tmp_path / "solutions"
    init_repo(repo)
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    monkeypatch.setattr(workflow, "fetch_problem", lambda slug, **kw: P)
    monkeypatch.setattr(editor, "open_problem", lambda folder: True)
    monkeypatch.setattr(editor, "close_window", lambda name: True)
    return Config(repo_path=repo, auto_push=False)


# --- Hard requirement 5: no crash computing the streak on a fresh repo ---

def test_header_survives_a_repo_with_no_commits(cfg):
    header = menu._header(cfg)
    assert header == "0 solved · 0 day streak"


def test_main_does_not_crash_on_a_fresh_repo_then_quits(cfg, monkeypatch):
    monkeypatch.setattr(menu, "load_config", lambda: cfg)
    _queue(monkeypatch, "select", ["Quit"])
    menu.main()  # must not raise


# --- Hard requirement 1: ReadmeUnpatched must never surface as a traceback ---

def test_solve_loop_reports_readme_unpatched_on_finish_instead_of_crashing(
        cfg, monkeypatch, capsys):
    active = workflow.start_problem(cfg, "two-sum")
    readme = cfg.repo_path / active.folder / "README.md"
    readme.write_text("hand-edited, markers gone\n", encoding="utf-8")

    monkeypatch.setattr(menu, "run_tests",
                         lambda folder: _Outcome(True, "1 passed", "", False))
    _queue(monkeypatch, "select", ["Done — test and commit"])
    _queue(monkeypatch, "text", ["hash map", "O(n)", "O(n)"])

    menu._solve_loop(cfg, active)  # must not raise

    out = capsys.readouterr().out
    assert "README.md" in out
    assert str(readme) in out or readme.name in out
    # The attempt is still active - nothing was silently discarded.
    assert load_active(cfg.repo_path) is not None


def test_solve_loop_reports_readme_unpatched_on_park_instead_of_crashing(
        cfg, monkeypatch, capsys):
    active = workflow.start_problem(cfg, "two-sum")
    readme = cfg.repo_path / active.folder / "README.md"
    readme.write_text("hand-edited, markers gone\n", encoding="utf-8")

    _queue(monkeypatch, "select", ["Park — give up for now"])

    menu._solve_loop(cfg, active)  # must not raise

    out = capsys.readouterr().out
    assert "README.md" in out
    assert load_active(cfg.repo_path) is not None


# --- Ordinary solve-loop paths ---

def test_solve_loop_parks_cleanly_when_readme_is_intact(cfg, monkeypatch):
    active = workflow.start_problem(cfg, "two-sum")
    _queue(monkeypatch, "select", ["Park — give up for now"])
    menu._solve_loop(cfg, active)
    assert load_active(cfg.repo_path) is None


def test_solve_loop_finishes_cleanly_when_tests_pass(cfg, monkeypatch):
    active = workflow.start_problem(cfg, "two-sum")
    monkeypatch.setattr(menu, "run_tests",
                         lambda folder: _Outcome(True, "1 passed", "", False))
    _queue(monkeypatch, "select", ["Done — test and commit"])
    _queue(monkeypatch, "text", ["hash map", "O(n)", "O(n)"])
    menu._solve_loop(cfg, active)
    assert load_active(cfg.repo_path) is None
    assert git(cfg.repo_path, "log", "-1", "--pretty=%s") == "Solve 1: Two Sum (hash map, O(n))"


def test_solve_loop_gate_blocks_a_failing_commit_until_confirmed(cfg, monkeypatch):
    active = workflow.start_problem(cfg, "two-sum")
    monkeypatch.setattr(
        menu, "run_tests",
        lambda folder: _Outcome(False, "1 failed", "boom", False))
    # First iteration: refuse to commit anyway -> loop back to the select
    # prompt; second iteration: park to end the test cleanly.
    _queue(monkeypatch, "select",
           ["Done — test and commit", "Park — give up for now"])
    _queue(monkeypatch, "confirm", [False])
    menu._solve_loop(cfg, active)
    assert load_active(cfg.repo_path) is None


# --- Doctor path must never shell out to real `gh` from a test ---

def test_doctor_choice_uses_only_the_mocked_checks(cfg, monkeypatch):
    monkeypatch.setattr(menu, "load_config", lambda: cfg)
    monkeypatch.setattr(menu.doctor_mod, "run_checks", lambda c: [])
    _queue(monkeypatch, "select", ["Doctor", "Quit"])
    menu.main()  # must not raise, must not touch the network or `gh`


# --- First-run path inside main() ---

def test_main_runs_the_first_run_wizard_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    repo = tmp_path / "solutions"
    monkeypatch.setattr(questionary, "path", lambda *a, **kw: _Ask(str(repo)))
    monkeypatch.setattr(questionary, "confirm", lambda *a, **kw: _Ask(False))
    _queue(monkeypatch, "select", ["Quit"])
    menu.main()
    assert (repo / ".git").is_dir()
