#!/usr/bin/env python3
"""Tests for the GitHub Branch Manager TUI."""

import sys

from gh_branch_manager.app import BranchManagerApp
from gh_branch_manager.github_api import (
    BranchInfo,
    GitHubBranchManager,
    MergeStatus,
    PRStatus,
)


def test_github_api():
    """Test GitHub API wrapper."""
    print("Testing GitHub API wrapper...")

    gh = GitHubBranchManager()

    # Test authentication check
    is_authed = gh.check_gh_auth()
    print(f"  ✓ Auth check: {is_authed}")

    # Test branch info creation with new enum-based structure
    branch = BranchInfo(
        name="test-branch",
        status="ahead",
        merge_status=MergeStatus.MERGED,
        pr_status=PRStatus.NOT_CLOSED,
        is_protected=False,
        is_default=False,
    )
    assert branch.name == "test-branch"
    assert branch.status == "ahead"
    assert branch.merge_status == MergeStatus.MERGED
    assert branch.pr_status == PRStatus.NOT_CLOSED
    assert branch.is_merged is True  # Using backward compatibility property
    assert branch.is_pr_closed is False  # Using backward compatibility property
    print("  ✓ BranchInfo creation works")

    print("✅ GitHub API tests passed\n")


def test_app_creation():
    """Test app creation."""
    print("Testing app creation...")

    app = BranchManagerApp()
    assert app is not None
    assert app.gh_manager is not None
    assert app.selected_branches == set()
    assert app.branches_data == []
    print("  ✓ App created successfully")

    # Test with sample data
    app.branches_data = [
        BranchInfo(
            name="main",
            status="protected",
            is_protected=True,
            is_default=True,
            merge_status=MergeStatus.NOT_MERGED,
            pr_status=PRStatus.NOT_CLOSED,
        ),
        BranchInfo(
            name="feature/test",
            status="ahead",
            merge_status=MergeStatus.NOT_MERGED,
            pr_status=PRStatus.NOT_CLOSED,
        ),
        BranchInfo(
            name="bugfix/old",
            status="identical",
            merge_status=MergeStatus.MERGED,
            pr_status=PRStatus.NOT_CLOSED,
        ),
    ]

    assert len(app.branches_data) == 3
    print("  ✓ Sample data added")

    # Verify branch properties
    main_branch = app.branches_data[0]
    assert main_branch.name == "main"
    assert main_branch.is_protected is True
    assert main_branch.is_default is True
    print("  ✓ Branch properties verified")

    feature_branch = app.branches_data[1]
    assert feature_branch.status == "ahead"
    assert feature_branch.is_merged is False
    print("  ✓ Feature branch properties verified")

    # Test selection
    app.selected_branches.add("feature/test")
    assert "feature/test" in app.selected_branches
    print("  ✓ Branch selection works")

    print("✅ App tests passed\n")


def test_filtering():
    """Test filtering logic."""
    print("Testing filtering logic...")

    branches = [
        BranchInfo(
            name="main",
            status="protected",
            is_protected=True,
            merge_status=MergeStatus.NOT_MERGED,
            pr_status=PRStatus.NOT_CLOSED,
            is_default=True,
        ),
        BranchInfo(
            name="feature/auth",
            status="ahead",
            merge_status=MergeStatus.NOT_MERGED,
            pr_status=PRStatus.NOT_CLOSED,
            is_protected=False,
            is_default=False,
        ),
        BranchInfo(
            name="feature/ui",
            status="diverged",
            merge_status=MergeStatus.NOT_MERGED,
            pr_status=PRStatus.NOT_CLOSED,
            is_protected=False,
            is_default=False,
        ),
        BranchInfo(
            name="bugfix/login",
            status="identical",
            merge_status=MergeStatus.MERGED,
            pr_status=PRStatus.NOT_CLOSED,
            is_protected=False,
            is_default=False,
        ),
    ]

    # Test filter
    filter_text = "feature"
    filtered = [b for b in branches if filter_text.lower() in b.name.lower()]
    assert len(filtered) == 2
    assert all("feature" in b.name for b in filtered)
    print("  ✓ Filtering works correctly")

    print("✅ Filtering tests passed\n")


def test_sorting():
    """Test sorting logic."""
    print("Testing sorting logic...")

    branches = [
        BranchInfo(
            name="z-branch",
            status="ahead",
            merge_status=MergeStatus.NOT_MERGED,
            pr_status=PRStatus.NOT_CLOSED,
            is_protected=False,
            is_default=False,
        ),
        BranchInfo(
            name="a-branch",
            status="diverged",
            merge_status=MergeStatus.MERGED,
            pr_status=PRStatus.NOT_CLOSED,
            is_protected=False,
            is_default=False,
        ),
        BranchInfo(
            name="m-branch",
            status="identical",
            merge_status=MergeStatus.MERGED,
            pr_status=PRStatus.NOT_CLOSED,
            is_protected=False,
            is_default=False,
        ),
    ]

    # Sort by name
    sorted_by_name = sorted(branches, key=lambda b: b.name)
    assert sorted_by_name[0].name == "a-branch"
    assert sorted_by_name[-1].name == "z-branch"
    print("  ✓ Sort by name works")

    # Sort by merged status
    sorted_by_merged = sorted(branches, key=lambda b: (not b.is_merged, b.name))
    merged_count = sum(1 for b in sorted_by_merged[:2] if b.is_merged)
    assert merged_count == 2
    print("  ✓ Sort by merged status works")

    print("✅ Sorting tests passed\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("GitHub Branch Manager TUI - Test Suite")
    print("=" * 60 + "\n")

    try:
        test_github_api()
        test_app_creation()
        test_filtering()
        test_sorting()

        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
