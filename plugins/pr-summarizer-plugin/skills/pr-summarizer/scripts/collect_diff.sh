#!/usr/bin/env bash
# collect_diff.sh — Collects git diff data for PR description drafting
# Usage: collect_diff.sh <repo_path> <feature_branch> <base_branch>
# Outputs structured text to stdout; progress messages go to stderr

set -euo pipefail

REPO_PATH="$1"
FEATURE_BRANCH="$2"
BASE_BRANCH="$3"
MAX_DIFF_BYTES=150000
MAX_FILE_LINES=200

cd "$REPO_PATH" || { echo "ERROR: Cannot cd to '$REPO_PATH'" >&2; exit 1; }

# Confirm it's a git repo
git rev-parse --show-toplevel > /dev/null 2>&1 || { echo "ERROR: '$REPO_PATH' is not a git repository." >&2; exit 1; }

# Validate branches
for branch in "$FEATURE_BRANCH" "$BASE_BRANCH"; do
  if ! git rev-parse --verify "$branch" &>/dev/null; then
    echo "ERROR: Branch '$branch' not found." >&2
    echo "Available branches:" >&2
    git branch -a >&2
    exit 1
  fi
done

# Merge base
MERGE_BASE=$(git merge-base "$BASE_BRANCH" "$FEATURE_BRANCH" 2>/dev/null || echo "")
if [[ -z "$MERGE_BASE" ]]; then
  echo "ERROR: Cannot find merge base between '$BASE_BRANCH' and '$FEATURE_BRANCH'." >&2
  exit 1
fi

COMMITS_AHEAD=$(git rev-list --count "$MERGE_BASE".."$FEATURE_BRANCH")
if [[ "$COMMITS_AHEAD" -eq 0 ]]; then
  echo "WARNING: '$FEATURE_BRANCH' has no commits ahead of '$BASE_BRANCH'. Nothing to summarize." >&2
  exit 0
fi

# ── File change summary ──────────────────────────────────────────────────────
echo "=== FILE CHANGES ==="
git diff --stat "$MERGE_BASE".."$FEATURE_BRANCH"
echo ""

echo "=== NAME STATUS ==="
git diff --name-status "$MERGE_BASE".."$FEATURE_BRANCH"
echo ""

# ── Commit messages ──────────────────────────────────────────────────────────
echo "=== COMMITS ($COMMITS_AHEAD commit(s)) ==="
git log --oneline --no-merges "$MERGE_BASE".."$FEATURE_BRANCH"
echo ""

# ── Full diff (excluding noise) ──────────────────────────────────────────────
FULL_DIFF=$(git diff "$MERGE_BASE".."$FEATURE_BRANCH" \
  -- ':!*.lock' ':!package-lock.json' ':!yarn.lock' \
     ':!*.min.js' ':!*.min.css' \
     ':!dist/' ':!build/' ':!*.snap' 2>/dev/null)
DIFF_SIZE=${#FULL_DIFF}

echo "=== DIFF ==="
if (( DIFF_SIZE <= MAX_DIFF_BYTES )); then
  echo "$FULL_DIFF"
else
  echo "[NOTE: Diff is large (${DIFF_SIZE} bytes). Truncated to ${MAX_FILE_LINES} lines per file.]"
  echo ""
  while IFS= read -r filepath; do
    echo "--- $filepath ---"
    git diff "$MERGE_BASE".."$FEATURE_BRANCH" -- "$filepath" | head -n "$MAX_FILE_LINES"
    echo ""
  done < <(git diff --name-only "$MERGE_BASE".."$FEATURE_BRANCH")
fi
