# LeetGrind — Design

**Date:** 2026-08-17
**Status:** Approved

## Purpose

Remove every step between "I want to solve a LeetCode problem" and "I am typing
the solution", and make each solve produce real commits in a public repo.

Today the loop is: make a folder, name it consistently, create the files, look up
the signature, open the editor, solve, write a commit message, commit, push,
update the README table. LeetGrind reduces that to: paste a link, solve, press
Enter.

## Success criteria

1. From paste to typing in `solution.py` takes one action and under three seconds.
2. Every solved problem produces at least two commits that count on the user's
   GitHub contribution graph.
3. The loop never strands the user. Every failure degrades to a working path.
4. The resulting repo reads well to a human browsing it.

## Product shape

A Python CLI distributed as a double-clickable shortcut. The default entry point
is a menu (TUI); the individual commands remain available in a terminal.

```
  ╔══════════════════════════════════════════╗
  ║           L E E T G R I N D              ║
  ║   13 solved · 🔥 5 day streak · 4 today  ║
  ╚══════════════════════════════════════════╝

   ▸ 1  Start coding          paste a link
     2  Today's daily         no pasting
     3  Next from a list      Blind 75 / NeetCode 150
     4  Resume                #42 Trapping Rain Water, 12m
     5  Stats
     6  Settings
     7  Doctor
     8  Quit
```

### Commands

| Command | Effect |
|---|---|
| `lc` | Open the menu (what the shortcut runs) |
| `lc new <url\|slug>` | Scaffold, commit "Start", open VS Code |
| `lc done` | Test, prompt, commit "Solve", push, close window |
| `lc park` | Commit the attempt as unsolved, clear state |
| `lc daily` | `lc new` against today's daily challenge |
| `lc next` | `lc new` against the next unsolved item in the active list |
| `lc undo` | Soft-reset the last commit |
| `lc doctor` | Diagnose environment and config |
| `lc config` | Read/write settings |

## Architecture

Ten modules, each with one responsibility. Target: no file over ~150 lines.

```
leetgrind/
  __main__.py    entry point; launches menu
  menu.py        TUI: menu, prompts, streak header, retry/force/park keys
  cli.py         command definitions; thin wrappers over the core modules
  leetcode.py    URL→slug · GraphQL · daily challenge · example extraction
  scaffold.py    render templates → solution.py / test_solution.py / README.md
  repo.py        git: init, remote, identity, add, commit, push, undo
  editor.py      VS Code open + best-effort close   [platform-specific]
  state.py       config (%APPDATA%) + active problem (.lc/state.json) + cache
  stats.py       folder scan → solved count, streak, tag index, README table
  lists.py       Blind 75 / NeetCode 150 definitions and progress
  templates/     the three generated files
build/
  make_shortcut.ps1   creates the pinnable .lnk with icon
```

`editor.py` is isolated deliberately: window-closing is the one inherently
fragile behaviour in the system, and quarantining it means it cannot take
anything else down.

### Boundaries

- `leetcode.py` performs network I/O and returns plain dataclasses. It never
  touches the filesystem or git.
- `scaffold.py` is pure: dataclass in, rendered file contents out. No I/O.
- `repo.py` shells out to `git`. It never knows what a LeetCode problem is.
- `menu.py` and `cli.py` are the only modules that print to the user.

## Two repositories

LeetGrind (this tool) and the solutions repo are separate:

- **Tool repo** — `leetgrind/`, the code in this spec.
- **Solutions repo** — created by the first-run wizard at a path the user picks,
  default `~/Documents/leetcode-solutions`. Public. This is what receives the
  commits.

## Data flow

### `lc new <url>`

1. Parse slug. Accepts a full URL, a URL with query parameters
   (`?envType=daily-question`), or a bare slug.
2. Check cache (`.lc/cache/<slug>.json`). On miss, POST to `leetcode.com/graphql`
   for `questionFrontendId`, `title`, `difficulty`, `topicTags`, `isPaidOnly`,
   `content`, `codeSnippets`. Cache the response.
3. Create `{questionFrontendId:04d}-{slug}/` and render three files.
4. `git add` the folder; commit `Start {id}: {title} ({difficulty})`.
5. Write `.lc/state.json`: slug, id, title, folder, `started_at`.
6. `code -n <folder>` then `code -g <folder>/solution.py` to focus the cursor.

Use `questionFrontendId`, never `questionId` — the latter is an internal
identifier that does not match the number shown on the site.

### `lc done`

1. Read `.lc/state.json`.
2. Run `pytest` scoped to that folder.
3. On failure: print expected vs actual per case, then offer
   `⏎` retry · `f` force-commit · `p` park. (There is no separate "skip" —
   park is the single, unambiguous way to leave a problem unfinished.)
4. On pass: prompt for approach, time complexity, space complexity.
5. Patch the problem README with those values and the elapsed solve time.
6. Regenerate the root README table and tag index from a folder scan, so they
   can never drift from reality.
7. Commit `Solve {id}: {title} ({approach}, {time})`; push if `auto_push`.
8. Best-effort close the VS Code window; clear state.

### `lc park`

Commits the attempt as `Park {id}: {title} (unsolved)`, closes the window, clears
state. Preserves the work and keeps the loop clean. Parked problems are marked in
the root README table so they can be revisited.

## Generated files

```
0042-trapping-rain-water/
  solution.py        official Python stub, correct signature
  test_solution.py   extracted Example cases
  README.md          number, title, difficulty, tags, link, approach, complexity, time
```

**The problem description is not reproduced.** The README stores the link, the
metadata, and the user's own one-line summary. LeetCode's problem statements are
copyrighted and their terms prohibit redistribution; reproducing them in a public
repo carries takedown risk for no benefit. Extracted examples in the test file are
test inputs, not prose, and are retained.

## Contribution-graph correctness

The tool's central promise is commits that count. Two things break this, and both
are checked at first run and by `lc doctor`:

1. **Commit email.** Commits only count if `git config user.email` is an email
   registered and verified on the user's GitHub account. A mismatch produces a
   full commit history and an empty contribution graph. `lc doctor` compares the
   configured email against `gh api user/emails` and fails loudly on mismatch.
   Requires the `user` OAuth scope; if absent, `doctor` prints the exact
   `gh auth refresh` command.
2. **Repository visibility.** Private-repo commits appear only if the user has
   enabled private contributions, and then only as unlabeled squares. The wizard
   defaults the solutions repo to public and explains why.

## Error handling

Every failure degrades to a working path. The loop must never strand the user.

| Condition | Behaviour |
|---|---|
| No network / API shape changed | Fall back to slug parsing; prompt for the number; blank stub. Still scaffolds, still commits. |
| Examples cannot be parsed | Emit a `pytest.skip` placeholder, never a failing test. Our parser's limits must not block the user's commit. |
| Problem is design/in-place/multi-answer | Detected by shape; falls back to the skip placeholder rather than generating a confidently wrong test. |
| `isPaidOnly` (premium) | `content` is null; scaffold from metadata alone. |
| HTTP 429 | Serve from cache; back off; never hard-fail a scaffold. |
| Push fails | The commit stands. Queued and retried on next push. Work is never lost. |
| Folder already exists | Prompt: resume, or create a new attempt directory for deliberate re-practice. |
| A problem is already active | Prompt: park the current one, or resume it. Never silently overwrite state. |
| `code` not on PATH | Warn once; skip opening; continue. |
| Window close fails | Silent no-op. Never fails a commit. |
| git identity unset | Blocked at first run with the exact commands to fix it. |

## Configuration

Stored in `%APPDATA%\leetgrind\config.toml` — outside the solutions repo, since
config contains the path to that repo.

```toml
repo_path      = "C:/Users/User/Documents/leetcode-solutions"
language       = "python"
auto_close     = true
auto_push      = true
gate_on_tests  = true
open_browser   = false
active_list    = "blind75"
clipboard_hint = true
```

`.lc/state.json` (active problem) and `.lc/cache/` live in the solutions repo and
are gitignored. State carries a schema version so future changes can migrate.

## Repo hygiene

The wizard writes `.gitignore` (`__pycache__/`, `.pytest_cache/`, `.lc/`) and
`.gitattributes` (`* text=auto eol=lf`) into the solutions repo at creation.
Without these, cache directories pollute every commit and CRLF churn makes diffs
unreadable on Windows.

## Packaging

A PowerShell script generates a `.lnk` shortcut with a custom icon, pointing at
the installed entry point. Double-clickable, pinnable to the taskbar, no terminal
typing.

PyInstaller single-file executables are deliberately not used: they are a known
Windows Defender false-positive pattern, and having the tool quarantined
mid-session is a worse failure than needing Python installed. A frozen build can
be added later if portability to a Python-less machine is ever required.

## Testing

**Unit** — slug parsing against a corpus of real URLs including query-parameter
and bare-slug forms; GraphQL response → dataclass; example extraction against
saved HTML fixtures covering standard, design, in-place, and multi-answer
problems; folder naming; streak arithmetic across timezone boundaries; README
table generation.

**Integration** — a throwaway git repo in a temp directory with LeetCode stubbed;
run start → solve end to end; assert exactly two commits with the expected
messages, and that the working tree is clean afterwards.

**Contract** — the GraphQL query and a recorded response fixture are pinned in
one place, so an upstream schema change fails a test rather than failing the user
at 11pm.

Network is mocked everywhere. One live smoke test exists but is opt-in, so a
LeetCode outage cannot turn the suite red.

## Out of scope for v1

Multi-language support, spaced repetition, LeetCode authentication and submission
reading, GitHub Actions CI, a graphical window, and a mistakes/notes log. Each is
additive; none is required for the loop to work.
