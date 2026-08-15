#!/usr/bin/env bash
#
# Export the Memory Palace machinery. MACHINERY - contains no vault content.
#
# Produces a bundle containing ONLY tooling: no notes, no identity, no project
# or session data. Intended for standing up a second instance (e.g. a work
# machine) that shares the system and shares no data.
#
# Design Principle #11: machinery is portable; content never leaves its machine.
#
# Usage:
#   bash Luna/System/export.sh --dry-run     # list what would be exported
#   bash Luna/System/export.sh               # build dist/luna-machinery-<ver>/
#   bash Luna/System/export.sh --tar         # also produce a .tar.gz
#   bash Luna/System/export.sh --force       # proceed despite a private-term hit
#
# The export set is an ALLOWLIST. Adding a new machinery file means adding it
# here explicitly. A denylist would fail open - a new content directory would
# silently ship.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

# A term shorter than this matches almost everything and produces noise.
# A scan that cries wolf gets ignored, which is worse than no scan.
MIN_TERM_LENGTH=3

DRY_RUN=0
MAKE_TAR=0
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --tar)     MAKE_TAR=1 ;;
        --force)   FORCE=1 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

# ---------------------------------------------------------------------------
# The allowlist. Everything exported is named here.
# ---------------------------------------------------------------------------
MACHINERY_FILES=(
    "CLAUDE.md"
    ".gitignore"
    ".luna-local.json.example"
    "Luna/Index.md"
    "Luna/System/vaultlib.py"
    "Luna/System/lint.py"
    "Luna/System/manifest.py"
    "Luna/System/covers.py"
    "Luna/System/export.sh"
    "Luna/System/hooks/pre-commit"
    "Luna/System/Schema.md"
    "Luna/System/SESSION_PROTOCOL.md"
    "Luna/Views/Projects.base"
    "Luna/Views/Health.base"
)

SKELETON_DIRS=(
    "Luna/Context"
    "Luna/Projects"
    "Luna/Sessions"
    "Luna/Archive"
    "Luna/System/hooks"
    "Luna/Views"
)

# NEVER exported:
#   Luna/Context/    Luna/Projects/    Luna/Sessions/    Luna/Archive/
#   Luna/Views/manifest.tsv     (real note paths and titles)
#   Luna/Views/registry.tsv     (rows are content; a header-only stub is emitted)
#   .luna-local.json            (absolute paths, private terms)

VERSION="$(python3 -c 'import sys; sys.path.insert(0, "Luna/System"); import vaultlib; print(vaultlib.MACHINERY_VERSION)' 2>/dev/null || echo "unknown")"
OUT_DIR="dist/luna-machinery-${VERSION}"

# ---------------------------------------------------------------------------
# Private-term scan
# ---------------------------------------------------------------------------
scan_private_terms() {
    local target_root="$1"
    local hits=0

    if [ ! -f ".luna-local.json" ]; then
        echo ""
        echo "  WARNING: no .luna-local.json - private-term scan SKIPPED."
        echo "  Copy .luna-local.json.example and fill in private_terms."
        echo ""
        return 0
    fi

    local parsed
    parsed="$(python3 - "$MIN_TERM_LENGTH" <<'PY'
import json, sys
min_len = int(sys.argv[1])
try:
    cfg = json.load(open(".luna-local.json"))
except Exception as exc:
    print("ERR\t%s" % exc)
    sys.exit(0)
for raw in cfg.get("private_terms", []):
    t = str(raw).strip()
    if not t:
        continue
    if len(t) < min_len:
        print("SHORT\t%s" % t)
    else:
        print("TERM\t%s" % t)
PY
)"

    if printf '%s\n' "$parsed" | grep -q '^ERR'; then
        echo "  ERROR: could not parse .luna-local.json:" >&2
        printf '%s\n' "$parsed" | sed -n 's/^ERR\t/      /p' >&2
        return 1
    fi

    local skipped
    skipped="$(printf '%s\n' "$parsed" | sed -n 's/^SHORT\t//p')"
    if [ -n "$skipped" ]; then
        echo "  Skipped (shorter than ${MIN_TERM_LENGTH} chars - would match everything):"
        printf '%s\n' "$skipped" | sed 's/^/      /'
    fi

    local terms
    terms="$(printf '%s\n' "$parsed" | sed -n 's/^TERM\t//p')"

    if [ -z "$terms" ]; then
        echo "  note: no usable private_terms - nothing checked."
        return 0
    fi

    while IFS= read -r term; do
        [ -z "$term" ] && continue
        if grep -rl --fixed-strings -- "$term" "$target_root" >/dev/null 2>&1; then
            echo "  LEAK: \"$term\" appears in:"
            grep -rl --fixed-strings -- "$term" "$target_root" | sed 's/^/      /'
            hits=$((hits + 1))
        fi
    done <<< "$terms"

    return $hits
}

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
echo ""
echo "Memory Palace machinery export"
echo "  version:  ${VERSION}"
echo "  repo:     ${REPO_ROOT}"
echo "  target:   ${OUT_DIR}"
echo ""
echo "Files to export:"

missing=0
for f in "${MACHINERY_FILES[@]}"; do
    if [ -f "$f" ]; then
        printf '  %s\n' "$f"
    else
        printf '  %s   [MISSING]\n' "$f"
        missing=$((missing + 1))
    fi
done

echo ""
echo "Empty directories to create:"
for d in "${SKELETON_DIRS[@]}"; do
    printf '  %s/\n' "$d"
done

echo ""
echo "Explicitly NOT exported: Luna/Context, Luna/Projects, Luna/Sessions,"
echo "Luna/Archive, Views/manifest.tsv, .luna-local.json"
echo ""

if [ "$missing" -gt 0 ]; then
    echo "WARNING: ${missing} allowlisted file(s) missing." >&2
fi

if [ "$DRY_RUN" -eq 1 ]; then
    echo "Dry run - nothing written."
    exit 0
fi

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

for d in "${SKELETON_DIRS[@]}"; do
    mkdir -p "$OUT_DIR/$d"
    : > "$OUT_DIR/$d/.gitkeep"
done

for f in "${MACHINERY_FILES[@]}"; do
    [ -f "$f" ] || continue
    mkdir -p "$OUT_DIR/$(dirname "$f")"
    cp "$f" "$OUT_DIR/$f"
done

head -n 1 "Luna/Views/registry.tsv" > "$OUT_DIR/Luna/Views/registry.tsv" 2>/dev/null \
    || printf 'id\tkind\troot_key\tmanifest\tdescription\n' > "$OUT_DIR/Luna/Views/registry.tsv"

chmod +x "$OUT_DIR/Luna/System/hooks/pre-commit" 2>/dev/null || true
chmod +x "$OUT_DIR/Luna/System/export.sh" 2>/dev/null || true

echo "Scanning bundle for private terms..."
set +e
scan_private_terms "$OUT_DIR"
leak_count=$?
set -e

if [ "$leak_count" -gt 0 ]; then
    echo ""
    echo "-------------------------------------------------------"
    echo "  ${leak_count} private term(s) found in the bundle."
    echo "  Machinery must not reference personal content."
    echo "  Edit the offending files, or re-run with --force if"
    echo "  you have reviewed each hit and accept it."
    echo "-------------------------------------------------------"
    if [ "$FORCE" -ne 1 ]; then
        rm -rf "$OUT_DIR"
        echo "  Bundle deleted. Nothing was exported."
        exit 1
    fi
    echo "  --force given: bundle kept despite hits."
fi

if [ "$MAKE_TAR" -eq 1 ]; then
    tar -czf "${OUT_DIR}.tar.gz" -C dist "$(basename "$OUT_DIR")"
    echo "  archive: ${OUT_DIR}.tar.gz"
fi

echo ""
echo "Exported to ${OUT_DIR}"
echo ""
echo "On the target machine:"
echo "  1. Copy the bundle to the new vault location"
echo "  2. git init && git add -A && git commit -m 'Memory Palace machinery ${VERSION}'"
echo "  3. git config core.hooksPath Luna/System/hooks"
echo "  4. cp .luna-local.json.example .luna-local.json   # then edit"
echo "  5. Create Luna/Context/CRITICAL_FACTS.md for THAT machine's identity"
echo "  6. python3 Luna/System/manifest.py"
echo ""
