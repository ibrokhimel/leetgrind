import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .editor import code_available
from .repo import identity, remote_url, unpushed_count

REFRESH = "gh auth refresh -h github.com -s user"
CREATE = "gh repo create <name> --public --source . --remote origin"


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
    except (OSError, json.JSONDecodeError, KeyError, TypeError, AttributeError):
        return None


def run_checks(cfg: Config | None) -> list[Check]:
    checks = [Check("configured", cfg is not None,
                    "config found" if cfg else "no config yet",
                    "" if cfg else "run the first-run wizard")]

    # With no config there is no repo to read, but git identity is normally
    # *global* - so read it from the home directory rather than reporting a
    # fabricated "unset" (which would also feed an empty address into the
    # GitHub check below and emit the scariest message the tool has).
    name, email = identity(cfg.repo_path if cfg else Path.home())
    has_identity = bool(name and email)
    detail = f"{name} <{email}>" if email else "user.name/user.email unset"

    checks.append(Check("git identity set", has_identity, detail,
                        'git config user.email "you@example.com"'))

    emails = github_emails()
    if not email:
        # Never render "(unset) is NOT a verified email ... commits will not
        # appear on your contribution graph" without evidence: it is the most
        # alarming line the tool has and it used to fire on every fresh run.
        checks.append(Check("commit email counts on GitHub", False,
                            "not checked - no git commit email set yet",
                            'git config --global user.email "you@example.com"'))
    elif emails is None:
        checks.append(Check("commit email counts on GitHub", False,
                            "cannot read GitHub emails (missing 'user' scope)", REFRESH))
    elif email in emails:
        checks.append(Check("commit email counts on GitHub", True,
                            f"{email} is verified on your account"))
    else:
        checks.append(Check(
            "commit email counts on GitHub", False,
            f"{email or '(unset)'} is NOT a verified email on your GitHub account - "
            "commits will not appear on your contribution graph",
            f'git config user.email "{emails[0]}"' if emails else
            "Add a verified email to your GitHub account (github.com/settings/emails)"))

    checks.extend(_remote_checks(cfg))

    code_ok = code_available()
    checks.append(Check("VS Code on PATH", code_ok,
                        "found" if code_ok else "`code` not found",
                        "VS Code > Command Palette > Shell Command: Install 'code' command"))
    return checks


def _remote_checks(cfg: Config | None) -> list[Check]:
    """Perfect local commits with no remote are the silent failure this whole
    tool exists to prevent, so make it detectable rather than invisible."""
    if cfg is None:
        return [Check("git remote configured", False,
                      "not checked - no config yet", "run the first-run wizard")]
    url = remote_url(cfg.repo_path)
    checks = [Check("git remote configured", bool(url),
                    url or "no `origin` remote - commits never leave this machine",
                    CREATE)]
    if not url:
        return checks
    ahead = unpushed_count(cfg.repo_path)
    checks.append(Check(
        "local commits are on origin", ahead == 0,
        "up to date with origin" if ahead == 0 else
        f"{ahead} commit(s) not pushed" if ahead else
        "no origin/<branch> yet - nothing has ever been pushed",
        "git push -u origin HEAD"))
    return checks
