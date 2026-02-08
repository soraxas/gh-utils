# GitHub Branch Manager TUI

A modern, interactive Terminal User Interface (TUI) for managing GitHub branches, built with [Textual](https://github.com/Textualize/textual).

## Features

### Core Functionality

- 🔄 **Auto-fetch branches**: Automatically fetches all remote branches from GitHub with their current status
- ⚡ **Non-blocking operations**: All network/IO operations run in background threads with live progress updates
- 🎨 **Colorful display**: Clear visual indicators for branch status (merged, diverged, ahead, behind, etc.)
- 📊 **Real-time status updates**: Status bar shows detailed progress during fetch and delete operations
- ✅ **Multi-select**: Select multiple branches for batch deletion
- 🔍 **Smart filtering**: Quickly find branches by name
- 📊 **Multiple sort modes**: Sort by name, status, or merge status
- 🛡️ **Protected branches**: Automatically prevents deletion of protected branches (main, master, develop, etc.)
- ⚠️ **Confirmation prompts**: Always confirms before deleting branches

### Keyboard Shortcuts

| Key       | Action             | Description                                             |
| --------- | ------------------ | ------------------------------------------------------- |
| **R**     | Refresh            | Fetch latest branch data from GitHub                    |
| **↑/↓**   | Navigate           | Move up/down through branch list                        |
| **Space** | Toggle Selection   | Select/deselect current branch, then move to next       |
| **A**     | Auto-select Merged | Automatically select all safe-to-delete merged branches |
| **D**     | Delete Selected    | Delete selected branches (with confirmation)            |
| **C**     | Clear Selection    | Clear all selections                                    |
| **/**     | Filter             | Focus the filter input to search branches               |
| **Esc**   | Clear Filter       | Clear filter and return to table                        |
| **S**     | Sort               | Cycle through sort modes (name → status → merged)       |
| **Q**     | Quit               | Exit the application                                    |

## Installation

### Prerequisites

- Python 3.8 or higher
- [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated
- A Git repository

### Using UV (Recommended)

```bash
# Install UV if you haven't already
pip install uv

# Clone the repository (if you haven't)
cd your-git-repo

# Install the package
uv pip install -e .
```

### Using pip

```bash
pip install -e .
```

## Usage

### Quick Start

1. Navigate to any Git repository that has a GitHub remote
2. Ensure you're authenticated with `gh` CLI:
   ```bash
   gh auth login
   ```
3. Run the TUI:
   ```bash
   gh-branch-manager-tui
   ```

### Workflow Example

#### Cleaning up merged branches

1. Open the TUI: `gh-branch-manager-tui`
2. Press **R** to fetch latest branch data
3. Press **A** to auto-select all merged branches that are safe to delete
4. Review the selected branches (marked with ✓)
5. Press **D** to delete them
6. Confirm when prompted with **Y**

#### Finding and deleting specific branches

1. Open the TUI
2. Press **/** to focus the filter
3. Type part of the branch name (e.g., "feature/old")
4. Use **↑/↓** to navigate to specific branches
5. Press **Space** to select them
6. Press **D** to delete

#### Sorting branches by status

1. Open the TUI
2. Press **S** to cycle through sort modes:
   - **By name**: Alphabetical order
   - **By status**: Groups by diverged → ahead → behind → identical
   - **By merged**: Shows merged branches first

## Performance & Responsiveness

The TUI is designed to be highly responsive even with slow network connections:

### Non-Blocking Operations

- **All network/IO operations run in background threads** - The UI remains responsive during:
  - Initial branch fetching
  - Repository information retrieval
  - Branch deletion operations

### Incremental Loading

- **Branches display immediately** - No waiting for all data to load
  - All branches appear with "fetching" status as soon as the branch list is retrieved
  - Each branch updates individually as its status is fetched
  - Table updates in real-time as data comes in

### Live Progress Updates

The status bar provides real-time feedback during long operations:

- **During fetch**: Shows which stage of the process is running
  - "Fetching repository information..."
  - "Fetching merged PR branches..."
  - "Fetching closed PR branches..."
  - "Fetching all remote branches..."
  - "Fetching status... (5/47)" - Progress for individual branch status checks

- **During deletion**: Shows which branch is being deleted
  - "Deleting (1/10): feature/old-branch..."
  - "Deleting (2/10): bugfix/deprecated..."

### Concurrent Operation Prevention

- Multiple operations cannot run simultaneously (prevents conflicts)
- If you try to start a new operation while one is running, you'll see: "⏳ Please wait for current operation to complete"

## Branch Status Indicators

The TUI displays branches with color-coded status:

| Status        | Color          | Description               | Safe to Delete?    |
| ------------- | -------------- | ------------------------- | ------------------ |
| **identical** | 🔵 Blue        | Same as default branch    | ✅ Yes             |
| **behind**    | 🟢 Green       | Behind default branch     | ✅ Yes (if merged) |
| **ahead**     | 🟡 Yellow      | Has unique commits        | ⚠️ Carefully       |
| **diverged**  | 🔴 Red         | Has diverged from default | ⚠️ Review first    |
| **protected** | 🟡 Bold Yellow | Protected branch          | ❌ Cannot delete   |
| **fetching**  | ⚪ Dim Italic  | Status being retrieved    | ⏳ Wait            |
| **unknown**   | ⚪ Dim         | Cannot determine status   | ⚠️ Review first    |

### Ahead/Behind Indicators

Branches show commit count differences with arrows:

- `ahead ↑5` - 5 commits ahead of default branch
- `behind ↓3` - 3 commits behind default branch
- `diverged ↑2 ↓3` - 2 commits ahead, 3 commits behind

Additional indicators:

- **merged**: PR was merged
- **PR closed**: PR was closed without merging
- **protected**: Protected by regex pattern
- **default**: The repository's default branch

## Safety Features

1. **Protected Branches**: Branches matching the pattern `^(main|master|staging|dev|develop)$` cannot be selected or deleted
2. **Default Branch**: The repository's default branch cannot be deleted
3. **Confirmation Required**: Always asks for confirmation before deleting
4. **Visual Feedback**: Clear visual indicators show which branches are selected
5. **Error Handling**: Gracefully handles authentication issues and network errors

## Troubleshooting

### "gh CLI is not authenticated"

Run `gh auth login` and follow the prompts to authenticate.

### "Failed to get repo info"

Ensure you're in a Git repository with a GitHub remote:

```bash
git remote -v  # Should show a github.com URL
```

### Branches don't appear

- Check if you're in the correct repository
- Try refreshing with **R**
- Ensure you have internet connectivity

## Development

### Running Tests

```bash
python test_tui.py
```

### Demo Mode (without authentication)

```bash
python demo.py --demo
```

## Comparison with Shell Script

This TUI complements the existing `gh-branch-manager.sh` script:

| Feature            | TUI               | Shell Script                    |
| ------------------ | ----------------- | ------------------------------- |
| Interactive        | ✅ Yes            | ❌ No                           |
| Multi-select       | ✅ Yes            | ✅ Yes (via args)               |
| Filtering          | ✅ Real-time      | ❌ No                           |
| Sorting            | ✅ Multiple modes | ❌ No                           |
| Visual feedback    | ✅ Colors + UI    | ✅ Colors only                  |
| Confirmation       | ✅ Modal dialog   | ✅ Prompt                       |
| Auto-select merged | ✅ Yes            | ✅ Yes (--delete-merged-branch) |

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

See repository license.
