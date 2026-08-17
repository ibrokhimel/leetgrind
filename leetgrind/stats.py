import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

_FOLDER_RE = re.compile(r"^(\d{4})-([a-z0-9-]+)$")
_TITLE_RE = re.compile(r"^#\s*\d+\.\s*(.+)$", re.MULTILINE)
_DIFF_RE = re.compile(r"\*\*Difficulty:\*\*\s*(\w+)")
_APPROACH_RE = re.compile(r"\*\*Approach:\*\*\s*(.+)")
_UNFILLED = "_(fill in when solved)_"


@dataclass
class SolvedEntry:
    id: int
    slug: str
    title: str
    difficulty: str
    status: str  # solved | in-progress | parked


def scan_solutions(repo: Path) -> list[SolvedEntry]:
    if not repo.is_dir():
        # menu._header calls this on every render. A moved, renamed, or
        # disconnected solutions repo must degrade to "0 solved" so the menu
        # still draws and `lc config --repo-path` is reachable.
        return []
    entries: list[SolvedEntry] = []
    for child in sorted(repo.iterdir()):
        if not child.is_dir() or not (m := _FOLDER_RE.match(child.name)):
            continue
        readme = child / "README.md"
        if not readme.exists():
            continue
        text = readme.read_text(encoding="utf-8")
        approach = (_APPROACH_RE.search(text) or [None, ""])[1].strip()
        status = "parked" if approach == "parked" else (
            "in-progress" if approach in ("", _UNFILLED) else "solved")
        entries.append(SolvedEntry(
            id=int(m.group(1)), slug=m.group(2),
            title=(_TITLE_RE.search(text) or [None, m.group(2)])[1].strip(),
            difficulty=(_DIFF_RE.search(text) or [None, "?"])[1],
            status=status))
    return entries


def streak_days(commit_dates: list[date]) -> int:
    if not commit_dates:
        return 0
    days = sorted(set(commit_dates), reverse=True)
    today = date.today()
    if days[0] not in (today, today - timedelta(days=1)):
        return 0
    streak, cursor = 1, days[0]
    for day in days[1:]:
        if day == cursor - timedelta(days=1):
            streak, cursor = streak + 1, day
        else:
            break
    return streak


def render_root_readme(entries: list[SolvedEntry]) -> str:
    solved = sum(1 for e in entries if e.status == "solved")
    counts = {d: sum(1 for e in entries if e.difficulty == d and e.status == "solved")
              for d in ("Easy", "Medium", "Hard")}
    lines = [
        "# LeetCode Solutions", "",
        f"**{solved} solved** — "
        f"{counts['Easy']} Easy · {counts['Medium']} Medium · {counts['Hard']} Hard", "",
        "| # | Problem | Difficulty | Status |", "|---|---|---|---|",
    ]
    for e in entries:
        lines.append(f"| {e.id} | [{e.title}]({e.id:04d}-{e.slug}/) "
                     f"| {e.difficulty} | {e.status} |")
    return "\n".join(lines) + "\n"
