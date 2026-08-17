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


def _has_local_git_config(repo_path) -> tuple[str, str]:
    """Check if repo has local git config for name and email."""
    try:
        result_name = subprocess.run(["git", "-C", str(repo_path), "config", "--local", "user.name"],
                                     capture_output=True, text=True)
        result_email = subprocess.run(["git", "-C", str(repo_path), "config", "--local", "user.email"],
                                      capture_output=True, text=True)
        name = result_name.stdout.strip() if result_name.returncode == 0 else ""
        email = result_email.stdout.strip() if result_email.returncode == 0 else ""
        return name, email
    except (OSError, ValueError):
        return "", ""


def run_checks(cfg: Config | None) -> list[Check]:
    checks = [Check("configured", cfg is not None,
                    "config found" if cfg else "no config yet",
                    "" if cfg else "run the first-run wizard")]

    if cfg:
        local_name, local_email = _has_local_git_config(cfg.repo_path)
        has_identity = bool(local_name and local_email)
        detail = f"{local_name} <{local_email}>" if local_email else "user.name/user.email unset"
    else:
        has_identity = False
        local_email = ""
        detail = "user.name/user.email unset"

    checks.append(Check("git identity set", has_identity, detail,
                        'git config --global user.email "you@example.com"'))

    emails = github_emails()
    if emails is None:
        checks.append(Check("commit email counts on GitHub", False,
                            "cannot read GitHub emails (missing 'user' scope)", REFRESH))
    elif local_email and local_email in emails:
        checks.append(Check("commit email counts on GitHub", True,
                            f"{local_email} is verified on your account"))
    else:
        checks.append(Check(
            "commit email counts on GitHub", False,
            f"{local_email or '(unset)'} is NOT a verified email on your GitHub account - "
            "commits will not appear on your contribution graph",
            f'git config --global user.email "{emails[0]}"' if emails else REFRESH))

    checks.append(Check("VS Code on PATH", code_available(),
                        "found" if code_available() else "`code` not found",
                        "VS Code > Command Palette > Shell Command: Install 'code' command"))
    return checks
