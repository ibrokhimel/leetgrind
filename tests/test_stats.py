from datetime import date, timedelta
from leetgrind.stats import SolvedEntry, scan_solutions, streak_days, render_root_readme


def write(repo, folder, body):
    (repo / folder).mkdir(parents=True)
    (repo / folder / "README.md").write_text(body, encoding="utf-8")


def test_scan_reads_metadata_from_problem_readmes(tmp_path):
    write(tmp_path, "0001-two-sum",
          "# 1. Two Sum\n\n**Difficulty:** Easy\n\n**Approach:** hash map\n")
    write(tmp_path, "0042-trapping-rain-water",
          "# 42. Trapping Rain Water\n\n**Difficulty:** Hard\n\n**Approach:** _(fill in when solved)_\n")
    entries = scan_solutions(tmp_path)
    assert [e.id for e in entries] == [1, 42]
    assert entries[0].status == "solved"
    assert entries[1].status == "in-progress"


def test_scan_ignores_non_problem_directories(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "scripts").mkdir()
    assert scan_solutions(tmp_path) == []


def test_streak_counts_consecutive_days_ending_today():
    today = date.today()
    assert streak_days([today, today - timedelta(days=1), today - timedelta(days=2)]) == 3


def test_streak_allows_yesterday_as_the_end():
    y = date.today() - timedelta(days=1)
    assert streak_days([y, y - timedelta(days=1)]) == 2


def test_streak_breaks_on_a_gap():
    today = date.today()
    assert streak_days([today, today - timedelta(days=3)]) == 1


def test_streak_of_no_commits_is_zero():
    assert streak_days([]) == 0


def test_root_readme_contains_a_row_per_problem():
    out = render_root_readme([SolvedEntry(1, "two-sum", "Two Sum", "Easy", "solved")])
    assert "| 1 |" in out
    assert "[Two Sum](0001-two-sum/)" in out
    assert "Easy" in out
