"""First-run setup. Takes already-collected answers so it is testable
without a TTY; menu.py owns the questionary prompts that gather them."""
from pathlib import Path

from .config import Config, save_config
from .repo import init_repo


def first_run(answers: dict) -> Config:
    """Create the solutions repo and persist config. Safe to re-run.

    init_repo() only creates .git if it is missing and only (re)writes
    .gitignore/.gitattributes, so re-running this against an existing repo
    never touches existing problem folders or history.
    """
    repo = Path(answers["repo_path"])
    init_repo(repo)
    cfg = Config(repo_path=repo,
                 auto_push=answers.get("auto_push", True),
                 auto_close=answers.get("auto_close", True),
                 gate_on_tests=answers.get("gate_on_tests", True))
    save_config(cfg)
    return cfg
