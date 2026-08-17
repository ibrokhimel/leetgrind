"""Core workflow: turn a pasted link into a scaffolded, committed problem,
and a finished attempt into a tested, committed, pushed, closed one."""
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from . import editor
from .config import Config
from .examples import Example, extract_examples
from .leetcode import LeetCodeUnavailable, fetch_problem
from .models import Problem
from .repo import commit_paths, push
from .scaffold import render_files
from .state import (ActiveProblem, cache_get, cache_put, clear_active,
                    elapsed_minutes, load_active, save_active)
from .stats import render_root_readme, scan_solutions
from .urls import parse_slug

console = Console()


class ProblemActive(Exception):
    """A problem is already in progress; park or resume it first."""


class NoActiveProblem(Exception):
    """Nothing is in progress."""


class ReadmeUnpatched(Exception):
    """The problem README no longer has the markers finish/park expect to update."""


def fallback_problem(slug: str, number: int) -> Problem:
    """Minimal, usable metadata for when LeetCode cannot be reached."""
    title = " ".join(word.capitalize() for word in slug.split("-"))
    return Problem(id=number, slug=slug, title=title, difficulty="?",
                   tags=(), is_paid_only=False, stub=None, content_html=None)


def _from_cache(payload: dict) -> tuple[Problem, tuple[Example, ...]] | None:
    """None on a shape mismatch - a cache miss, not a crash."""
    try:
        p = payload["problem"]
        problem = Problem(id=p["id"], slug=p["slug"], title=p["title"],
                          difficulty=p["difficulty"], tags=tuple(p["tags"]),
                          is_paid_only=p["is_paid_only"], stub=p["stub"], content_html=None)
        examples = tuple(Example(args=tuple(e["args"]), expected=e["expected"])
                         for e in payload["examples"])
        return problem, examples
    except (KeyError, TypeError):
        return None


def _fetch_with_cache(repo: Path, slug: str,
                      number: int | None) -> tuple[Problem, tuple[Example, ...]]:
    """Cache lives here per ruling 1 (leetcode.py stays a pure network client).
    A hit skips extract_examples - no HTML to parse. Never persists
    content_html on either path - extract_examples is its only consumer."""
    cached = cache_get(repo, slug)
    hit = _from_cache(cached) if cached is not None else None
    if hit is not None:
        return hit

    try:
        problem = fetch_problem(slug)
    except LeetCodeUnavailable:
        if number is None:
            raise
        return fallback_problem(slug, number), ()
    examples = extract_examples(problem)
    data = asdict(problem) | {"content_html": None}
    cache_put(repo, slug, {"problem": data, "examples": [asdict(e) for e in examples]})
    return problem, examples


def _commit_and_push(cfg: Config, paths: list[Path], subject: str) -> bool:
    """False when nothing was staged. A failed push is always reported: the commit
    is safe locally, but the graph does not update until it reaches the remote."""
    committed = commit_paths(cfg.repo_path, paths, subject)
    if cfg.auto_push and not push(cfg.repo_path):
        console.print("[yellow]commit saved locally; push failed, will retry.[/]"
                      " Run `lc doctor`.")
    return committed


def start_problem(cfg: Config, text: str, *, number: int | None = None) -> ActiveProblem:
    if load_active(cfg.repo_path) is not None:
        raise ProblemActive("park or resume the active problem first")

    slug = parse_slug(text)
    problem, examples = _fetch_with_cache(cfg.repo_path, slug, number)

    folder = cfg.repo_path / problem.folder_name
    folder.mkdir(parents=True, exist_ok=True)
    for name, body in render_files(problem, examples).items():
        target = folder / name
        if not target.exists():
            target.write_text(body, encoding="utf-8")

    # Ruling 2: init_repo writes .gitignore/.gitattributes but never commits
    # them, so the first start must, or the working tree never goes clean.
    started = _commit_and_push(
        cfg, [folder, cfg.repo_path / ".gitignore", cfg.repo_path / ".gitattributes"],
        f"Start {problem.id}: {problem.title} ({problem.difficulty})")
    if not started:
        console.print(f"[yellow]Resuming {problem.folder_name}[/] - it was already "
                      "scaffolded, so this attempt has no new Start commit.")

    active = ActiveProblem(id=problem.id, slug=problem.slug, title=problem.title,
                           difficulty=problem.difficulty, folder=problem.folder_name,
                           started_at=datetime.now(timezone.utc).isoformat())
    save_active(cfg.repo_path, active)
    if not editor.open_problem(folder):
        console.print(f"[yellow]VS Code did not open.[/] Open {folder} yourself.")
    return active


def _patch_readme(path: Path, approach: str, time_c: str, space_c: str, minutes: int) -> None:
    text = path.read_text(encoding="utf-8")
    # re.subn reads its replacement as a *template*: a `\g<1>` typed into the
    # approach raises re.error and a `\n` injects a real newline. Doubling the
    # backslashes makes the user's text land verbatim.
    approach, time_c, space_c = (s.replace("\\", "\\\\") for s in (approach, time_c, space_c))
    text, n1 = re.subn(r"\*\*Approach:\*\*.*", f"**Approach:** {approach}", text, count=1)
    text, n2 = re.subn(r"\*\*Time:\*\*.*", f"**Time:** {time_c}  **Space:** {space_c}",
                       text, count=1)
    text, n3 = re.subn(r"\*\*Solved in:\*\*.*", f"**Solved in:** {minutes}m", text, count=1)
    if not (n1 and n2 and n3):
        # re.sub silently no-ops on a missing marker; that would let finish/park
        # commit a "Solve"/"Park" message while the README quietly kept its
        # placeholder text. Fail loudly instead of shipping a mismatch.
        raise ReadmeUnpatched(f"expected README markers missing: {path}")
    path.write_text(text, encoding="utf-8")


def _finalise(cfg: Config, active: ActiveProblem, subject: str) -> str:
    root_readme = cfg.repo_path / "README.md"
    root_readme.write_text(render_root_readme(scan_solutions(cfg.repo_path)), encoding="utf-8")
    _commit_and_push(cfg, [cfg.repo_path / active.folder, root_readme], subject)
    if cfg.auto_close:
        editor.close_window(active.folder)
    clear_active(cfg.repo_path)
    return subject


def finish_problem(cfg: Config, approach: str, time_c: str, space_c: str) -> str:
    active = load_active(cfg.repo_path)
    if active is None:
        raise NoActiveProblem("nothing in progress")
    _patch_readme(cfg.repo_path / active.folder / "README.md",
                  approach, time_c, space_c, elapsed_minutes(active))
    return _finalise(cfg, active,
                     f"Solve {active.id}: {active.title} ({approach}, {time_c})")


def park_problem(cfg: Config) -> str:
    active = load_active(cfg.repo_path)
    if active is None:
        raise NoActiveProblem("nothing in progress")
    _patch_readme(cfg.repo_path / active.folder / "README.md",
                  "parked", "-", "-", elapsed_minutes(active))
    return _finalise(cfg, active, f"Park {active.id}: {active.title} (unsolved)")
