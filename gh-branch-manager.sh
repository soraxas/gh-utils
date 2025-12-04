#!/usr/bin/env sh
set -eu

DEFAULT_PROTECTED_REGEX='^(main|master|staging|dev|develop)$'

usage() {
  cat <<EOF
Delete GitHub branches via gh, safely.

Modes:
  1) No branch args: STATUS mode (default). List all remote branches with (status)
     vs default branch, and annotate protected + merged.
     If --delete-merged-branch is also given, it will delete branches listed
     (excluding protected) and still respects --no-dry-run.
  2) Branch args given: delete exactly those branches (with confirmation prompt).
     --delete-merged-branch cannot be used with branch args.

Requires:
  - gh (GitHub CLI) authenticated
  - sort, grep

Usage:
  gh-branch-delete.sh [--protected REGEX] [--delete-merged-branch] [--no-dry-run] [--yes] [branch...]
  gh-branch-delete.sh -h|--help

Options:
  --protected REGEX           Regex of branch names to NEVER delete.
                              Default: '$DEFAULT_PROTECTED_REGEX'
  --delete-merged-branch     Enable deletion in STATUS mode (no positional args).
  --no-dry-run               Actually delete. Without this, script only prints actions.
  --yes                      Skip confirmation prompt in "branch args" mode.
  -v, --verbose              Print underlying gh errors on failures.
  -h, --help                 Show this help message.
EOF
}

protected="$DEFAULT_PROTECTED_REGEX"
dry_run=1
assume_yes=0
verbose=0
delete_merged=0

# --- parse flags (leave remaining args as branch names) ---
while [ $# -gt 0 ]; do
  case "$1" in
  --protected)
    shift
    [ $# -gt 0 ] || {
      echo "Error: --protected requires a value" >&2
      usage >&2
      exit 2
    }
    protected=$1
    ;;
  --protected=*)
    protected=${1#*=}
    ;;
  --delete-merged-branch)
    delete_merged=1
    ;;
  --no-dry-run)
    dry_run=0
    ;;
  --yes | -y)
    assume_yes=1
    ;;
  -v | --verbose)
    verbose=1
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  --)
    shift
    break
    ;;
  -*)
    echo "Error: unknown option: $1" >&2
    usage >&2
    exit 2
    ;;
  *) break ;;
  esac
  shift
done

# remaining args (if any) are explicit branch names
branches_args="$*"

if [ "$delete_merged" -eq 1 ] && [ -n "${branches_args:-}" ]; then
  echo "Error: --delete-merged-branch cannot be used with explicit branch arguments." >&2
  usage >&2
  exit 2
fi

# --- colors (auto-disable if not a TTY, or if NO_COLOR is set) ---
if [ -t 1 ] && [ "${NO_COLOR:-}" = "" ]; then
  RED="$(printf '\033[31m')"
  GREEN="$(printf '\033[32m')"
  YELLOW="$(printf '\033[33m')"
  BLUE="$(printf '\033[34m')"
  DIM="$(printf '\033[2m')"
  BOLD="$(printf '\033[1m')"
  RESET="$(printf '\033[0m')"
else
  RED=""
  GREEN=""
  YELLOW=""
  BLUE=""
  DIM=""
  BOLD=""
  RESET=""
fi

REPO_FULL="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
DEFAULT_BRANCH="$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)"

banner() {
  if [ "$dry_run" -eq 1 ]; then
    echo "${YELLOW}${BOLD}Dry run${RESET}${YELLOW} (no branches will be deleted).${RESET}"
    echo "${DIM}Re-run with ${RESET}${BOLD}--no-dry-run${RESET}${DIM} to actually delete branches.${RESET}"
  else
    echo "${RED}${BOLD}LIVE RUN${RESET}${RED}: branches will be deleted.${RESET}"
  fi
  echo "${DIM}Repo:${RESET} ${BOLD}$REPO_FULL${RESET}"
  echo "${DIM}Default branch:${RESET} ${BOLD}$DEFAULT_BRANCH${RESET}"
  echo "${DIM}Protected regex:${RESET} ${BOLD}$protected${RESET}"
  echo
}

urlenc() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1"
  else
    python -c 'import sys; try: import urllib.parse as u; except ImportError: import urllib as u; print(u.quote(sys.argv[1], safe=""))' "$1"
  fi
}

delete_branch() {
  b="$1"
  if [ "$dry_run" -eq 1 ]; then
    echo "  ${GREEN}WOULD DELETE${RESET} $b"
    return 0
  fi

  echo "  ${RED}DELETE${RESET} $b"

  err_file="${TMPDIR:-/tmp}/gh-branch-delete.$$.$(printf '%s' "$b" | tr '/ ' '__').err"
  if gh api -X DELETE "repos/$REPO_FULL/git/refs/heads/$b" >/dev/null 2>"$err_file"; then
    rm -f "$err_file"
    return 0
  fi

  # "Reference does not exist" is normal if it was already deleted; make it non-scary.
  if grep -q "Reference does not exist" "$err_file" 2>/dev/null; then
    echo "  ${YELLOW}SKIP${RESET} ${DIM}already deleted: $b${RESET}" >&2
  else
    echo "  ${YELLOW}WARN${RESET} ${DIM}failed to delete (protected by server rules or no permission): $b${RESET}" >&2
  fi

  if [ "$verbose" -eq 1 ] && [ -s "$err_file" ]; then
    echo "  ${DIM}--- gh error output ---${RESET}" >&2
    sed 's/^/  /' "$err_file" >&2
    echo "  ${DIM}-----------------------${RESET}" >&2
  fi
  rm -f "$err_file"
}

confirm() {
  prompt="$1"
  if [ "$assume_yes" -eq 1 ]; then
    return 0
  fi
  printf "%s" "$prompt" >&2
  IFS= read -r ans || ans=""
  case "$ans" in y | Y | yes | YES) return 0 ;; *) return 1 ;; esac
}

# --- MODE 2: explicit branches provided ---
if [ -n "${branches_args:-}" ]; then
  # explicit delete mode ignores dry-run (as requested previously)
  dry_run=0
  banner
  echo "${BLUE}${BOLD}Direct delete mode${RESET} ${DIM}(you specified branches)${RESET}"

  # normalize: one per line, drop empties, unique
  branch_list="$(printf '%s\n' "$@" | sed '/^$/d' | sort -u)"

  protected_list="$(printf '%s\n' "$branch_list" | grep -E "$protected" || true)"
  deletable_list="$(printf '%s\n' "$branch_list" | grep -E -v "$protected" || true)"

  if [ -n "${protected_list:-}" ]; then
    echo
    echo "${YELLOW}${BOLD}Skipped because protected:${RESET}"
    printf '%s\n' "$protected_list" | while IFS= read -r b; do
      [ -n "$b" ] || continue
      echo "  ${YELLOW}SKIP${RESET} ${DIM}$b${RESET}"
    done
  fi

  if [ -z "${deletable_list:-}" ]; then
    echo
    echo "${DIM}Nothing left to delete after protected filtering.${RESET}"
    exit 0
  fi

  echo
  echo "${GREEN}${BOLD}Targets:${RESET}"
  printf '%s\n' "$deletable_list" | while IFS= read -r b; do
    [ -n "$b" ] || continue
    echo "  ${RED}DELETE${RESET} $b"
  done

  echo
  if confirm "${BOLD}Proceed to delete the above branch(es)?${RESET} ${DIM}(y/N): ${RESET}"; then
    echo
    echo "${GREEN}${BOLD}Executing:${RESET}"
    printf '%s\n' "$deletable_list" | while IFS= read -r b; do
      [ -n "$b" ] || continue
      delete_branch "$b"
    done
  else
    echo
    echo "${YELLOW}Cancelled.${RESET}"
  fi

  exit 0
fi

# --- MODE 1: STATUS mode (default) ---
banner
echo "${BLUE}${BOLD}Status mode${RESET} ${DIM}(lists ALL remote branches with compare status; protected branches are marked)${RESET}"
echo

tmp_merged="${TMPDIR:-/tmp}/merged_heads.$$"
tmp_closed="${TMPDIR:-/tmp}/closed_heads.$$"
tmp_remote="${TMPDIR:-/tmp}/remote_branches.$$"
tmp_report="${TMPDIR:-/tmp}/report.$$"
trap 'rm -f "$tmp_merged" "$tmp_closed" "$tmp_remote" "$tmp_report"' EXIT

# merged PR head branch names (unique)
gh pr list --state merged --limit 200 \
  --json headRefName \
  --jq '.[].headRefName' |
  sort -u >"$tmp_merged"

# closed (not merged) PR head branch names (unique)
gh pr list --state closed --limit 200 \
  --json headRefName,mergedAt \
  --jq '.[] | select(.mergedAt == null) | .headRefName' |
  sort -u >"$tmp_closed"

# all remote branches in this repo
gh api "repos/$REPO_FULL/branches?per_page=100" --paginate \
  --jq '.[].name' |
  sort -u >"$tmp_remote"

: >"$tmp_report"
while IFS= read -r b; do
  [ -n "$b" ] || continue

  # protected = never delete (safest to KEEP)
  if printf '%s\n' "$b" | grep -Eq "$protected"; then
    # mark with a tag we can color later
    printf '%s\t%s\t0\t0\n' "$b" "protected" >>"$tmp_report"
    continue
  fi

  merged=0
  if grep -Fqx "$b" "$tmp_merged"; then
    merged=1
  fi

  closed=0
  if grep -Fqx "$b" "$tmp_closed"; then
    closed=1
  fi

  enc="$(urlenc "$DEFAULT_BRANCH...$b")"
  status="$(gh api "repos/$REPO_FULL/compare/$enc" --jq '.status' 2>/dev/null || printf 'unknown')"

  # Store raw fields (not colored) so coloring is done at print time
  # Fields: name<TAB>status<TAB>merged(0/1)<TAB>closed(0/1)
  printf '%s\t%s\t%s\t%s\n' "$b" "$status" "$merged" "$closed" >>"$tmp_report"
done <"$tmp_remote"

echo "${BLUE}${BOLD}Branches:${RESET}"
sort -u "$tmp_report" | while IFS="$(printf '\t')" read -r name status merged closed; do
  [ -n "$name" ] || continue

  # protected branches are kept; ignore other metadata
  if [ "${status:-}" = "protected" ]; then
    # KEEP / never delete
    echo "  $name ${BOLD}${YELLOW}(protected)${RESET}"
    continue
  fi

  m=""
  [ "${merged:-0}" = "1" ] && m=", merged"
  c=""
  [ "${closed:-0}" = "1" ] && c=", PR closed"

  # Color by deletion safety:
  # - behind      => safest to delete (default is ahead; branch has no unique commits)
  # - identical   => safe-ish (usually means same tip as default)
  # - ahead       => unsafe (branch has commits not in default)
  # - diverged    => unsafe (both have unique commits)
  # - unknown     => caution
  case "$status" in
  behind)
    # safest delete
    echo "  $name ${GREEN}(behind$m$c)${RESET}"
    ;;
  identical)
    # usually safe, but less strong than behind
    echo "  $name ${BLUE}(identical$m$c)${RESET}"
    ;;
  ahead)
    # do NOT delete lightly
    echo "  $name ${RED}(ahead$m$c)${RESET}"
    ;;
  diverged)
    # do NOT delete lightly
    echo "  $name ${RED}(diverged$m$c)${RESET}"
    ;;
  *)
    # unknown / error
    echo "  $name ${YELLOW}(unknown$m$c)${RESET}"
    ;;
  esac
done
echo

if [ "$delete_merged" -ne 1 ]; then
  echo "${DIM}Tip:${RESET} add ${BOLD}--delete-merged-branch${RESET} to delete branches shown above (excludes protected; still respects --no-dry-run)."
  exit 0
fi

# delete mode from STATUS list: exclude protected and exclude default branch
branches_to_delete="$(
  awk -F'\t' '
    $2 != "protected" { print $1 }
  ' "$tmp_report" |
    grep -E -v "^${DEFAULT_BRANCH}$" |
    sort -u
)"

if [ -z "${branches_to_delete:-}" ]; then
  echo "${DIM}Nothing to delete after filtering protected/default.${RESET}"
  exit 0
fi

echo "${GREEN}${BOLD}Delete mode (from status list):${RESET}"
if [ "$dry_run" -eq 1 ]; then
  echo "${YELLOW}${BOLD}Dry run${RESET}${YELLOW}: showing what would be deleted.${RESET}"
else
  echo "${RED}${BOLD}LIVE RUN${RESET}${RED}: deleting branches now.${RESET}"
fi
echo

printf '%s\n' "$branches_to_delete" | while IFS= read -r b; do
  [ -n "$b" ] || continue
  delete_branch "$b"
done
