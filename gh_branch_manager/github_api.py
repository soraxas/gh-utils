"""GitHub API wrapper for branch operations using gh CLI."""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Set, Tuple


class MergeStatus(Enum):
    """Status of whether a branch is merged."""

    UNKNOWN = "unknown"
    MERGED = "merged"
    NOT_MERGED = "not_merged"
    FETCHING = "fetching"


class PRStatus(Enum):
    """Status of whether a branch has a closed PR."""

    UNKNOWN = "unknown"
    CLOSED = "closed"
    NOT_CLOSED = "not_closed"
    FETCHING = "fetching"


@dataclass
class BranchInfo:
    """Information about a GitHub branch."""

    name: str
    status: str  # identical, ahead, behind, diverged, unknown, fetching
    merge_status: MergeStatus = MergeStatus.UNKNOWN
    pr_status: PRStatus = PRStatus.UNKNOWN
    is_protected: bool = False
    is_default: bool = False
    ahead_by: Optional[int] = None
    behind_by: Optional[int] = None

    # Legacy properties for backward compatibility
    @property
    def is_merged(self) -> bool:
        """Check if branch is merged (backward compatibility)."""
        return self.merge_status == MergeStatus.MERGED

    @property
    def is_pr_closed(self) -> bool:
        """Check if branch has closed PR (backward compatibility)."""
        return self.pr_status == PRStatus.CLOSED


class GitHubBranchManager:
    """Manages GitHub branch operations using gh CLI."""

    DEFAULT_PROTECTED_REGEX = r"^(main|master|staging|dev|develop)$"

    def __init__(self):
        """Initialize the branch manager."""
        self.repo_full: Optional[str] = None
        self.default_branch: Optional[str] = None
        self.branches: List[BranchInfo] = []
        self._merged_branches: Set[str] = set()
        self._closed_pr_branches: Set[str] = set()

    def check_gh_auth(self) -> bool:
        """Check if gh CLI is authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_repo_info(self) -> Tuple[str, str]:
        """Get repository name and default branch."""
        try:
            # Get repo full name
            result = subprocess.run(
                [
                    "gh",
                    "repo",
                    "view",
                    "--json",
                    "nameWithOwner",
                    "-q",
                    ".nameWithOwner",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise Exception(f"Failed to get repo info: {result.stderr}")
            self.repo_full = result.stdout.strip()

            # Get default branch
            result = subprocess.run(
                [
                    "gh",
                    "repo",
                    "view",
                    "--json",
                    "defaultBranchRef",
                    "-q",
                    ".defaultBranchRef.name",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise Exception(f"Failed to get default branch: {result.stderr}")
            self.default_branch = result.stdout.strip()

            return self.repo_full, self.default_branch
        except subprocess.TimeoutExpired:
            raise Exception("Timeout while fetching repository information")
        except FileNotFoundError:
            raise Exception("gh CLI not found. Please install GitHub CLI.")

    def fetch_branches(
        self, progress_callback=None, incremental_callback=None
    ) -> List[BranchInfo]:
        """Fetch all branches with their status.

        Args:
            progress_callback: Optional callback function to report progress.
                               Called with (stage, message) strings.
            incremental_callback: Optional callback function for incremental updates.
                                  Called with (branch_info) after each branch is processed.
        """
        if not self.repo_full or not self.default_branch:
            self.get_repo_info()

        # Get all remote branches FIRST for immediate display
        if progress_callback:
            progress_callback("branches", "Fetching all remote branches...")
        branches = self._fetch_all_branches()

        # Immediately display all branches with "fetching" status for merge/PR info
        if incremental_callback:
            for branch_name in branches:
                # Create a placeholder branch info with fetching statuses
                placeholder = BranchInfo(
                    name=branch_name,
                    status="fetching",
                    merge_status=MergeStatus.FETCHING,
                    pr_status=PRStatus.FETCHING,
                )
                incremental_callback(placeholder)

        # Now fetch merged PR branches in background
        if progress_callback:
            progress_callback("merged", "Fetching merged PR branches...")
        self._fetch_merged_branches()

        # Update all branches with merge status
        if incremental_callback:
            for branch_name in branches:
                update = BranchInfo(
                    name=branch_name,
                    status="fetching",
                    merge_status=MergeStatus.MERGED
                    if branch_name in self._merged_branches
                    else MergeStatus.NOT_MERGED,
                    pr_status=PRStatus.FETCHING,
                )
                incremental_callback(update)

        # Get closed (not merged) PR branches
        if progress_callback:
            progress_callback("closed", "Fetching closed PR branches...")
        self._fetch_closed_pr_branches()

        # Update all branches with PR status
        if incremental_callback:
            for branch_name in branches:
                update = BranchInfo(
                    name=branch_name,
                    status="fetching",
                    merge_status=MergeStatus.MERGED
                    if branch_name in self._merged_branches
                    else MergeStatus.NOT_MERGED,
                    pr_status=PRStatus.CLOSED
                    if branch_name in self._closed_pr_branches
                    else PRStatus.NOT_CLOSED,
                )
                incremental_callback(update)

        # Now update branch statuses using parallel fetching for better performance
        if progress_callback:
            progress_callback(
                "status", f"Fetching status for {len(branches)} branches..."
            )

        self.branches = []
        completed_count = 0

        # Use ThreadPoolExecutor to fetch branch statuses in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all branch info fetch tasks
            future_to_branch = {
                executor.submit(self._get_branch_info, branch_name): branch_name
                for branch_name in branches
            }

            # Process results as they complete
            for future in as_completed(future_to_branch):
                branch_name = future_to_branch[future]
                try:
                    branch_info = future.result()
                    self.branches.append(branch_info)
                    completed_count += 1

                    # Update progress
                    if progress_callback and (
                        completed_count == 1
                        or completed_count % 5 == 0
                        or completed_count == len(branches)
                    ):
                        progress_callback(
                            "status",
                            f"Fetching status... ({completed_count}/{len(branches)})",
                        )

                    # Call incremental callback to update UI immediately
                    if incremental_callback:
                        incremental_callback(branch_info)
                except Exception as e:
                    # If a branch fetch fails, create a minimal entry
                    branch_info = BranchInfo(
                        name=branch_name,
                        status="unknown",
                        merge_status=MergeStatus.MERGED
                        if branch_name in self._merged_branches
                        else MergeStatus.NOT_MERGED,
                        pr_status=PRStatus.CLOSED
                        if branch_name in self._closed_pr_branches
                        else PRStatus.NOT_CLOSED,
                    )
                    self.branches.append(branch_info)
                    if incremental_callback:
                        incremental_callback(branch_info)

        return self.branches

    def _fetch_merged_branches(self):
        """Fetch branches with merged PRs."""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--state",
                    "merged",
                    "--limit",
                    "200",
                    "--json",
                    "headRefName",
                    "--jq",
                    ".[].headRefName",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                self._merged_branches = set(
                    line.strip()
                    for line in result.stdout.strip().split("\n")
                    if line.strip()
                )
        except subprocess.TimeoutExpired:
            pass

    def _fetch_closed_pr_branches(self):
        """Fetch branches with closed (not merged) PRs."""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--state",
                    "closed",
                    "--limit",
                    "200",
                    "--json",
                    "headRefName,mergedAt",
                    "--jq",
                    ".[] | select(.mergedAt == null) | .headRefName",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                self._closed_pr_branches = set(
                    line.strip()
                    for line in result.stdout.strip().split("\n")
                    if line.strip()
                )
        except subprocess.TimeoutExpired:
            pass

    def _fetch_all_branches(self) -> List[str]:
        """Fetch all branch names."""
        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{self.repo_full}/branches?per_page=100",
                    "--paginate",
                    "--jq",
                    ".[].name",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return [
                    line.strip()
                    for line in result.stdout.strip().split("\n")
                    if line.strip()
                ]
            return []
        except subprocess.TimeoutExpired:
            return []

    def _get_branch_info(self, branch_name: str) -> BranchInfo:
        """Get detailed information about a branch."""
        import re

        # Check if protected
        is_protected = bool(re.match(self.DEFAULT_PROTECTED_REGEX, branch_name))

        # Check if default branch
        is_default = branch_name == self.default_branch

        # Determine merge and PR status using enums
        merge_status = (
            MergeStatus.MERGED
            if branch_name in self._merged_branches
            else MergeStatus.NOT_MERGED
        )
        pr_status = (
            PRStatus.CLOSED
            if branch_name in self._closed_pr_branches
            else PRStatus.NOT_CLOSED
        )

        # Get compare status
        status = "unknown"
        ahead_by = None
        behind_by = None
        if is_protected or is_default:
            status = "protected"
        else:
            status, ahead_by, behind_by = self._get_compare_status(branch_name)

        return BranchInfo(
            name=branch_name,
            status=status,
            merge_status=merge_status,
            pr_status=pr_status,
            is_protected=is_protected,
            is_default=is_default,
            ahead_by=ahead_by,
            behind_by=behind_by,
        )

    def _get_compare_status(
        self, branch_name: str
    ) -> Tuple[str, Optional[int], Optional[int]]:
        """Get the compare status of a branch against the default branch.

        Returns:
            Tuple of (status, ahead_by, behind_by)
        """
        try:
            # URL encode the comparison
            import urllib.parse

            comparison = f"{self.default_branch}...{branch_name}"
            encoded = urllib.parse.quote(comparison, safe="")

            result = subprocess.run(
                ["gh", "api", f"repos/{self.repo_full}/compare/{encoded}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                status = data.get("status", "unknown")
                ahead_by = data.get("ahead_by")
                behind_by = data.get("behind_by")
                return status, ahead_by, behind_by
            return "unknown", None, None
        except (subprocess.TimeoutExpired, Exception):
            return "unknown", None, None

    def delete_branch(self, branch_name: str) -> Tuple[bool, str]:
        """Delete a branch.

        Returns:
            Tuple: (success, message)
        """
        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    "-X",
                    "DELETE",
                    f"repos/{self.repo_full}/git/refs/heads/{branch_name}",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return True, f"Successfully deleted {branch_name}"

            # Check for common error cases
            if "Reference does not exist" in result.stderr:
                return False, f"Branch {branch_name} does not exist"
            else:
                return False, f"Failed to delete {branch_name}: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, f"Timeout while deleting {branch_name}"
        except Exception as e:
            return False, f"Error deleting {branch_name}: {str(e)}"

    def delete_branches(
        self, branch_names: List[str], progress_callback=None
    ) -> List[Tuple[str, bool, str]]:
        """Delete multiple branches.

        Args:
            branch_names: List of branch names to delete
            progress_callback: Optional callback function to report progress.
                               Called with (current, total, branch_name) integers and string.

        Returns:
            List of tuples: (branch_name, success, message)
        """
        results = []
        total = len(branch_names)
        for idx, branch_name in enumerate(branch_names, 1):
            if progress_callback:
                progress_callback(idx, total, branch_name)
            success, message = self.delete_branch(branch_name)
            results.append((branch_name, success, message))
        return results
