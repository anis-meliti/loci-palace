#!/usr/bin/env bash
#
# Machinery leak audit. MACHINERY - contains no vault content.
#
# Answers one question: does any machinery file contain personal content?
#
# Machinery is portable - it gets copied to other machines and, if you
# contribute upstream, published. Content must never travel with it. This is
# the check to run BEFORE copying machinery anywhere or opening a pull request.
#
# Replaces the export half of the older export.sh. Distribution is now handled
# by the loci-palace package, which cannot carry content because it never had
# any. Auditing is the part that still needs doing, because you edit these
# files by hand and a leak arrives one careless sentence at a time.
#
# Usage:
#   bash <vault>/System/audit.sh              # audit this vault's machinery
#   bash <vault>/System/audit.sh --path DIR   # audit an arbitrary directory
#   bash <vault>/System/audit.sh --list       # show what would be audited
#
# Exit codes:  0 = clean   1 = leak found   2 = misconfigured

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

LOCAL_CONFIG=".loci-local.json"
MIN_TERM_LENGTH=3

TARGET=""
LIST_ONLY=0
while [ $# -gt 0 ]; do
    case "$1" in
        --path) TARGET="${2:-}"; shift 2 ;;
        --list) LIST_ONLY=1; shift ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

# Resolve the vault directory rather than assuming a name.
VAULT_DIR=$(python3 - <<'PY' 2>/dev/null
import glob, os, sys
for lib in glob.glob("*/System/vaultlib.py"):
    sys.path.insert(0, os.path.dirname(os.path.abspath(lib)))
    try:
        import vaultlib as V
        name = V.vault_dir(os.getcwd(), required=False)
        if name:
            print(name)
    except Exception:
        pass
    break
PY
)

if [ -z "$VAULT_DIR" ] && [ -z "$TARGET" ]; then
    echo "error: cannot locate the vault directory. Add .loci.json, or pass --path." >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# What counts as machinery. Content directories are deliberately absent:
# they are SUPPOSED to contain personal material and are never audited.
# ---------------------------------------------------------------------------
if [ -n "$TARGET" ]; then
    AUDIT_PATHS=("$TARGET")
else
    AUDIT_PATHS=(
        "${VAULT_DIR}/System"
        "${VAULT_DIR}/Index.md"
        "${VAULT_DIR}/Views/Projects.base"
        "${VAULT_DIR}/Views/Health.base"
        "CLAUDE.md"
        "AGENTS.md"
        "GEMINI.md"
        ".gitignore"
        "${LOCAL_CONFIG}.example"
    )
fi

collect_files() {
    for p in "${AUDIT_PATHS[@]}"; do
        [ -e "$p" ] || continue
        if [ -d "$p" ]; then
            find "$p" -type f ! -path '*/.git/*' ! -name '*.pyc' 2>/dev/null
        else
            echo "$p"
        fi
    done
}

echo ""
echo "Machinery leak audit"
[ -n "$TARGET" ] && echo "  target:  ${TARGET}" || echo "  vault:   ${VAULT_DIR}/"
echo ""

FILES="$(collect_files)"
FILE_COUNT="$(printf '%s\n' "$FILES" | grep -c . || true)"

if [ "$LIST_ONLY" -eq 1 ]; then
    echo "Files that would be audited (${FILE_COUNT}):"
    printf '%s\n' "$FILES" | sed 's/^/  /'
    echo ""
    echo "NOT audited (content by design):"
    echo "  ${VAULT_DIR}/Context  ${VAULT_DIR}/Projects  ${VAULT_DIR}/Sessions"
    echo "  ${VAULT_DIR}/Archive  ${VAULT_DIR}/Views/manifest.tsv"
    echo ""
    exit 0
fi

if [ "$FILE_COUNT" -eq 0 ]; then
    echo "  error: no machinery files found - is the vault directory correct?" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Terms
# ---------------------------------------------------------------------------
if [ ! -f "$LOCAL_CONFIG" ]; then
    echo "  Cannot audit: no ${LOCAL_CONFIG}."
    echo "  Copy ${LOCAL_CONFIG}.example and fill in private_terms."
    echo ""
    echo "  Skipping is NOT passing. Nothing was checked."
    exit 2
fi

PARSED="$(python3 - "$MIN_TERM_LENGTH" <<'PY'
import json, sys
min_len = int(sys.argv[1])
try:
    cfg = json.load(open(".loci-local.json"))
except Exception as exc:
    print("ERR\t%s" % exc); sys.exit(0)
for raw in cfg.get("private_terms", []):
    t = str(raw).strip()
    if not t:
        continue
    print(("SHORT\t%s" if len(t) < min_len else "TERM\t%s") % t)
PY
)"

if printf '%s\n' "$PARSED" | grep -q '^ERR'; then
    echo "  error: could not parse ${LOCAL_CONFIG}:" >&2
    printf '%s\n' "$PARSED" | sed -n 's/^ERR\t/    /p' >&2
    exit 2
fi

SKIPPED="$(printf '%s\n' "$PARSED" | sed -n 's/^SHORT\t//p')"
TERMS="$(printf '%s\n' "$PARSED" | sed -n 's/^TERM\t//p')"
TERM_COUNT="$(printf '%s\n' "$TERMS" | grep -c . || true)"

if [ -n "$SKIPPED" ]; then
    echo "  Skipped (shorter than ${MIN_TERM_LENGTH} chars - would match everything):"
    printf '%s\n' "$SKIPPED" | sed 's/^/    /'
    echo ""
fi

if [ "$TERM_COUNT" -eq 0 ]; then
    echo "  No usable private_terms. Nothing was checked - this is not a pass."
    exit 2
fi

# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------
echo "Scanning ${FILE_COUNT} machinery file(s) for ${TERM_COUNT} private term(s)..."
echo ""

HITS=0
while IFS= read -r term; do
    [ -z "$term" ] && continue
    matches="$(printf '%s\n' "$FILES" | tr '\n' '\0' \
               | xargs -0 grep -l --fixed-strings -- "$term" 2>/dev/null)"
    if [ -n "$matches" ]; then
        echo "  LEAK: \"$term\""
        printf '%s\n' "$matches" | sed 's/^/        /'
        HITS=$((HITS + 1))
    fi
done <<< "$TERMS"

echo "-------------------------------------------------------"
if [ "$HITS" -gt 0 ]; then
    echo "  ${HITS} private term(s) found in machinery."
    echo "  Machinery must use generic language. Rewrite the offending"
    echo "  lines before copying this anywhere or contributing upstream."
    echo "-------------------------------------------------------"
    exit 1
fi
echo "  Clean: ${FILE_COUNT} files, ${TERM_COUNT} terms, 0 leaks."
echo ""
echo "  Note: this is a denylist over known strings. It cannot catch a"
echo "  description that identifies you without naming you. The habit of"
echo "  writing machinery generically is the real protection."
echo "-------------------------------------------------------"
exit 0
