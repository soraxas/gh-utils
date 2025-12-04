# Utils for `gh`

- `gh-branch-manager.sh`: helps you to quickly view remote branch status, and delete branches (e.g. diverged, closed remote branches)

```sh
$ gh-branch-manager.sh
Dry run (no branches will be deleted).
Re-run with --no-dry-run to actually delete branches.
Repo: soraxas/gh-utils
Default branch: master
Protected regex: ^(main|master|staging|dev|develop)$

Status mode (lists ALL remote branches with compare status; protected branches are marked)

Branches:
  feat/add-integration-and-plugins (diverged)
  dev (protected)
  develop (protected)
  feat/api-integration (diverged, merged)
  copilot/sub-pr-38-again (diverged, PR closed)
  copilot/sub-pr-38-another-one (diverged, merged)
  copilot/sub-pr-38 (diverged, PR closed)
  copilot/sub-pr-38-yet-again (diverged, merged)
  feature/session-recording-refactor (diverged)
  main (protected)
  staging (protected)

Tip: add --delete-merged-branch to delete branches shown above (excludes protected; still respects --no-dry-run).
```
