#!/usr/bin/env bash
#
# Stage everything and commit, with a confirmation gate.
# MACHINERY - contains no vault content.
#
# The pre-commit hook handles lint and manifest regeneration, so this only
# has to answer one question: does the operator want THESE changes committed?
#
# Automate what is compiled; never automate what is chosen.
# The manifest is compiled - the hook regenerates it silently.
# The contents of a commit are chosen - hence the prompt.
#
# Usage:
#   bash Luna/System/save.sh "commit message"
#   bash Luna/System/save.sh "message" --yes     # skip the prompt
#   bash Luna/System/save.sh --status            # show pending changes, exit

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "error: not inside a git repository" >&2
    exit 1
}
cd "$REPO_ROOT"

ASSUME_YES=0
STATUS_ONLY=0
MESSAGE=""

for arg in "$@"; do
    case "$arg" in
        --yes|-y)  ASSUME_YES=1 ;;
        --status)  STATUS_ONLY=1 ;;
        -*)        echo "unknown option: $arg" >&2; exit 2 ;;
        *)         [ -z "$MESSAGE" ] && MESSAGE="$arg" ;;
    esac
done

if [ -z "$(git status --porcelain)" ]; then
    echo "Nothing to commit - working tree is clean."
    exit 0
fi

echo ""
echo "Pending changes:"
git status --short | sed 's/^/  /'

added=$(git status --porcelain | grep -c '^??' || true)
modified=$(git status --porcelain | grep -c '^.M\|^M' || true)
deleted=$(git status --porcelain | grep -c '^.D\|^D' || true)
echo ""
echo "  ${added} new · ${modified} modified · ${deleted} deleted"
echo ""

if [ "$STATUS_ONLY" -eq 1 ]; then
    exit 0
fi

if [ -z "$MESSAGE" ]; then
    echo "error: no commit message given" >&2
    echo "  usage: bash Luna/System/save.sh \"your message\"" >&2
    exit 2
fi

echo "Message: ${MESSAGE}"
echo ""

if [ "$ASSUME_YES" -ne 1 ]; then
    printf "Stage all and commit? [y/N] "
    read -r reply </dev/tty
    case "$reply" in
        y|Y|yes|YES) ;;
        *) echo "Aborted. Nothing staged, nothing committed."; exit 0 ;;
    esac
fi

git add -A
git commit -m "$MESSAGE"
