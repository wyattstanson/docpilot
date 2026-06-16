"""GitHub integration: fix branches, pull requests, and PR comments.

Local git operations (branch / commit / push) run via subprocess so they work
against the checkout that GitHub Actions already provides. PyGithub is used only
for the API surface (opening PRs, upserting comments). Both degrade gracefully:
with no token or no PyGithub installed the integration runs in *dry-run* mode,
logging what it would do and returning a synthetic PR URL, so the entrypoint and
tests never crash.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("docpilot.github")

# Hidden marker so we can find and update our own comment instead of spamming.
_COMMENT_MARKER = "<!-- docpilot-summary -->"


@dataclass
class PRResult:
    url: str
    number: Optional[int]
    dry_run: bool


class GitHubIntegration:
    def __init__(
        self,
        repo_root: str,
        repo_full_name: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.repo_full_name = repo_full_name or os.environ.get("GITHUB_REPOSITORY")
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self._gh = self._maybe_client()

    @property
    def dry_run(self) -> bool:
        return self._gh is None or not self.repo_full_name

    def _maybe_client(self):
        if not self.token:
            logger.info("No GITHUB_TOKEN; GitHub integration in dry-run mode.")
            return None
        try:
            from github import Github  # lazy import (PyGithub)
        except ImportError:
            logger.info("PyGithub not installed; GitHub integration in dry-run mode.")
            return None
        try:
            return Github(self.token)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not init PyGithub: %s", exc)
            return None

    # -- git plumbing --------------------------------------------------------

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["git", "-C", str(self.repo_root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if check and result.returncode != 0:
            logger.warning("git %s failed: %s", " ".join(args), result.stderr.strip())
        return result

    def create_fix_pr(
        self,
        branch: str,
        base: str,
        title: str,
        body: str,
        files: list[str],
        commit_message: str,
    ) -> PRResult:
        """Commit ``files`` to a new ``branch`` and open a PR against ``base``."""
        if not files:
            return PRResult(url="", number=None, dry_run=True)

        # Always perform the local git work; it is safe in a checkout.
        self._configure_identity()
        self._git("checkout", "-B", branch)
        self._git("add", *files)
        commit = self._git("commit", "-m", commit_message, check=False)
        if commit.returncode != 0 and "nothing to commit" in (commit.stdout + commit.stderr):
            logger.info("No changes to commit for %s.", branch)
            return PRResult(url="", number=None, dry_run=True)

        if self.dry_run:
            logger.info("[dry-run] Would push %s and open PR: %s", branch, title)
            return PRResult(
                url=f"https://github.com/{self.repo_full_name or 'local/repo'}/pull/NEW",
                number=None,
                dry_run=True,
            )

        push = self._git("push", "--force", "origin", branch, check=False)
        if push.returncode != 0:
            logger.warning("Push failed; cannot open PR.")
            return PRResult(url="", number=None, dry_run=True)

        try:
            repo = self._gh.get_repo(self.repo_full_name)
            pr = repo.create_pull(title=title, body=body, head=branch, base=base)
            logger.info("Opened fix PR #%d: %s", pr.number, pr.html_url)
            return PRResult(url=pr.html_url, number=pr.number, dry_run=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to open PR: %s", exc)
            return PRResult(url="", number=None, dry_run=True)

    def _configure_identity(self) -> None:
        # Use the GitHub Actions bot identity if not already configured.
        if not self._git("config", "user.email", check=False).stdout.strip():
            self._git("config", "user.email", "docpilot[bot]@users.noreply.github.com")
            self._git("config", "user.name", "docpilot[bot]")

    # -- comments ------------------------------------------------------------

    def upsert_pr_comment(self, pr_number: int, body: str) -> bool:
        """Create or update DocPilot's summary comment on a PR."""
        full = f"{_COMMENT_MARKER}\n{body}"
        if self.dry_run:
            logger.info("[dry-run] Would post comment on PR #%s:\n%s", pr_number, body)
            return False
        try:
            repo = self._gh.get_repo(self.repo_full_name)
            issue = repo.get_issue(pr_number)
            for comment in issue.get_comments():
                if _COMMENT_MARKER in (comment.body or ""):
                    comment.edit(full)
                    logger.info("Updated DocPilot comment on PR #%d.", pr_number)
                    return True
            issue.create_comment(full)
            logger.info("Posted DocPilot comment on PR #%d.", pr_number)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to post comment: %s", exc)
            return False


def set_action_outputs(**outputs: object) -> None:
    """Write key=value pairs to ``$GITHUB_OUTPUT`` (no-op when unset)."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        for k, v in outputs.items():
            logger.info("output %s=%s", k, v)
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            for k, v in outputs.items():
                fh.write(f"{k}={v}\n")
    except OSError as exc:
        logger.warning("Could not write GITHUB_OUTPUT: %s", exc)
