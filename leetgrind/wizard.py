"""First-run setup. Takes already-collected answers so it is testable
without a TTY; menu.py owns the questionary prompts that gather them."""
from pathlib import Path

from .config import Config, save_config
from .repo import init_repo, remote_url, set_remote


def first_run(answers: dict) -> Config:
    """Create the solutions repo and persist config. Safe to re-run.

    init_repo() only creates .git if it is missing and only (re)writes
    .gitignore/.gitattributes, so re-running this against an existing repo
    never touches existing problem folders or history.

    `remote_url` in answers wires up `origin`. Without a remote every commit
    stays on this machine and the contribution graph - the entire point of
    the tool - stays empty. menu._ensure_remote collects it.
    """
    repo = Path(answers["repo_path"])
    init_repo(repo)
    if answers.get("remote_url") and not remote_url(repo):
        set_remote(repo, answers["remote_url"])
    cfg = Config(repo_path=repo,
                 auto_push=answers.get("auto_push", True),
                 auto_close=answers.get("auto_close", True),
                 gate_on_tests=answers.get("gate_on_tests", True))
    save_config(cfg)
    return cfg
