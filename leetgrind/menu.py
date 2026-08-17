"""The launcher's home screen: a solved-count/streak header, a menu, and
the paste-link -> solve -> commit loop."""
from datetime import datetime
from pathlib import Path

import questionary
from rich.console import Console

from . import doctor as doctor_mod
from . import workflow
from .config import load_config
from .leetcode import LeetCodeUnavailable, fetch_daily
from .repo import GitError, create_github_repo, git, remote_url, set_remote
from .runner import run_tests
from .state import load_active
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
    if repo is None:
        console.print("[yellow]Setup cancelled.[/]")
        return None
    push = questionary.confirm("Push after every commit?").ask()
    cfg = first_run({"repo_path": repo, "auto_push": bool(push)})
    _ensure_remote(cfg)
    return cfg


def _ensure_remote(cfg) -> None:
    """No remote means every commit stays on this machine and the contribution
    graph - the whole point - stays empty. Public by default (spec:165-166):
    private-repo commits show only as unlabeled squares, and only if the user
    has opted into private contributions."""
    if remote_url(cfg.repo_path):
        return
    if questionary.confirm("Create a public GitHub repo now (gh repo create)?",
                           default=True).ask():
        ok, detail = create_github_repo(cfg.repo_path)
        # style=, not markup: gh's stderr routinely contains square brackets.
        console.print(detail, style="green" if ok else "red")
        if ok:
            return
    url = questionary.text("Remote URL (blank to skip - commits stay local):").ask()
    if url:
        try:
            set_remote(cfg.repo_path, url)
        except GitError as exc:
            console.print(f"[red]{exc}[/]")


def _park(cfg) -> None:
    try:
        console.print(f"[yellow]{workflow.park_problem(cfg)}[/]")
    except workflow.ReadmeUnpatched as exc:
        console.print(f"[red]Could not park: {exc}[/]\n"
                      "Fix the README markers by hand, then try again.")
    except (workflow.NoActiveProblem, GitError) as exc:
        console.print(f"[red]Could not park: {exc}[/]")


def _solve_loop(cfg, active) -> None:
    while True:
        choice = questionary.select(
            f"Solving {active.id}: {active.title}",
            choices=["Done — test and commit", "Park — give up for now"]).ask()
        if choice is None or choice.startswith("Park"):
            _park(cfg)
            return
        outcome = run_tests(cfg.repo_path / active.folder)
        if not outcome.passed and cfg.gate_on_tests:
            console.print(f"[red]{outcome.summary}[/]\n{outcome.output}")
            if not questionary.confirm("Commit anyway?", default=False).ask():
                continue
        approach = questionary.text("Approach:").ask() or "n/a"
        time_c = questionary.text("Time complexity:", default="O(n)").ask() or "n/a"
        space_c = questionary.text("Space complexity:", default="O(1)").ask() or "n/a"
        try:
            result = workflow.finish_problem(cfg, approach, time_c, space_c)
        except workflow.ReadmeUnpatched as exc:
            # finish_problem/park_problem raise this when a hand-edited
            # README lost its marker lines. A traceback must never reach
            # the user - name the file and let them fix it and retry.
            console.print(f"[red]Could not save: {exc}[/]\n"
                          "Fix the README markers by hand, then finish again.")
            return
        except GitError as exc:
            console.print(f"[red]git failed: {exc}[/]\nThe attempt is still "
                          "active - fix the repo and finish again.")
            return
        console.print(f"[green]{result}[/]")
        return


def main() -> None:
    cfg = _ensure_config()
    if cfg is None:
        return
    while True:
        console.rule(f"LEETGRIND — {_header(cfg)}")
        # Without Resume/Park a stale active problem soft-locks the menu:
        # start_problem raises ProblemActive forever and a shortcut-only user
        # has no terminal to escape from.
        stale = load_active(cfg.repo_path)
        choices = ["Start coding", "Today's daily", "Doctor", "Quit"]
        if stale is not None:
            choices[:0] = [f"Resume {stale.id}: {stale.title}",
                           f"Park {stale.id} — give up for now"]
        choice = questionary.select("What now?", choices=choices).ask()
        if choice is None or choice == "Quit":
            return
        if choice.startswith("Resume"):
            _solve_loop(cfg, stale)
            continue
        if choice.startswith("Park"):
            _park(cfg)
            continue
        if choice == "Doctor":
            for check in doctor_mod.run_checks(cfg):
                console.print(("[green]OK  [/]" if check.ok else "[red]FAIL[/]")
                              + f" {check.name} — {check.detail}")
            continue
        try:
            text = (fetch_daily() if choice == "Today's daily"
                    else questionary.text("Link:").ask())
        except LeetCodeUnavailable:
            console.print("[red]Could not reach LeetCode for the daily challenge.[/] "
                          "Find today's slug and paste it under Start coding.")
            continue
        if not text:
            continue
        try:
            active = workflow.start_problem(cfg, text)
        except Exception as exc:
            console.print(f"[red]{exc}[/]")
            continue
        _solve_loop(cfg, active)
