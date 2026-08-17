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
    except (OSError, json.JSONDecodeError, KeyError, TypeError, AttributeError):
        return None


def run_checks(cfg: Config | None) -> list[Check]:
    checks = [Check("configured", cfg is not None,
                    "config found" if cfg else "no config yet",
                    "" if cfg else "run the first-run wizard")]

    name, email = identity(cfg.repo_path) if cfg else ("", "")
    has_identity = bool(name and email)
    detail = f"{name} <{email}>" if email else "user.name/user.email unset"

    checks.append(Check("git identity set", has_identity, detail,
                        'git config user.email "you@example.com"'))

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
            f'git config user.email "{emails[0]}"' if emails else
            "Add a verified email to your GitHub account (github.com/settings/emails)"))

    checks.append(Check("VS Code on PATH", code_available(),
                        "found" if code_available() else "`code` not found",
                        "VS Code > Command Palette > Shell Command: Install 'code' command"))
    return checks
