"""Main Textual TUI application for GitHub branch management."""

from typing import List, Tuple

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static
from textual.worker import Worker, WorkerState

from .github_api import BranchInfo, GitHubBranchManager, MergeStatus, PRStatus


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Modal screen for confirming branch deletion."""

    DEFAULT_CSS = """
    ConfirmDeleteScreen {
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("y", "dismiss(True)", "Yes", priority=True),
        Binding("n", "dismiss(False)", "No", priority=True),
        Binding("escape", "dismiss(False)", "Cancel", priority=True),
    ]

    def __init__(self, branch_count: int, branch_names: List[str]):
        super().__init__()
        self.branch_count = branch_count
        self.branch_names = branch_names

    def compose(self) -> ComposeResult:
        """Compose the confirmation dialog."""
        with Container(id="confirm-dialog"):
            yield Label(
                f"⚠️  Delete {self.branch_count} branch(es)?", id="confirm-title"
            )
            yield Label(
                "\n".join(f"  • {name}" for name in self.branch_names[:10])
                + (
                    f"\n  ... and {len(self.branch_names) - 10} more"
                    if len(self.branch_names) > 10
                    else ""
                ),
                id="confirm-branches",
            )
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes (Y)", variant="error", id="yes-button")
                yield Button("No (N)", variant="primary", id="no-button")

    def on_mount(self) -> None:
        """Focus the No button by default."""
        self.query_one("#no-button", Button).focus()

    @on(Button.Pressed, "#yes-button")
    def on_yes_pressed(self) -> None:
        """Handle Yes button press."""
        self.log("🟢 Yes button pressed - dismissing with True")
        self.dismiss(True)

    @on(Button.Pressed, "#no-button")
    def on_no_pressed(self) -> None:
        """Handle No button press."""
        self.log("🔴 No button pressed - dismissing with False")
        self.dismiss(False)


class BranchManagerApp(App):
    """A Textual app for managing GitHub branches."""

    CSS = """
    Screen {
        background: $surface;
    }

    #info-panel {
        height: 4;
        background: $boost;
        border: solid $primary;
        padding: 0 1;
    }

    #filter-input {
        height: 3;
        border: solid $accent;
        margin-bottom: 1;
    }

    #branch-table {
        height: 1fr;
    }

    #status-bar {
        height: 3;
        background: $panel;
        border: solid $primary;
        padding: 0 1;
    }

    #confirm-dialog {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }

    #confirm-title {
        text-align: center;
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }

    #confirm-branches {
        margin-bottom: 1;
        max-height: 15;
        overflow-y: auto;
    }

    #confirm-buttons {
        align: center middle;
        height: auto;
    }

    #confirm-buttons Button {
        margin: 0 1;
    }

    DataTable > .datatable--cursor {
        background: $accent 20%;
    }

    DataTable > .datatable--header {
        text-style: bold;
        background: $boost;
    }

    .selected-row {
        background: $secondary 40%;
    }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("a", "auto_select_merged", "Auto-select merged", priority=True),
        Binding("d", "delete_selected", "Delete selected", priority=True),
        Binding("space", "toggle_selection", "Toggle selection", priority=True),
        Binding("c", "clear_selection", "Clear selection", priority=True),
        Binding("/", "focus_filter", "Filter", priority=True),
        Binding("escape", "clear_filter", "Clear filter", priority=True),
        Binding("s", "cycle_sort", "Sort", priority=True),
        Binding("q", "quit", "Quit", priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.gh_manager = GitHubBranchManager()
        self.selected_branches = set()
        self.branches_data = []
        self.branches_dict = {}  # Map branch names to indices for fast lookup
        self.filter_text = ""
        self.sort_mode = "name"  # name, status, or merged
        self._loading = False

    def _progress_status_update(self, message: str) -> None:
        """Update status bar with progress message (for use in threads)."""
        self.update_status(f"🔄 {message}")

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Static("", id="info-panel")
        yield Input(
            placeholder="Filter branches (press / to focus, ESC to clear)...",
            id="filter-input",
        )
        yield DataTable(id="branch-table", cursor_type="row", zebra_stripes=True)
        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Set up the application on mount."""
        # Set up the table
        table = self.query_one("#branch-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Sel", "Branch Name", "Status", "Info")

        # Focus the table by default
        table.focus()

        # Start initial auth check and fetch in background
        self.check_auth_and_refresh()

    @work(exclusive=True, thread=True)
    def check_auth_and_refresh(self) -> None:
        """Check authentication and refresh in a background thread."""
        # Check gh authentication
        # if not self.gh_manager.check_gh_auth():
        #     self.call_from_thread(
        #         self.update_status,
        #         "❌ Error: gh CLI is not authenticated. Run 'gh auth login'",
        #         error=True,
        #     )
        #     return

        # Trigger refresh
        self.call_from_thread(self.action_refresh)

    def action_refresh(self) -> None:
        """Refresh the branch list."""
        # if self._loading:
        #     self.update_status("⏳ Already loading...", error=True)
        #     return

        # Clear existing data
        self.branches_data = []
        self.branches_dict = {}
        # self.selected_branches.clear()

        # Start the background fetch
        self.fetch_branches_background()

    @work(exclusive=True, thread=True)
    def fetch_branches_background(self) -> None:
        """Fetch branches in a background thread."""
        self._loading = True
        self.call_from_thread(
            self.update_status, "🔄 Fetching repository information..."
        )

        try:
            # Get repo info
            repo_full, default_branch = self.gh_manager.get_repo_info()

            # Update info panel on main thread
            info_text = f"📁 Repository: [bold]{repo_full}[/bold]  |  🌿 Default: [bold]{default_branch}[/bold]"
            self.call_from_thread(
                lambda: self.query_one("#info-panel", Static).update(info_text)
            )

            # Define progress callback
            def progress_callback(stage: str, message: str):
                self.call_from_thread(self._progress_status_update, message)

            # Define incremental callback to update UI as branches are fetched
            def incremental_callback(branch_info: BranchInfo):
                self.call_from_thread(self._handle_branch_update, branch_info)

            # Fetch branches with progress and incremental updates
            branches = self.gh_manager.fetch_branches(
                progress_callback=progress_callback,
                incremental_callback=incremental_callback,
            )

            # Final status update
            self.call_from_thread(
                self.update_status, f"✅ Loaded {len(branches)} branches"
            )

        except Exception as e:
            self.call_from_thread(self.update_status, f"❌ Error: {str(e)}", error=True)
        finally:
            self._loading = False

    def _handle_branch_update(self, branch_info: BranchInfo) -> None:
        """Handle a single branch update from background thread."""
        # Use dictionary for O(1) lookup instead of linear search
        if branch_info.name in self.branches_dict:
            # Update existing branch
            idx = self.branches_dict[branch_info.name]
            self.branches_data[idx] = branch_info
        else:
            # Add new branch
            idx = len(self.branches_data)
            self.branches_data.append(branch_info)
            self.branches_dict[branch_info.name] = idx

        # Update table display
        self._update_table()

    def _update_table(self, preserve_cursor: bool = False) -> None:
        """Update the data table with current branches.

        Args:
            preserve_cursor: If True, attempt to preserve cursor position by branch name
        """
        table = self.query_one("#branch-table", DataTable)

        # Save current cursor row's branch name if preserving cursor
        current_branch_name = None
        if preserve_cursor and table.cursor_row is not None:
            try:
                coordinate = table.cursor_coordinate
                if coordinate is not None:
                    row_key = table.coordinate_to_cell_key(coordinate).row_key
                    current_branch_name = (
                        str(row_key.value)
                        if hasattr(row_key, "value")
                        else str(row_key)
                    )
            except Exception:
                pass

        table.clear()

        # Filter branches based on filter text
        filtered_branches = [
            b for b in self.branches_data if self.filter_text.lower() in b.name.lower()
        ]

        # Sort branches
        if self.sort_mode == "name":
            filtered_branches.sort(key=lambda b: b.name)
        elif self.sort_mode == "status":
            status_order = {
                "protected": 0,
                "diverged": 1,
                "ahead": 2,
                "behind": 3,
                "identical": 4,
                "fetching": 5,
                "unknown": 6,
            }
            filtered_branches.sort(
                key=lambda b: (status_order.get(b.status, 7), b.name)
            )
        elif self.sort_mode == "merged":
            filtered_branches.sort(key=lambda b: (not b.is_merged, b.name))

        target_row_idx = None
        for idx, branch in enumerate(filtered_branches):
            # Selection indicator
            sel = "✓" if branch.name in self.selected_branches else " "

            # Branch name
            name = branch.name

            # Status with color and ahead/behind info
            status_text = self._format_status(branch)

            # Additional info
            info_parts = []

            # Show merge status
            if branch.merge_status == MergeStatus.MERGED:
                info_parts.append("merged")
            elif branch.merge_status == MergeStatus.FETCHING:
                info_parts.append("merge:fetching")

            # Show PR status
            if branch.pr_status == PRStatus.CLOSED:
                info_parts.append("PR closed")
            elif branch.pr_status == PRStatus.FETCHING:
                info_parts.append("PR:fetching")

            if branch.is_protected:
                info_parts.append("protected")
            if branch.is_default:
                info_parts.append("default")

            info = ", ".join(info_parts) if info_parts else ""

            # Add row
            row_key = table.add_row(sel, name, status_text, info, key=branch.name)

            # Track the row index for the current branch
            if current_branch_name and branch.name == current_branch_name:
                target_row_idx = idx

        # Restore cursor position if we found the branch
        if preserve_cursor and target_row_idx is not None and table.row_count > 0:
            try:
                table.move_cursor(row=target_row_idx)
            except Exception:
                pass

        # Update status with filter info
        if self.filter_text:
            self.update_status(
                f"🔍 Filtered: {len(filtered_branches)}/{len(self.branches_data)} branches | Sort: {self.sort_mode}"
            )

    def _format_status(self, branch: BranchInfo) -> Text:
        """Format status with colors and ahead/behind info."""
        status = branch.status

        # Build status text with ahead/behind info
        status_str = status
        if status in ["ahead", "behind", "diverged"]:
            parts = [status]
            if branch.ahead_by is not None and branch.ahead_by > 0:
                parts.append(f"↑{branch.ahead_by}")
            if branch.behind_by is not None and branch.behind_by > 0:
                parts.append(f"↓{branch.behind_by}")
            status_str = " ".join(parts)

        # Apply colors
        if status == "identical":
            return Text(status_str, style="blue")
        elif status == "behind":
            return Text(status_str, style="green")
        elif status == "ahead":
            return Text(status_str, style="yellow")
        elif status == "diverged":
            return Text(status_str, style="red")
        elif status == "protected":
            return Text(status_str, style="bold yellow")
        elif status == "fetching":
            return Text(status_str, style="dim italic")
        else:
            return Text(status_str, style="dim")

    def action_toggle_selection(self) -> None:
        """Toggle selection of the current branch."""
        table = self.query_one("#branch-table", DataTable)

        if table.cursor_row is None:
            return

        # Save cursor position
        current_row = table.cursor_row

        # Get the row key which is the branch name
        try:
            # Get the coordinate of the current cursor position
            coordinate = table.cursor_coordinate
            if coordinate is None:
                return

            # Get the row key for the current row
            row_key = table.coordinate_to_cell_key(coordinate).row_key
            branch_name = (
                str(row_key.value) if hasattr(row_key, "value") else str(row_key)
            )

            # Find the branch in our data
            branch = None
            for b in self.branches_data:
                if b.name == branch_name:
                    branch = b
                    break

            if not branch:
                return

            # Don't allow selection of protected or default branches
            if branch.is_protected or branch.is_default:
                self.update_status(
                    f"⚠️  Cannot select protected/default branch: {branch.name}",
                    error=True,
                )
                return

            if branch.name in self.selected_branches:
                self.selected_branches.remove(branch.name)
            else:
                self.selected_branches.add(branch.name)

            # Update table with cursor preservation
            self._update_table(preserve_cursor=True)

            # Move to next row if there is one
            try:
                if current_row < table.row_count - 1:
                    table.move_cursor(row=current_row + 1)
                else:
                    table.move_cursor(row=current_row)
            except Exception:
                # If we can't set cursor, that's okay
                pass

            self.update_status(f"Selected {len(self.selected_branches)} branch(es)")
        except (IndexError, AttributeError, Exception) as e:
            # Fallback: just show an error message
            self.update_status(f"⚠️  Could not toggle selection", error=True)
            return

    def action_auto_select_merged(self) -> None:
        """Auto-select all merged branches."""
        count = 0
        for branch in self.branches_data:
            # Skip protected and default branches
            if branch.is_protected or branch.is_default:
                continue

            # Select if merged and fully incorporated (identical or behind)
            if branch.is_merged and branch.status in ["identical", "behind"]:
                self.selected_branches.add(branch.name)
                count += 1

        self._update_table()
        self.update_status(f"✅ Auto-selected {count} merged branch(es)")

    def action_clear_selection(self) -> None:
        """Clear all selections."""
        self.selected_branches.clear()
        self._update_table()
        self.update_status("Cleared selection")

    def action_focus_filter(self) -> None:
        """Focus the filter input."""
        filter_input = self.query_one("#filter-input", Input)
        filter_input.focus()

    def action_clear_filter(self) -> None:
        """Clear the filter."""
        filter_input = self.query_one("#filter-input", Input)
        filter_input.value = ""
        self.filter_text = ""
        self._update_table()
        # Return focus to table
        table = self.query_one("#branch-table", DataTable)
        table.focus()

    def action_cycle_sort(self) -> None:
        """Cycle through sort modes."""
        sort_modes = ["name", "status", "merged"]
        current_idx = sort_modes.index(self.sort_mode)
        self.sort_mode = sort_modes[(current_idx + 1) % len(sort_modes)]
        self._update_table()
        self.update_status(f"Sort by: {self.sort_mode}")

    @on(Input.Changed, "#filter-input")
    def on_filter_changed(self, event: Input.Changed) -> None:
        """Handle filter text changes."""
        self.filter_text = event.value
        self._update_table()

    def action_delete_selected(self) -> None:
        """Delete selected branches with confirmation."""
        if not self.selected_branches:
            self.update_status("⚠️  No branches selected", error=True)
            return

        if self._loading:
            self.update_status(
                "⏳ Please wait for current operation to complete", error=True
            )
            return

        # Create list of branch names
        branch_names = sorted(self.selected_branches)

        def check_delete(confirmed: bool | None) -> None:
            """Called when ConfirmDeleteScreen is dismissed."""
            # Debug: Log the actual result received
            self.log(f"Dialog result: {confirmed!r} (type: {type(confirmed).__name__})")

            if confirmed is None:
                self.update_status("⚠️  Dialog dismissed without response", error=True)
                return

            if not confirmed:
                self.update_status("❌ Deletion cancelled")
                return

            # Start deletion in background
            self.update_status(
                f"✅ Confirmed - proceeding with deletion of {len(branch_names)} branch(es)"
            )
            self.delete_branches_background(branch_names)

        # Show confirmation dialog with callback
        self.push_screen(
            ConfirmDeleteScreen(len(branch_names), branch_names), check_delete
        )

    @work(exclusive=True, thread=True)
    def delete_branches_background(self, branch_names: List[str]) -> None:
        """Delete branches in a background thread."""
        self._loading = True

        # Perform deletion with progress updates
        total = len(branch_names)
        self.call_from_thread(self.update_status, f"🗑️  Deleting {total} branch(es)...")

        def progress_callback(current: int, total: int, branch_name: str):
            self.call_from_thread(
                self.update_status, f"🗑️  Deleting ({current}/{total}): {branch_name}..."
            )

        results = self.gh_manager.delete_branches(
            branch_names, progress_callback=progress_callback
        )

        # Count successes and failures
        success_count = sum(1 for _, success, _ in results if success)
        failure_count = len(results) - success_count

        # Update on main thread
        self.call_from_thread(
            self._handle_deletion_complete, results, success_count, failure_count
        )

        self._loading = False

    def _handle_deletion_complete(
        self,
        results: List[Tuple[str, bool, str]],
        success_count: int,
        failure_count: int,
    ) -> None:
        """Handle deletion completion from background thread."""
        # Clear selection of successfully deleted branches
        for branch_name, success, _ in results:
            if success and branch_name in self.selected_branches:
                self.selected_branches.remove(branch_name)

        # Show results
        if failure_count == 0:
            self.update_status(f"✅ Successfully deleted {success_count} branch(es)")
        else:
            self.update_status(
                f"⚠️  Deleted {success_count}, failed {failure_count}", error=True
            )

        # Refresh the branch list
        self.action_refresh()

    def update_status(self, message: str, error: bool = False) -> None:
        """Update the status bar."""
        style = "bold red" if error else "bold green"
        status_widget = self.query_one("#status-bar", Static)
        status_widget.update(f"[{style}]{message}[/{style}]")


def main():
    """Run the branch manager TUI."""
    app = BranchManagerApp()
    app.run()


if __name__ == "__main__":
    main()
