"""Typer CLI: new, done, park, daily, undo, doctor.

`lc` with no subcommand launches the menu (Task 14); the commands here
remain available for direct, scriptable use.
"""
import typer
from rich.console import Console

from . import doctor as doctor_mod
from . import workflow
from .config import load_config
from .leetcode import LeetCodeUnavailable, fetch_daily
from .repo import GitError, undo_last
from .runner import run_tests
from .state import load_active

app = typer.Typer(add_completion=False, help="LeetCode solve loop automation.")
console = Console()

NUMBER_HINT = ("Could not reach LeetCode. "
              "Re-run with --number <n> to scaffold offline.")


def _require_config():
    cfg = load_config()
    if cfg is None:
        console.print("[red]Not configured.[/] Run `lc` and complete first-run setup.")
        raise typer.Exit(1)
    return cfg


@app.command()
def new(text: str, number: int = typer.Option(None, help="Problem number if offline")):
    """Scaffold a problem, commit, and open VS Code."""
    cfg = _require_config()
    try:
        active = workflow.start_problem(cfg, text, number=number)
    except workflow.ProblemActive as exc:
        console.print(f"[red]{exc}[/] Use `lc park` or `lc done` first.")
        raise typer.Exit(1)
    except LeetCodeUnavailable:
        console.print(f"[red]{NUMBER_HINT}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Started[/] {active.id}: {active.title} ({active.difficulty})")


@app.command()
def done(approach: str = typer.Option(..., prompt=True),
         time: str = typer.Option(..., prompt="Time complexity"),
         space: str = typer.Option(..., prompt="Space complexity"),
         force: bool = typer.Option(False, help="Commit even if tests fail")):
    """Test, commit, push, and close the window."""
    cfg = _require_config()

    # The test gate needs active.folder, so it must confirm a problem is
    # active before touching it - never assume load_active() is non-None.
    if cfg.gate_on_tests and not force:
        active = load_active(cfg.repo_path)
        if active is None:
            console.print("[red]Nothing in progress.[/]")
            raise typer.Exit(1)
        outcome = run_tests(cfg.repo_path / active.folder)
        if not outcome.passed:
            console.print(f"[red]{outcome.summary}[/]\n{outcome.output}")
            console.print("[dim]re-run with --force to commit anyway, "
                          "or `lc park` to shelve it[/]")
            raise typer.Exit(1)

    try:
        subject = workflow.finish_problem(cfg, approach, time, space)
    except workflow.NoActiveProblem:
        console.print("[red]Nothing in progress.[/]")
        raise typer.Exit(1)
    except workflow.ReadmeUnpatched as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Committed[/] {subject}")


@app.command()
def park():
    """Record the current attempt as unsolved and move on."""
    cfg = _require_config()
    try:
        subject = workflow.park_problem(cfg)
    except workflow.NoActiveProblem as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    except workflow.ReadmeUnpatched as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    console.print(f"[yellow]Parked[/] {subject}")


@app.command()
def daily():
    """Start today's LeetCode daily challenge."""
    try:
        slug = fetch_daily()
    except LeetCodeUnavailable:
        console.print("[red]Could not reach LeetCode for the daily challenge.[/] "
                      "Find today's slug and run `lc new <slug> --number <n>` instead.")
        raise typer.Exit(1)
    new(slug, number=None)


@app.command()
def undo():
    """Soft-reset the most recent commit."""
    cfg = _require_config()
    try:
        subject = undo_last(cfg.repo_path)
    except GitError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    console.print(f"[yellow]Undid[/] {subject}")


@app.command()
def doctor():
    """Diagnose environment and contribution-graph problems."""
    checks = doctor_mod.run_checks(load_config())
    for check in checks:
        mark = "[green]OK  [/]" if check.ok else "[red]FAIL[/]"
        console.print(f"{mark} {check.name} - {check.detail}")
        if not check.ok and check.fix:
            console.print(f"     [dim]fix:[/] {check.fix}")
    raise typer.Exit(0 if all(c.ok for c in checks) else 1)
