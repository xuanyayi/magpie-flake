#!/usr/bin/env bash
set -euo pipefail

# Keep an unmerged dependency update when refreshing the release PR.
# If main has changed its lock since the PR branched, main takes precedence.
pending=refs/remotes/origin/automation/update-magpie
if git show-ref --verify --quiet "$pending" && ! git merge-base --is-ancestor "$pending" HEAD; then
  base=$(git merge-base HEAD "$pending")
  if git diff --quiet "$base" HEAD -- flake.lock; then
    git show "$pending:flake.lock" > flake.lock
  fi
fi
