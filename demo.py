#!/usr/bin/env python3
"""Demo script to test the TUI without authentication."""

from gh_branch_manager.app import BranchManagerApp
from gh_branch_manager.github_api import BranchInfo, MergeStatus, PRStatus


def demo_mode():
    """Run the app in demo mode with sample data."""
    app = BranchManagerApp()

    # Add some sample branch data for demo purposes
    app.branches_data = [
        BranchInfo(name="main", status="protected", is_protected=True, is_default=True),
        BranchInfo(name="develop", status="protected", is_protected=True),
        BranchInfo(
            name="feature/add-auth", status="ahead", merge_status=MergeStatus.NOT_MERGED
        ),
        BranchInfo(
            name="feature/update-ui",
            status="diverged",
            merge_status=MergeStatus.MERGED,
            pr_status=PRStatus.NOT_CLOSED,
        ),
        BranchInfo(
            name="bugfix/fix-login", status="identical", merge_status=MergeStatus.MERGED
        ),
        BranchInfo(
            name="hotfix/security-patch",
            status="behind",
            merge_status=MergeStatus.MERGED,
        ),
        BranchInfo(
            name="feature/new-feature",
            status="ahead",
            merge_status=MergeStatus.NOT_MERGED,
        ),
        BranchInfo(
            name="old-branch",
            status="identical",
            merge_status=MergeStatus.MERGED,
            pr_status=PRStatus.CLOSED,
        ),
    ]

    # Update info panel with demo info
    app.gh_manager.repo_full = "demo/repository"
    app.gh_manager.default_branch = "main"

    return app


if __name__ == "__main__":
    import sys

    if "--demo" in sys.argv:
        print("Running in demo mode with sample data...")
        app = demo_mode()
        # Skip the on_mount which would try to fetch real data
        app.run()
    else:
        print("This is a demo script. Use --demo flag to run with sample data.")
        print("To use the real app, ensure gh CLI is authenticated and run:")
        print("  gh-branch-manager-tui")
