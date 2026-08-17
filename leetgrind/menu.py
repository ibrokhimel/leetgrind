"""The launcher's home screen: a solved-count/streak header, a menu, and
the paste-link -> solve -> commit loop."""
from datetime import datetime
from pathlib import Path

import questionary
from rich.console import Console

from . import doctor as doctor_mod
from . import workflow
from .config import load_config
from .leetcode import fetch_daily
from .repo import git
from .runner import run_tests
from .stats import scan_solutions, streak_days
from .wizard import first_run

console = Console()


def _header(cfg) -> str:
    entries = scan_solutions(cfg.repo_path)
    solved = sum(1 for e in entries if e.status == "solved")
    try:
        # A fresh repo has no commits yet: `git log` exits non-zero and
        # raises GitError. Malformed commit dates would also land here.
        # Either way, fall back to an empty streak instead of crashing.
        dates = [datetime.fromisoformat(d).date()
                 for d in git(cfg.repo_path, "log", "--pretty=%cI").splitlines()]
    except Exception:
        dates = []
    return f"{solved} solved · {streak_days(dates)} day streak"


def _ensure_config():
    cfg = load_config()
    if cfg is not None:
        return cfg
    console.print("[bold]First run — let's set up your solutions repo.[/]")
    repo = questionary.path(
        "Where should solutions live?",
        default=str(Path.home() / "Documents" / "leetcode-solutions")).ask()
    push = questionary.confirm("Push after every commit?").ask()
    return first_run({"repo_path": repo, "auto_push": push})


def _solve_loop(cfg, active) -> None:
    while True:
        choice = questionary.select(
            f"Solving {active.id}: {active.title}",
            choices=["Done — test and commit", "Park — give up for now"]).ask()
        if choice is None or choice.startswith("Park"):
            try:
                console.print(f"[yellow]{workflow.park_problem(cfg)}[/]")
            except workflow.ReadmeUnpatched as exc:
                console.print(f"[red]Could not park: {exc}[/]\n"
                              "Fix the README markers by hand, then try again.")
            return
        outcome = run_tests(cfg.repo_path / active.folder)
        if not outcome.passed and cfg.gate_on_tests:
            console.print(f"[red]{outcome.summary}[/]\n{outcome.output}")
            if not questionary.confirm("Commit anyway?", default=False).ask():
                continue
        approach = questionary.text("Approach:").ask() or "n/a"
        time_c = questionary.text("Time complexity:", default="O(n)").ask()
        space_c = questionary.text("Space complexity:", default="O(1)").ask()
        try:
            result = workflow.finish_problem(cfg, approach, time_c, space_c)
        except workflow.ReadmeUnpatched as exc:
            # finish_problem/park_problem raise this when a hand-edited
            # README lost its marker lines. A traceback must never reach
            # the user - name the file and let them fix it and retry.
            console.print(f"[red]Could not save: {exc}[/]\n"
                          "Fix the README markers by hand, then finish again.")
            return
        console.print(f"[green]{result}[/]")
        return


def main() -> None:
    cfg = _ensure_config()
    while True:
        console.rule(f"LEETGRIND — {_header(cfg)}")
        choice = questionary.select("What now?", choices=[
            "Start coding", "Today's daily", "Doctor", "Quit"]).ask()
        if choice is None or choice == "Quit":
            return
        if choice == "Doctor":
            for check in doctor_mod.run_checks(cfg):
                console.print(("[green]OK  [/]" if check.ok else "[red]FAIL[/]")
                              + f" {check.name} — {check.detail}")
            continue
        text = fetch_daily() if choice == "Today's daily" else questionary.text("Link:").ask()
        if not text:
            continue
        try:
            active = workflow.start_problem(cfg, text)
        except Exception as exc:
            console.print(f"[red]{exc}[/]")
            continue
        _solve_loop(cfg, active)
