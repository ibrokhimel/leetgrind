# LeetGrind Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that turns "paste a LeetCode link" into a scaffolded folder, an open VS Code window, and two real commits per solved problem.

**Architecture:** Ten small single-responsibility modules behind a Typer CLI and a questionary menu. Pure logic (slug parsing, template rendering, stats) is separated from I/O (HTTP, git, filesystem, editor) so the bulk of the system is testable without mocks. `editor.py` quarantines the one inherently fragile behaviour — closing a VS Code window by title match.

**Tech Stack:** Python 3.12, Typer, httpx, Rich, questionary, tomli-w, pyperclip. Tests: pytest, respx.

**Spec:** `docs/superpowers/specs/2026-08-17-leetgrind-design.md`

## Global Constraints

- Python >= 3.12. Use `tomllib` (stdlib) to read TOML, `tomli-w` to write it.
- No source file over 150 lines. If a task's file exceeds it, split by responsibility.
- **Never write LeetCode problem description text to disk.** Metadata, link, tags, and user-authored summary only. Extracted example values in test files are permitted.
- **Always use `questionFrontendId`**, never `questionId`. The latter is an internal id that does not match the site.
- All tests mock the network. The one live test is marked `@pytest.mark.live` and deselected by default.
- Config lives in `%APPDATA%\leetgrind\config.toml`, never inside the solutions repo.
- Every failure path degrades to a working state. The loop must never strand the user.
- Commit messages must not include a `Co-Authored-By` trailer.
- Two repos: this tool repo, and the separate solutions repo the tool writes into.

---

### Task 1: Project skeleton and configuration

**Files:**
- Create: `pyproject.toml`
- Create: `leetgrind/__init__.py`
- Create: `leetgrind/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Config` dataclass with fields `repo_path: Path`, `language: str`, `auto_close: bool`, `auto_push: bool`, `gate_on_tests: bool`, `open_browser: bool`, `active_list: str`, `clipboard_hint: bool`. Functions `config_path() -> Path`, `load_config() -> Config | None`, `save_config(cfg: Config) -> None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from pathlib import Path
from leetgrind.config import Config, load_config, save_config

def test_save_then_load_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    cfg = Config(repo_path=Path("C:/repos/leetcode-solutions"), auto_push=False)
    save_config(cfg)
    assert load_config() == cfg

def test_load_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert load_config() is None

def test_defaults_are_applied_for_missing_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from leetgrind.config import config_path
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text('repo_path = "C:/x"\n', encoding="utf-8")
    cfg = load_config()
    assert cfg.language == "python"
    assert cfg.auto_close is True
    assert cfg.gate_on_tests is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.config'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[project]
name = "leetgrind"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "typer>=0.12", "httpx>=0.27", "rich>=13.7",
    "questionary>=2.0", "tomli-w>=1.0", "pyperclip>=1.8",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "respx>=0.21"]

[project.scripts]
lc = "leetgrind.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
markers = ["live: hits the real LeetCode API (deselected by default)"]
addopts = "-m 'not live'"
```

```python
# leetgrind/config.py
import os
import tomllib
from dataclasses import dataclass, asdict, fields
from pathlib import Path

import tomli_w


@dataclass
class Config:
    repo_path: Path
    language: str = "python"
    auto_close: bool = True
    auto_push: bool = True
    gate_on_tests: bool = True
    open_browser: bool = False
    active_list: str = "blind75"
    clipboard_hint: bool = True


def config_path() -> Path:
    base = os.environ.get("APPDATA") or Path.home() / ".config"
    return Path(base) / "leetgrind" / "config.toml"


def load_config() -> Config | None:
    path = config_path()
    if not path.exists():
        return None
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Config)}
    data = {k: v for k, v in raw.items() if k in known}
    data["repo_path"] = Path(data["repo_path"])
    return Config(**data)


def save_config(cfg: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    data["repo_path"] = cfg.repo_path.as_posix()
    path.write_text(tomli_w.dumps(data), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -e ".[dev]"` then `pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml leetgrind/ tests/
git commit -m "feat: project skeleton and configuration"
```

---

### Task 2: URL and slug parsing

**Files:**
- Create: `leetgrind/urls.py`
- Test: `tests/test_urls.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `parse_slug(text: str) -> str` — raises `ValueError` on unparseable input.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_urls.py
import pytest
from leetgrind.urls import parse_slug

@pytest.mark.parametrize("text,expected", [
    ("https://leetcode.com/problems/two-sum/", "two-sum"),
    ("https://leetcode.com/problems/two-sum", "two-sum"),
    ("http://leetcode.com/problems/trapping-rain-water/description/", "trapping-rain-water"),
    ("https://leetcode.com/problems/two-sum/?envType=daily-question&envId=2026-08-17", "two-sum"),
    ("https://leetcode.cn/problems/two-sum/", "two-sum"),
    ("leetcode.com/problems/two-sum/", "two-sum"),
    ("  https://leetcode.com/problems/two-sum/  ", "two-sum"),
    ("two-sum", "two-sum"),
    ("Two Sum", "two-sum"),
])
def test_parse_slug(text, expected):
    assert parse_slug(text) == expected

@pytest.mark.parametrize("bad", ["", "   ", "https://example.com/", "https://leetcode.com/contest/x/"])
def test_parse_slug_rejects(bad):
    with pytest.raises(ValueError):
        parse_slug(bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_urls.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.urls'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/urls.py
import re

_URL_RE = re.compile(r"leetcode\.(?:com|cn)/problems/([a-z0-9-]+)", re.IGNORECASE)
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_slug(text: str) -> str:
    """Extract a LeetCode problem slug from a URL, bare slug, or plain title."""
    text = text.strip()
    if not text:
        raise ValueError("empty input")

    if match := _URL_RE.search(text):
        return match.group(1).lower()

    if "/" in text or "leetcode." in text.lower():
        raise ValueError(f"not a LeetCode problem URL: {text!r}")

    candidate = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not candidate or not _SLUG_RE.match(candidate):
        raise ValueError(f"cannot derive a slug from: {text!r}")
    return candidate
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_urls.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add leetgrind/urls.py tests/test_urls.py
git commit -m "feat: parse problem slugs from URLs, slugs, and titles"
```

---

### Task 3: Problem model and GraphQL client

**Files:**
- Create: `leetgrind/models.py`
- Create: `leetgrind/leetcode.py`
- Test: `tests/test_leetcode.py`
- Test: `tests/fixtures/two-sum.json`

**Interfaces:**
- Consumes: `parse_slug` from Task 2.
- Produces:
  - `Problem` frozen dataclass: `id: int`, `slug: str`, `title: str`, `difficulty: str`, `tags: tuple[str, ...]`, `is_paid_only: bool`, `stub: str | None`, `content_html: str | None`.
  - `QUESTION_QUERY: str` — the pinned GraphQL document.
  - `fetch_problem(slug: str, *, client: httpx.Client | None = None) -> Problem` — raises `LeetCodeUnavailable` on any network or shape failure.
  - `fetch_daily(*, client=None) -> str` returning today's slug.
  - `LeetCodeUnavailable(Exception)`.

- [ ] **Step 1: Write the failing test**

Create `tests/fixtures/two-sum.json` with a trimmed real response:

```json
{"data":{"question":{"questionFrontendId":"1","questionId":"1","title":"Two Sum","titleSlug":"two-sum","difficulty":"Easy","isPaidOnly":false,"topicTags":[{"slug":"array"},{"slug":"hash-table"}],"content":"<p>Given an array...</p>","codeSnippets":[{"langSlug":"python3","code":"class Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:\n        "},{"langSlug":"java","code":"class Solution {}"}]}}}
```

```python
# tests/test_leetcode.py
import json
from pathlib import Path
import httpx, pytest, respx
from leetgrind.leetcode import fetch_problem, fetch_daily, LeetCodeUnavailable

FIXTURE = json.loads((Path(__file__).parent / "fixtures/two-sum.json").read_text())

@respx.mock
def test_fetch_problem_parses_metadata():
    respx.post("https://leetcode.com/graphql").mock(return_value=httpx.Response(200, json=FIXTURE))
    p = fetch_problem("two-sum")
    assert p.id == 1
    assert p.title == "Two Sum"
    assert p.difficulty == "Easy"
    assert p.tags == ("array", "hash-table")
    assert p.is_paid_only is False
    assert "def twoSum" in p.stub

@respx.mock
def test_fetch_problem_raises_on_http_error():
    respx.post("https://leetcode.com/graphql").mock(return_value=httpx.Response(429))
    with pytest.raises(LeetCodeUnavailable):
        fetch_problem("two-sum")

@respx.mock
def test_fetch_problem_raises_on_unknown_slug():
    respx.post("https://leetcode.com/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"question": None}}))
    with pytest.raises(LeetCodeUnavailable):
        fetch_problem("nope")

@respx.mock
def test_fetch_problem_raises_on_shape_change():
    respx.post("https://leetcode.com/graphql").mock(
        return_value=httpx.Response(200, json={"data": {"question": {"title": "x"}}}))
    with pytest.raises(LeetCodeUnavailable):
        fetch_problem("two-sum")

@respx.mock
def test_fetch_daily_returns_slug():
    respx.post("https://leetcode.com/graphql").mock(return_value=httpx.Response(200, json={
        "data": {"activeDailyCodingChallengeQuestion": {"question": {"titleSlug": "trapping-rain-water"}}}}))
    assert fetch_daily() == "trapping-rain-water"

@respx.mock
def test_paid_only_problem_has_no_stub():
    payload = json.loads(json.dumps(FIXTURE))
    payload["data"]["question"]["isPaidOnly"] = True
    payload["data"]["question"]["content"] = None
    payload["data"]["question"]["codeSnippets"] = None
    respx.post("https://leetcode.com/graphql").mock(return_value=httpx.Response(200, json=payload))
    p = fetch_problem("two-sum")
    assert p.is_paid_only is True
    assert p.stub is None
    assert p.content_html is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_leetcode.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.leetcode'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/models.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Problem:
    id: int
    slug: str
    title: str
    difficulty: str
    tags: tuple[str, ...]
    is_paid_only: bool
    stub: str | None
    content_html: str | None

    @property
    def folder_name(self) -> str:
        return f"{self.id:04d}-{self.slug}"
```

```python
# leetgrind/leetcode.py
import httpx
from .models import Problem

ENDPOINT = "https://leetcode.com/graphql"
_HEADERS = {"Referer": "https://leetcode.com", "User-Agent": "leetgrind/0.1"}

QUESTION_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionFrontendId title titleSlug difficulty isPaidOnly content
    topicTags { slug }
    codeSnippets { langSlug code }
  }
}"""

DAILY_QUERY = """
query { activeDailyCodingChallengeQuestion { question { titleSlug } } }"""


class LeetCodeUnavailable(Exception):
    """LeetCode could not be reached or returned something unusable."""


def _post(query: str, variables: dict, client: httpx.Client | None) -> dict:
    owned = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        resp = client.post(ENDPOINT, json={"query": query, "variables": variables},
                           headers=_HEADERS)
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise LeetCodeUnavailable(str(exc)) from exc
    finally:
        if owned:
            client.close()


def fetch_problem(slug: str, *, client: httpx.Client | None = None) -> Problem:
    payload = _post(QUESTION_QUERY, {"titleSlug": slug}, client)
    q = (payload.get("data") or {}).get("question")
    if not q:
        raise LeetCodeUnavailable(f"no such problem: {slug}")
    try:
        snippets = q.get("codeSnippets") or []
        stub = next((s["code"] for s in snippets if s["langSlug"] == "python3"), None)
        return Problem(
            id=int(q["questionFrontendId"]),
            slug=q["titleSlug"],
            title=q["title"],
            difficulty=q["difficulty"],
            tags=tuple(t["slug"] for t in (q.get("topicTags") or [])),
            is_paid_only=bool(q.get("isPaidOnly")),
            stub=stub,
            content_html=q.get("content"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LeetCodeUnavailable(f"unexpected response shape: {exc}") from exc


def fetch_daily(*, client: httpx.Client | None = None) -> str:
    payload = _post(DAILY_QUERY, {}, client)
    try:
        return payload["data"]["activeDailyCodingChallengeQuestion"]["question"]["titleSlug"]
    except (KeyError, TypeError) as exc:
        raise LeetCodeUnavailable(f"unexpected daily response: {exc}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_leetcode.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add leetgrind/models.py leetgrind/leetcode.py tests/test_leetcode.py tests/fixtures/
git commit -m "feat: LeetCode GraphQL client with pinned query and fixture"
```

---

### Task 4: Example extraction with unsupported-shape detection

**Files:**
- Create: `leetgrind/examples.py`
- Test: `tests/test_examples.py`

**Interfaces:**
- Consumes: `Problem` from Task 3.
- Produces:
  - `Example` frozen dataclass: `args: tuple[str, ...]` (raw Python literal source), `expected: str`.
  - `extract_examples(problem: Problem) -> tuple[Example, ...]` — returns `()` when the problem shape is unsupported or parsing fails. Never raises.

This is the module most likely to be wrong on real input, so it fails closed:
returning `()` makes the scaffolder emit a skipped placeholder test rather than a
confidently broken one.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_examples.py
from leetgrind.examples import extract_examples, Example
from leetgrind.models import Problem

def make(html, title="Two Sum", tags=("array",)):
    return Problem(id=1, slug="two-sum", title=title, difficulty="Easy",
                   tags=tags, is_paid_only=False, stub="class Solution: pass",
                   content_html=html)

STANDARD = """
<p><strong>Example 1:</strong></p>
<pre><strong>Input:</strong> nums = [2,7,11,15], target = 9
<strong>Output:</strong> [0,1]</pre>
<p><strong>Example 2:</strong></p>
<pre><strong>Input:</strong> nums = [3,2,4], target = 6
<strong>Output:</strong> [1,2]</pre>"""

def test_extracts_standard_examples():
    got = extract_examples(make(STANDARD))
    assert got == (Example(args=("[2,7,11,15]", "9"), expected="[0,1]"),
                   Example(args=("[3,2,4]", "6"), expected="[1,2]"))

def test_returns_empty_when_no_content():
    assert extract_examples(make(None)) == ()

def test_returns_empty_for_design_problems():
    html = """<pre><strong>Input:</strong>
["LRUCache","put","get"]
[[2],[1,1],[1]]
<strong>Output:</strong>
[null,null,1]</pre>"""
    assert extract_examples(make(html, title="LRU Cache", tags=("design",))) == ()

def test_returns_empty_for_in_place_problems():
    html = """<pre><strong>Input:</strong> nums = [1,1,2]
<strong>Output:</strong> 2, nums = [1,2,_]</pre>"""
    assert extract_examples(make(html, title="Remove Duplicates")) == ()

def test_returns_empty_when_any_answer_accepted():
    html = """<pre><strong>Input:</strong> nums = [1,2,3]
<strong>Output:</strong> [1,2,3]</pre>
<p><strong>Note:</strong> You may return the answer in <em>any order</em>.</p>"""
    assert extract_examples(make(html)) == ()

def test_returns_empty_on_unparseable_literals():
    html = """<pre><strong>Input:</strong> root = [1,null,2,3]
<strong>Output:</strong> &lt;some tree&gt;</pre>"""
    assert extract_examples(make(html)) == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_examples.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.examples'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/examples.py
import ast
import html as html_mod
import re
from dataclasses import dataclass

from .models import Problem

_PRE_RE = re.compile(r"<pre>(.*?)</pre>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_INPUT_RE = re.compile(r"Input:\s*(.*?)\s*Output:\s*(.*?)(?:\s*Explanation:|$)", re.DOTALL)
_ARG_RE = re.compile(r"[A-Za-z_]\w*\s*=\s*")

_UNSUPPORTED_TAGS = {"design"}
_ANY_ORDER_RE = re.compile(r"in any order|any valid|multiple valid", re.IGNORECASE)


@dataclass(frozen=True)
class Example:
    args: tuple[str, ...]
    expected: str


def _strip(fragment: str) -> str:
    return html_mod.unescape(_TAG_RE.sub("", fragment)).strip()


def _is_literal(src: str) -> bool:
    try:
        ast.literal_eval(src)
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return False
    return True


def _split_args(raw: str) -> tuple[str, ...] | None:
    """Split `nums = [1,2], target = 9` into ('[1,2]', '9')."""
    if not _ARG_RE.match(raw):
        return None
    parts = []
    bounds = [m.start() for m in _ARG_RE.finditer(raw)]
    for start, end in zip(bounds, bounds[1:] + [len(raw)]):
        value = raw[_ARG_RE.match(raw, start).end():end].strip().rstrip(",").strip()
        parts.append(value)
    return tuple(parts) if parts else None


def extract_examples(problem: Problem) -> tuple[Example, ...]:
    """Best-effort example extraction. Returns () whenever it is not confident."""
    html = problem.content_html
    if not html:
        return ()
    if _UNSUPPORTED_TAGS & set(problem.tags):
        return ()
    if _ANY_ORDER_RE.search(_strip(html)):
        return ()

    examples: list[Example] = []
    for block in _PRE_RE.findall(html):
        text = _strip(block)
        match = _INPUT_RE.search(text)
        if not match:
            return ()
        raw_args, raw_out = match.group(1).strip(), match.group(2).strip()
        # In-place problems report the mutated input in the output.
        if "=" in raw_out or "_" in raw_out:
            return ()
        args = _split_args(raw_args)
        if not args or not all(_is_literal(a) for a in args) or not _is_literal(raw_out):
            return ()
        examples.append(Example(args=args, expected=raw_out))
    return tuple(examples)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_examples.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add leetgrind/examples.py tests/test_examples.py
git commit -m "feat: example extraction that fails closed on unsupported shapes"
```

---

### Task 5: Template rendering

**Files:**
- Create: `leetgrind/scaffold.py`
- Test: `tests/test_scaffold.py`

**Interfaces:**
- Consumes: `Problem` (Task 3), `Example` (Task 4).
- Produces: `render_files(problem: Problem, examples: tuple[Example, ...]) -> dict[str, str]` mapping filename to contents. Keys are always exactly `solution.py`, `test_solution.py`, `README.md`. Pure — no I/O.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scaffold.py
from leetgrind.scaffold import render_files
from leetgrind.examples import Example
from leetgrind.models import Problem

P = Problem(id=1, slug="two-sum", title="Two Sum", difficulty="Easy",
            tags=("array", "hash-table"), is_paid_only=False,
            stub="class Solution:\n    def twoSum(self, nums, target):\n        ",
            content_html="<p>ignored</p>")

def test_renders_three_files():
    assert set(render_files(P, ())) == {"solution.py", "test_solution.py", "README.md"}

def test_solution_uses_the_official_stub():
    assert "def twoSum" in render_files(P, ())["solution.py"]

def test_readme_has_metadata_but_not_the_description():
    out = render_files(P, ())["README.md"]
    assert "# 1. Two Sum" in out
    assert "Easy" in out and "array" in out
    assert "https://leetcode.com/problems/two-sum/" in out
    assert "ignored" not in out

def test_tests_are_generated_from_examples():
    ex = (Example(args=("[2,7,11,15]", "9"), expected="[0,1]"),)
    out = render_files(P, ex)["test_solution.py"]
    assert "twoSum" in out
    assert "([2,7,11,15], 9)" in out
    assert "[0,1]" in out
    assert "skip" not in out

def test_missing_examples_produce_a_skipped_placeholder():
    out = render_files(P, ())["test_solution.py"]
    assert "pytest.skip" in out

def test_paid_only_falls_back_to_a_generic_stub():
    paid = Problem(id=2, slug="x", title="X", difficulty="Hard", tags=(),
                   is_paid_only=True, stub=None, content_html=None)
    assert "class Solution" in render_files(paid, ())["solution.py"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scaffold.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.scaffold'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/scaffold.py
import re

from .examples import Example
from .models import Problem

_GENERIC_STUB = "class Solution:\n    def solve(self):\n        ...\n"
_METHOD_RE = re.compile(r"def\s+(\w+)\s*\(")

_README = """# {id}. {title}

**Link:** {url}
**Difficulty:** {difficulty}
**Tags:** {tags}

**Approach:** _(fill in when solved)_
**Time:** O(?)  **Space:** O(?)
**Solved in:** _(pending)_
"""

_TEST_HEAD = """import pytest

from solution import Solution

"""

_SKIP_BODY = """

def test_examples():
    pytest.skip("no examples auto-extracted - add cases by hand")
"""

_CASE_BODY = """cases = [
{cases}]


@pytest.mark.parametrize("args,expected", cases)
def test_examples(args, expected):
    assert Solution().{method}(*args) == expected
"""


def _method_name(stub: str | None) -> str:
    if stub and (m := _METHOD_RE.search(stub)):
        return m.group(1)
    return "solve"


def url_for(slug: str) -> str:
    return f"https://leetcode.com/problems/{slug}/"


def render_files(problem: Problem, examples: tuple[Example, ...]) -> dict[str, str]:
    stub = problem.stub or _GENERIC_STUB
    if not stub.endswith("\n"):
        stub += "\n"

    readme = _README.format(
        id=problem.id, title=problem.title, url=url_for(problem.slug),
        difficulty=problem.difficulty, tags=", ".join(problem.tags) or "-")

    if examples:
        rows = "".join(
            f"    (({', '.join(e.args)}), {e.expected}),\n" for e in examples)
        tests = _TEST_HEAD + _CASE_BODY.format(
            cases=rows, method=_method_name(problem.stub))
    else:
        tests = _TEST_HEAD + _SKIP_BODY

    return {"solution.py": stub, "test_solution.py": tests, "README.md": readme}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scaffold.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add leetgrind/scaffold.py tests/test_scaffold.py
git commit -m "feat: render solution, test, and README from problem metadata"
```

---

### Task 6: Git operations

**Files:**
- Create: `leetgrind/repo.py`
- Test: `tests/test_repo.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `git(repo: Path, *args: str) -> str`, `init_repo(repo: Path) -> None`, `commit_paths(repo: Path, paths: list[Path], message: str) -> bool` (False when nothing staged), `push(repo: Path) -> bool` (False on failure, never raises), `undo_last(repo: Path) -> str`, `identity(repo: Path) -> tuple[str, str]`, `GitError(Exception)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_repo.py
import pytest
from leetgrind.repo import init_repo, commit_paths, git, undo_last, identity, GitError

@pytest.fixture
def repo(tmp_path):
    init_repo(tmp_path)
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.com")
    return tmp_path

def test_init_creates_repo_on_main(repo):
    assert (repo / ".git").is_dir()
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"

def test_init_writes_gitignore_and_gitattributes(repo):
    assert "__pycache__/" in (repo / ".gitignore").read_text()
    assert ".lc/" in (repo / ".gitignore").read_text()
    assert "text=auto" in (repo / ".gitattributes").read_text()

def test_commit_paths_creates_a_commit(repo):
    (repo / "a.txt").write_text("hello")
    assert commit_paths(repo, [repo / "a.txt"], "feat: a") is True
    assert git(repo, "log", "-1", "--pretty=%s") == "feat: a"

def test_commit_paths_returns_false_when_nothing_changed(repo):
    (repo / "a.txt").write_text("hello")
    commit_paths(repo, [repo / "a.txt"], "feat: a")
    assert commit_paths(repo, [repo / "a.txt"], "feat: again") is False

def test_undo_last_removes_the_commit_but_keeps_files(repo):
    (repo / "a.txt").write_text("hello")
    commit_paths(repo, [repo / "a.txt"], "feat: a")
    (repo / "b.txt").write_text("world")
    commit_paths(repo, [repo / "b.txt"], "feat: b")
    undo_last(repo)
    assert git(repo, "log", "-1", "--pretty=%s") == "feat: a"
    assert (repo / "b.txt").exists()

def test_identity_reads_config(repo):
    assert identity(repo) == ("Test", "test@example.com")

def test_git_raises_on_failure(repo):
    with pytest.raises(GitError):
        git(repo, "checkout", "no-such-branch")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_repo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.repo'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/repo.py
import subprocess
from pathlib import Path

GITIGNORE = "__pycache__/\n.pytest_cache/\n.lc/\n*.pyc\n"
GITATTRIBUTES = "* text=auto eol=lf\n"


class GitError(Exception):
    """A git invocation failed."""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").is_dir():
        git(repo, "init", "-q")
        git(repo, "branch", "-M", "main")
    (repo / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (repo / ".gitattributes").write_text(GITATTRIBUTES, encoding="utf-8")


def identity(repo: Path) -> tuple[str, str]:
    try:
        return git(repo, "config", "user.name"), git(repo, "config", "user.email")
    except GitError:
        return "", ""


def commit_paths(repo: Path, paths: list[Path], message: str) -> bool:
    for path in paths:
        git(repo, "add", "--", str(path))
    if not git(repo, "diff", "--cached", "--name-only"):
        return False
    git(repo, "commit", "-q", "-m", message)
    return True


def push(repo: Path) -> bool:
    """Push if a remote exists. Never raises - a failed push must not lose work."""
    try:
        if not git(repo, "remote"):
            return False
        git(repo, "push", "-q", "-u", "origin", "main")
        return True
    except GitError:
        return False


def undo_last(repo: Path) -> str:
    subject = git(repo, "log", "-1", "--pretty=%s")
    git(repo, "reset", "--soft", "HEAD~1")
    return subject
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_repo.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add leetgrind/repo.py tests/test_repo.py
git commit -m "feat: git operations with non-raising push and undo"
```

---

### Task 7: Active-problem state and response cache

**Files:**
- Create: `leetgrind/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ActiveProblem` dataclass (`id`, `slug`, `title`, `difficulty`, `folder`, `started_at: str`, `schema: int = 1`), `load_active(repo: Path) -> ActiveProblem | None`, `save_active(repo, active) -> None`, `clear_active(repo) -> None`, `elapsed_minutes(active) -> int`, `cache_get(repo, slug) -> dict | None`, `cache_put(repo, slug, payload) -> None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state.py
from datetime import datetime, timedelta, timezone
from leetgrind.state import (ActiveProblem, load_active, save_active, clear_active,
                             elapsed_minutes, cache_get, cache_put)

def make(**kw):
    base = dict(id=42, slug="trapping-rain-water", title="Trapping Rain Water",
                difficulty="Hard", folder="0042-trapping-rain-water",
                started_at=datetime.now(timezone.utc).isoformat())
    return ActiveProblem(**{**base, **kw})

def test_roundtrip(tmp_path):
    a = make()
    save_active(tmp_path, a)
    assert load_active(tmp_path) == a

def test_load_returns_none_when_absent(tmp_path):
    assert load_active(tmp_path) is None

def test_clear_removes_state(tmp_path):
    save_active(tmp_path, make())
    clear_active(tmp_path)
    assert load_active(tmp_path) is None

def test_unknown_schema_version_is_ignored_not_crashed(tmp_path):
    save_active(tmp_path, make())
    path = tmp_path / ".lc" / "state.json"
    path.write_text(path.read_text().replace('"schema": 1', '"schema": 99'))
    assert load_active(tmp_path) is None

def test_elapsed_minutes(tmp_path):
    started = (datetime.now(timezone.utc) - timedelta(minutes=12)).isoformat()
    assert elapsed_minutes(make(started_at=started)) == 12

def test_cache_roundtrip(tmp_path):
    assert cache_get(tmp_path, "two-sum") is None
    cache_put(tmp_path, "two-sum", {"a": 1})
    assert cache_get(tmp_path, "two-sum") == {"a": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.state'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/state.py
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1


@dataclass
class ActiveProblem:
    id: int
    slug: str
    title: str
    difficulty: str
    folder: str
    started_at: str
    schema: int = SCHEMA


def _dir(repo: Path) -> Path:
    path = repo / ".lc"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_file(repo: Path) -> Path:
    return _dir(repo) / "state.json"


def load_active(repo: Path) -> ActiveProblem | None:
    path = _state_file(repo)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA:
            return None
        return ActiveProblem(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def save_active(repo: Path, active: ActiveProblem) -> None:
    _state_file(repo).write_text(json.dumps(asdict(active), indent=2), encoding="utf-8")


def clear_active(repo: Path) -> None:
    _state_file(repo).unlink(missing_ok=True)


def elapsed_minutes(active: ActiveProblem) -> int:
    started = datetime.fromisoformat(active.started_at)
    delta = datetime.now(timezone.utc) - started
    return max(0, int(delta.total_seconds() // 60))


def cache_get(repo: Path, slug: str) -> dict | None:
    path = _dir(repo) / "cache" / f"{slug}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def cache_put(repo: Path, slug: str, payload: dict) -> None:
    path = _dir(repo) / "cache" / f"{slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add leetgrind/state.py tests/test_state.py
git commit -m "feat: versioned active-problem state and response cache"
```

---

### Task 8: Stats, streak, and README generation

**Files:**
- Create: `leetgrind/stats.py`
- Test: `tests/test_stats.py`

**Interfaces:**
- Consumes: `git` from Task 6.
- Produces: `SolvedEntry` dataclass (`id`, `slug`, `title`, `difficulty`, `status`), `scan_solutions(repo: Path) -> list[SolvedEntry]`, `streak_days(commit_dates: list[date]) -> int`, `render_root_readme(entries: list[SolvedEntry]) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stats.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stats.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.stats'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/stats.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_stats.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add leetgrind/stats.py tests/test_stats.py
git commit -m "feat: solution scanning, streak math, and root README generation"
```

---

### Task 9: VS Code integration

**Files:**
- Create: `leetgrind/editor.py`
- Test: `tests/test_editor.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `code_available() -> bool`, `open_problem(folder: Path) -> bool`, `close_window(folder_name: str) -> bool`. All are best-effort and never raise.

`close_window` matches the VS Code window title and calls `CloseMainWindow()`,
which closes gracefully so unsaved work still prompts. It is the single fragile
behaviour in the system and is therefore isolated here and always non-fatal.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_editor.py
import subprocess
from pathlib import Path
from leetgrind import editor

def test_open_problem_invokes_code_with_new_window(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(editor, "code_available", lambda: True)
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0))
    assert editor.open_problem(tmp_path) is True
    assert ["-n", str(tmp_path)] == calls[0][1:]
    assert "-g" in calls[1]
    assert calls[1][-1].endswith("solution.py")

def test_open_problem_is_a_no_op_without_code(monkeypatch, tmp_path):
    monkeypatch.setattr(editor, "code_available", lambda: False)
    assert editor.open_problem(tmp_path) is False

def test_open_problem_never_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(editor, "code_available", lambda: True)
    def boom(*a, **k): raise OSError("nope")
    monkeypatch.setattr(subprocess, "run", boom)
    assert editor.open_problem(tmp_path) is False

def test_close_window_never_raises(monkeypatch):
    def boom(*a, **k): raise OSError("nope")
    monkeypatch.setattr(subprocess, "run", boom)
    assert editor.close_window("0042-trapping-rain-water") is False

def test_close_window_passes_the_folder_name_to_powershell(monkeypatch):
    seen = {}
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: seen.update(cmd=cmd) or subprocess.CompletedProcess(cmd, 0))
    editor.close_window("0042-trapping-rain-water")
    assert "0042-trapping-rain-water" in " ".join(seen["cmd"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_editor.py -v`
Expected: FAIL with `ImportError: cannot import name 'editor'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/editor.py
import shutil
import subprocess
from pathlib import Path

_CLOSE_PS = (
    "Get-Process code -ErrorAction SilentlyContinue | "
    "Where-Object {{ $_.MainWindowTitle -like '*{name}*' }} | "
    "ForEach-Object {{ $_.CloseMainWindow() }} | Out-Null"
)


def code_available() -> bool:
    return shutil.which("code") is not None


def open_problem(folder: Path) -> bool:
    """Open a new VS Code window on `folder` with solution.py focused."""
    if not code_available():
        return False
    try:
        subprocess.run(["code", "-n", str(folder)], check=False)
        subprocess.run(["code", "-g", str(folder / "solution.py")], check=False)
        return True
    except OSError:
        return False


def close_window(folder_name: str) -> bool:
    """Best-effort graceful close of the VS Code window for `folder_name`."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             _CLOSE_PS.format(name=folder_name)],
            check=False, capture_output=True)
        return result.returncode == 0
    except OSError:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_editor.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add leetgrind/editor.py tests/test_editor.py
git commit -m "feat: best-effort VS Code open and window close"
```

---

### Task 10: Test runner

**Files:**
- Create: `leetgrind/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `TestOutcome` dataclass (`passed: bool`, `summary: str`, `output: str`, `skipped: bool`), `run_tests(folder: Path) -> TestOutcome`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runner.py
from leetgrind.runner import run_tests

def scaffold(folder, solution, test):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "solution.py").write_text(solution, encoding="utf-8")
    (folder / "test_solution.py").write_text(test, encoding="utf-8")

PASSING = """import pytest
from solution import Solution
def test_ok():
    assert Solution().twoSum([2,7], 9) == [0,1]
"""

def test_passing_suite_reports_passed(tmp_path):
    scaffold(tmp_path / "p", "class Solution:\n    def twoSum(self, n, t): return [0,1]\n", PASSING)
    outcome = run_tests(tmp_path / "p")
    assert outcome.passed is True
    assert outcome.skipped is False

def test_failing_suite_reports_output(tmp_path):
    scaffold(tmp_path / "p", "class Solution:\n    def twoSum(self, n, t): return [9,9]\n", PASSING)
    outcome = run_tests(tmp_path / "p")
    assert outcome.passed is False
    assert "assert" in outcome.output

def test_skipped_suite_is_marked_skipped(tmp_path):
    scaffold(tmp_path / "p", "class Solution: pass\n",
             "import pytest\ndef test_x():\n    pytest.skip('none')\n")
    outcome = run_tests(tmp_path / "p")
    assert outcome.passed is True
    assert outcome.skipped is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.runner'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/runner.py
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_SUMMARY_RE = re.compile(r"^=+ (.*(?:passed|failed|error|skipped).*) =+$", re.MULTILINE)


@dataclass
class TestOutcome:
    passed: bool
    summary: str
    output: str
    skipped: bool


def run_tests(folder: Path) -> TestOutcome:
    """Run the problem's tests with its own folder importable as the rootdir."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "test_solution.py", "-q",
         "-p", "no:cacheprovider", "--no-header"],
        cwd=folder, capture_output=True, text=True)
    output = result.stdout + result.stderr
    match = _SUMMARY_RE.search(output)
    summary = match.group(1).strip() if match else output.strip().splitlines()[-1:] or [""]
    if isinstance(summary, list):
        summary = summary[0]
    return TestOutcome(
        passed=result.returncode == 0,
        summary=summary,
        output=output,
        skipped="skipped" in output and "passed" not in output and "failed" not in output,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_runner.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add leetgrind/runner.py tests/test_runner.py
git commit -m "feat: per-problem pytest runner with parsed summary"
```

---

### Task 11: Core workflow — start, solve, park

**Files:**
- Create: `leetgrind/workflow.py`
- Test: `tests/test_workflow.py`

**Interfaces:**
- Consumes: everything from Tasks 2-10.
- Produces:
  - `start_problem(cfg: Config, text: str) -> ActiveProblem` — scaffolds, commits `Start`, opens VS Code.
  - `finish_problem(cfg, approach: str, time_c: str, space_c: str) -> str` — patches README, regenerates root README, commits `Solve`, pushes, closes window, clears state. Returns commit subject.
  - `park_problem(cfg) -> str` — commits `Park`, closes window, clears state.
  - `fallback_problem(slug: str, number: int) -> Problem` — used when LeetCode is unreachable.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workflow.py
import pytest
from pathlib import Path
from leetgrind import workflow, leetcode, editor
from leetgrind.config import Config
from leetgrind.models import Problem
from leetgrind.repo import init_repo, git
from leetgrind.state import load_active

P = Problem(id=1, slug="two-sum", title="Two Sum", difficulty="Easy",
            tags=("array",), is_paid_only=False,
            stub="class Solution:\n    def twoSum(self, nums, target):\n        return [0,1]\n",
            content_html=None)

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_workflow.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.workflow'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/workflow.py
import re
from datetime import datetime, timezone
from pathlib import Path

from . import editor
from .config import Config
from .examples import extract_examples
from .leetcode import fetch_problem
from .models import Problem
from .repo import commit_paths, push
from .scaffold import render_files
from .state import (ActiveProblem, clear_active, elapsed_minutes, load_active,
                    save_active)
from .stats import render_root_readme, scan_solutions
from .urls import parse_slug


class ProblemActive(Exception):
    """A problem is already in progress; park or resume it first."""


class NoActiveProblem(Exception):
    """Nothing is in progress."""


def fallback_problem(slug: str, number: int) -> Problem:
    title = " ".join(word.capitalize() for word in slug.split("-"))
    return Problem(id=number, slug=slug, title=title, difficulty="?",
                   tags=(), is_paid_only=False, stub=None, content_html=None)


def start_problem(cfg: Config, text: str, *, number: int | None = None) -> ActiveProblem:
    if load_active(cfg.repo_path) is not None:
        raise ProblemActive("park or resume the active problem first")

    slug = parse_slug(text)
    try:
        problem = fetch_problem(slug)
    except Exception:
        if number is None:
            raise
        problem = fallback_problem(slug, number)

    folder = cfg.repo_path / problem.folder_name
    folder.mkdir(parents=True, exist_ok=True)
    for name, body in render_files(problem, extract_examples(problem)).items():
        target = folder / name
        if not target.exists():
            target.write_text(body, encoding="utf-8")

    commit_paths(cfg.repo_path, [folder],
                 f"Start {problem.id}: {problem.title} ({problem.difficulty})")
    if cfg.auto_push:
        push(cfg.repo_path)

    active = ActiveProblem(id=problem.id, slug=problem.slug, title=problem.title,
                           difficulty=problem.difficulty, folder=problem.folder_name,
                           started_at=datetime.now(timezone.utc).isoformat())
    save_active(cfg.repo_path, active)
    editor.open_problem(folder)
    return active


def _patch_readme(path: Path, approach: str, time_c: str, space_c: str, minutes: int) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\*\*Approach:\*\*.*", f"**Approach:** {approach}", text, count=1)
    text = re.sub(r"\*\*Time:\*\*.*", f"**Time:** {time_c}  **Space:** {space_c}", text, count=1)
    text = re.sub(r"\*\*Solved in:\*\*.*", f"**Solved in:** {minutes}m", text, count=1)
    path.write_text(text, encoding="utf-8")


def _finalise(cfg: Config, active: ActiveProblem, subject: str) -> str:
    root_readme = cfg.repo_path / "README.md"
    root_readme.write_text(render_root_readme(scan_solutions(cfg.repo_path)), encoding="utf-8")
    commit_paths(cfg.repo_path, [cfg.repo_path / active.folder, root_readme], subject)
    if cfg.auto_push:
        push(cfg.repo_path)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_workflow.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add leetgrind/workflow.py tests/test_workflow.py
git commit -m "feat: start, solve, and park workflow"
```

---

### Task 12: Doctor — environment and contribution-graph checks

**Files:**
- Create: `leetgrind/doctor.py`
- Test: `tests/test_doctor.py`

**Interfaces:**
- Consumes: `Config` (Task 1), `identity` (Task 6), `code_available` (Task 9).
- Produces: `Check` dataclass (`name: str`, `ok: bool`, `detail: str`, `fix: str`), `run_checks(cfg: Config | None) -> list[Check]`, `github_emails() -> list[str] | None`.

This task implements the spec's central correctness promise: commits only count
toward the contribution graph when `user.email` is verified on the GitHub account.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doctor.py
from pathlib import Path
from leetgrind import doctor
from leetgrind.config import Config
from leetgrind.repo import init_repo, git

def by_name(checks, name):
    return next(c for c in checks if c.name == name)

def make_repo(tmp_path, email):
    init_repo(tmp_path)
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", email)
    return Config(repo_path=tmp_path)

def test_flags_email_not_on_the_github_account(tmp_path, monkeypatch):
    cfg = make_repo(tmp_path, "wrong@example.com")
    monkeypatch.setattr(doctor, "github_emails", lambda: ["real@example.com"])
    monkeypatch.setattr(doctor, "code_available", lambda: True)
    check = by_name(doctor.run_checks(cfg), "commit email counts on GitHub")
    assert check.ok is False
    assert "wrong@example.com" in check.detail

def test_passes_when_email_is_on_the_account(tmp_path, monkeypatch):
    cfg = make_repo(tmp_path, "real@example.com")
    monkeypatch.setattr(doctor, "github_emails", lambda: ["real@example.com"])
    monkeypatch.setattr(doctor, "code_available", lambda: True)
    assert by_name(doctor.run_checks(cfg), "commit email counts on GitHub").ok is True

def test_reports_when_the_scope_is_missing(tmp_path, monkeypatch):
    cfg = make_repo(tmp_path, "real@example.com")
    monkeypatch.setattr(doctor, "github_emails", lambda: None)
    monkeypatch.setattr(doctor, "code_available", lambda: True)
    check = by_name(doctor.run_checks(cfg), "commit email counts on GitHub")
    assert check.ok is False
    assert "gh auth refresh" in check.fix

def test_flags_missing_git_identity(tmp_path, monkeypatch):
    init_repo(tmp_path)
    monkeypatch.setattr(doctor, "github_emails", lambda: [])
    monkeypatch.setattr(doctor, "code_available", lambda: True)
    assert by_name(doctor.run_checks(Config(repo_path=tmp_path)), "git identity set").ok is False

def test_flags_missing_vscode(tmp_path, monkeypatch):
    cfg = make_repo(tmp_path, "real@example.com")
    monkeypatch.setattr(doctor, "github_emails", lambda: ["real@example.com"])
    monkeypatch.setattr(doctor, "code_available", lambda: False)
    assert by_name(doctor.run_checks(cfg), "VS Code on PATH").ok is False

def test_handles_no_config_at_all(monkeypatch):
    monkeypatch.setattr(doctor, "github_emails", lambda: [])
    monkeypatch.setattr(doctor, "code_available", lambda: False)
    assert by_name(doctor.run_checks(None), "configured").ok is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_doctor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.doctor'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/doctor.py
import json
import subprocess
from dataclasses import dataclass

from .config import Config
from .editor import code_available
from .repo import identity

REFRESH = "gh auth refresh -h github.com -s user"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def github_emails() -> list[str] | None:
    """Verified emails on the authenticated GitHub account, or None if unknowable."""
    try:
        result = subprocess.run(["gh", "api", "user/emails"],
                                capture_output=True, text=True)
        if result.returncode != 0:
            return None
        return [e["email"] for e in json.loads(result.stdout) if e.get("verified")]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


def run_checks(cfg: Config | None) -> list[Check]:
    checks = [Check("configured", cfg is not None,
                    "config found" if cfg else "no config yet",
                    "" if cfg else "run the first-run wizard")]

    name, email = identity(cfg.repo_path) if cfg else ("", "")
    checks.append(Check("git identity set", bool(name and email),
                        f"{name} <{email}>" if email else "user.name/user.email unset",
                        'git config --global user.email "you@example.com"'))

    emails = github_emails()
    if emails is None:
        checks.append(Check("commit email counts on GitHub", False,
                            "cannot read GitHub emails (missing 'user' scope)", REFRESH))
    elif email and email in emails:
        checks.append(Check("commit email counts on GitHub", True,
                            f"{email} is verified on your account"))
    else:
        checks.append(Check(
            "commit email counts on GitHub", False,
            f"{email or '(unset)'} is NOT a verified email on your GitHub account - "
            "commits will not appear on your contribution graph",
            f'git config --global user.email "{emails[0]}"' if emails else REFRESH))

    checks.append(Check("VS Code on PATH", code_available(),
                        "found" if code_available() else "`code` not found",
                        "VS Code > Command Palette > Shell Command: Install 'code' command"))
    return checks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_doctor.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add leetgrind/doctor.py tests/test_doctor.py
git commit -m "feat: doctor checks including contribution-graph email verification"
```

---

### Task 13: CLI commands

**Files:**
- Create: `leetgrind/cli.py`
- Create: `leetgrind/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_config` (Task 1), `fetch_daily` (Task 3), `undo_last` (Task 6), `load_active` (Task 7), `run_tests` (Task 10), `start_problem`/`finish_problem`/`park_problem` (Task 11), `run_checks`/`Check` (Task 12).
- Produces: Typer `app` exposing `new`, `done`, `park`, `daily`, `undo`, `doctor`. `lc` with no subcommand launches the menu (Task 14).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
import pytest
from typer.testing import CliRunner
from leetgrind import cli, workflow, doctor
from leetgrind.config import Config
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.cli'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/cli.py
import typer
from rich.console import Console

from . import doctor as doctor_mod
from . import workflow
from .config import load_config
from .leetcode import fetch_daily
from .repo import undo_last
from .runner import run_tests
from .state import load_active

app = typer.Typer(add_completion=False, help="LeetCode solve loop automation.")
console = Console()


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
    console.print(f"[green]Started[/] {active.id}: {active.title} ({active.difficulty})")


@app.command()
def done(approach: str = typer.Option(..., prompt=True),
         time: str = typer.Option(..., prompt="Time complexity"),
         space: str = typer.Option(..., prompt="Space complexity"),
         force: bool = typer.Option(False, help="Commit even if tests fail")):
    """Test, commit, push, and close the window."""
    cfg = _require_config()
    active = load_active(cfg.repo_path)
    if active is None:
        console.print("[red]Nothing in progress.[/]")
        raise typer.Exit(1)

    if cfg.gate_on_tests and not force:
        outcome = run_tests(cfg.repo_path / active.folder)
        if not outcome.passed:
            console.print(f"[red]{outcome.summary}[/]\n{outcome.output}")
            console.print("[dim]re-run with --force to commit anyway, "
                          "or `lc park` to shelve it[/]")
            raise typer.Exit(1)

    subject = workflow.finish_problem(cfg, approach, time, space)
    console.print(f"[green]Committed[/] {subject}")


@app.command()
def park():
    """Record the current attempt as unsolved and move on."""
    cfg = _require_config()
    try:
        console.print(f"[yellow]Parked[/] {workflow.park_problem(cfg)}")
    except workflow.NoActiveProblem as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)


@app.command()
def daily():
    """Start today's LeetCode daily challenge."""
    new(fetch_daily(), number=None)


@app.command()
def undo():
    """Soft-reset the most recent commit."""
    console.print(f"[yellow]Undid[/] {undo_last(_require_config().repo_path)}")


@app.command()
def doctor():
    """Diagnose environment and contribution-graph problems."""
    checks = doctor_mod.run_checks(load_config())
    for check in checks:
        mark = "[green]OK  [/]" if check.ok else "[red]FAIL[/]"
        console.print(f"{mark} {check.name} — {check.detail}")
        if not check.ok and check.fix:
            console.print(f"     [dim]fix:[/] {check.fix}")
    raise typer.Exit(0 if all(c.ok for c in checks) else 1)
```

```python
# leetgrind/__main__.py
from .menu import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add leetgrind/cli.py leetgrind/__main__.py tests/test_cli.py
git commit -m "feat: CLI commands for new, done, park, daily, undo, doctor"
```

---

### Task 14: Menu, first-run wizard, and packaging

**Files:**
- Create: `leetgrind/menu.py`
- Create: `leetgrind/wizard.py`
- Create: `build/make_shortcut.ps1`
- Test: `tests/test_wizard.py`
- Test: `tests/test_integration.py`

**Interfaces:**
- Consumes: everything.
- Produces: `menu.main() -> None`, `wizard.first_run(answers: dict) -> Config`.

`wizard.first_run` takes already-collected answers so it is testable without a
TTY; `menu.py` owns the questionary prompts that gather them.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wizard.py
from pathlib import Path
from leetgrind import wizard
from leetgrind.config import load_config

def test_first_run_creates_repo_and_config(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    repo = tmp_path / "solutions"
    cfg = wizard.first_run({"repo_path": repo, "auto_push": False})
    assert (repo / ".git").is_dir()
    assert (repo / ".gitignore").exists()
    assert (repo / ".gitattributes").exists()
    assert cfg.repo_path == repo
    assert load_config() == cfg

def test_first_run_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    repo = tmp_path / "solutions"
    wizard.first_run({"repo_path": repo, "auto_push": False})
    (repo / "0001-two-sum").mkdir()
    cfg = wizard.first_run({"repo_path": repo, "auto_push": False})
    assert (repo / "0001-two-sum").exists()
    assert cfg.repo_path == repo
```

```python
# tests/test_integration.py
import pytest
from leetgrind import workflow, editor, wizard
from leetgrind.models import Problem
from leetgrind.repo import git

P = Problem(id=1, slug="two-sum", title="Two Sum", difficulty="Easy",
            tags=("array",), is_paid_only=False,
            stub="class Solution:\n    def twoSum(self, nums, target):\n        return [0,1]\n",
            content_html="""<pre><strong>Input:</strong> nums = [2,7,11,15], target = 9
<strong>Output:</strong> [0,1]</pre>""")

def test_full_loop_produces_exactly_two_commits(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(workflow, "fetch_problem", lambda slug, **kw: P)
    monkeypatch.setattr(editor, "open_problem", lambda folder: True)
    monkeypatch.setattr(editor, "close_window", lambda name: True)

    cfg = wizard.first_run({"repo_path": tmp_path / "solutions", "auto_push": False})
    git(cfg.repo_path, "config", "user.name", "Test")
    git(cfg.repo_path, "config", "user.email", "test@example.com")

    workflow.start_problem(cfg, "https://leetcode.com/problems/two-sum/")
    workflow.finish_problem(cfg, "hash map", "O(n)", "O(n)")

    subjects = git(cfg.repo_path, "log", "--pretty=%s").splitlines()
    assert subjects[0] == "Solve 1: Two Sum (hash map, O(n))"
    assert subjects[1] == "Start 1: Two Sum (Easy)"
    assert git(cfg.repo_path, "status", "--porcelain") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_wizard.py tests/test_integration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'leetgrind.wizard'`

- [ ] **Step 3: Write minimal implementation**

```python
# leetgrind/wizard.py
from pathlib import Path

from .config import Config, save_config
from .repo import init_repo


def first_run(answers: dict) -> Config:
    """Create the solutions repo and persist config. Safe to re-run."""
    repo = Path(answers["repo_path"])
    init_repo(repo)
    cfg = Config(repo_path=repo,
                 auto_push=answers.get("auto_push", True),
                 auto_close=answers.get("auto_close", True),
                 gate_on_tests=answers.get("gate_on_tests", True))
    save_config(cfg)
    return cfg
```

```python
# leetgrind/menu.py
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
    repo = questionary.path("Where should solutions live?",
                            default=str(Path.home() / "Documents" / "leetcode-solutions")).ask()
    return first_run({"repo_path": repo,
                      "auto_push": questionary.confirm("Push after every commit?").ask()})


def _solve_loop(cfg, active) -> None:
    while True:
        choice = questionary.select(
            f"Solving {active.id}: {active.title}",
            choices=["Done — test and commit", "Park — give up for now"]).ask()
        if choice is None or choice.startswith("Park"):
            console.print(f"[yellow]{workflow.park_problem(cfg)}[/]")
            return
        outcome = run_tests(cfg.repo_path / active.folder)
        if not outcome.passed and cfg.gate_on_tests:
            console.print(f"[red]{outcome.summary}[/]\n{outcome.output}")
            if not questionary.confirm("Commit anyway?", default=False).ask():
                continue
        approach = questionary.text("Approach:").ask() or "n/a"
        time_c = questionary.text("Time complexity:", default="O(n)").ask()
        space_c = questionary.text("Space complexity:", default="O(1)").ask()
        console.print(f"[green]{workflow.finish_problem(cfg, approach, time_c, space_c)}[/]")
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
```

```powershell
# build/make_shortcut.ps1
$ErrorActionPreference = "Stop"
$target  = (Get-Command lc).Source
$desktop = [Environment]::GetFolderPath("Desktop")
$link    = Join-Path $desktop "LeetGrind.lnk"

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($link)
$sc.TargetPath       = $target
$sc.WorkingDirectory = $env:USERPROFILE
$sc.Description      = "LeetGrind - LeetCode solve loop"
$sc.Save()

Write-Host "Created $link - right-click it and Pin to taskbar."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -v`
Expected: all tests pass, including `test_full_loop_produces_exactly_two_commits`

- [ ] **Step 5: Commit**

```bash
git add leetgrind/menu.py leetgrind/wizard.py build/ tests/test_wizard.py tests/test_integration.py
git commit -m "feat: menu, first-run wizard, and pinnable shortcut"
```

---

## Self-Review

**Spec coverage.** Menu → Task 14. Commands table → Task 13 (`next` deferred with
`lists.py`, see gaps). Module map → Tasks 1-14. Two repos → Task 14. `lc new` /
`lc done` / `lc park` flows → Task 11. Generated files and the no-description rule
→ Task 5. Contribution-graph correctness → Task 12. Error-handling table → Tasks
3, 4, 6, 9, 11. Configuration → Task 1. Repo hygiene → Task 6. Packaging → Task
14. Testing strategy → every task, plus the integration test in Task 14.

**Known gaps, deliberately deferred.** `lists.py` (Blind 75 / NeetCode 150,
menu item 3) and clipboard auto-detection are specified but not planned as tasks.
Both are additive: they feed a slug into the existing `start_problem` entry point
and change nothing structural. They are follow-up work after the loop is proven
end to end.

**Type consistency.** `Problem.folder_name` (Task 3) is consumed by Tasks 11 and
14. `Example.args`/`.expected` (Task 4) are consumed by Task 5. `ActiveProblem`
(Task 7) is consumed by Tasks 11, 13, 14. `Check` (Task 12) is consumed by Tasks
13 and 14. `TestOutcome` (Task 10) is consumed by Task 14. Names verified
identical across definition and use.
