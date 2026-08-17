# LeetGrind

A Windows CLI that automates the LeetCode solve loop so the work shows up on
your GitHub contribution graph.

Paste a link → it scaffolds a folder, commits `Start N`, and opens VS Code.
Solve it, run `lc done` → it runs the tests, commits `Solve N`, pushes, and
closes the window.

## Install

Requires Python 3.12+, git, and (optionally) VS Code with the `code` command on
PATH.

```
pip install .
```

That gives you an `lc` command. Then:

```
lc doctor
```

`doctor` is the first thing to run. It checks the four things that silently
break the promise above:

- a config exists
- `git config user.name` / `user.email` are set
- your commit email is **verified on your GitHub account** — commits with an
  unverified address produce a full history and an empty graph
- an `origin` remote exists and your local commits have actually reached it
- `code` is on PATH

Fix anything it reports before you start; it prints the exact command for each.

## First run

```
lc
```

With no arguments `lc` opens the menu. On a fresh machine it asks where
solutions should live, whether to push after every commit, and offers to create
the GitHub repo for you with `gh repo create <name> --public --source . --remote
origin`. If you decline, or `gh` is not installed, it asks for a remote URL
instead.

**Say yes to public.** Private-repo commits appear on the contribution graph
only if you have opted into private contributions, and then only as unlabeled
squares.

## Commands

| Command | Effect |
|---|---|
| `lc` | Open the menu (what the desktop shortcut runs) |
| `lc new <url\|slug>` | Scaffold, commit `Start`, open VS Code |
| `lc done` | Test, prompt, commit `Solve`, push, close the window |
| `lc park` | Commit the attempt as unsolved and move on |
| `lc daily` | `lc new` against today's daily challenge |
| `lc undo` | Soft-reset the last commit |
| `lc config` | Show settings; `--repo-path` repoints a moved repo |
| `lc doctor` | Diagnose environment and contribution-graph problems |

`lc new` takes a full URL or a bare slug. If LeetCode cannot be reached, pass
`--number <n>` and it scaffolds offline from the slug.

`lc done` will not commit while the generated tests fail. Pass `--force` to
commit anyway, or `lc park` to shelve the attempt.

## Desktop shortcut

```
powershell -ExecutionPolicy Bypass -File build\make_shortcut.ps1
```

That creates `LeetGrind.lnk` on your Desktop pointing at `lc`. Right-click it
and Pin to taskbar.

## Development

```
pip install -e ".[dev]"
python -m pytest -q
```
