#!/usr/bin/env bash
#
# Preflight environment check. MACHINERY - contains no vault content.
#
# Verifies the full runtime stack BEFORE scaffolding, so a fresh install cannot
# look fine while silently not working.
#
# Architecture checked (decided 2026-08-09, superseding the never-implemented
# filesystem-MCP decision of 2026-07-31):
#
#     Claude client -> palace-mcp (uv + fastmcp)
#                   -> HTTP :27123
#                   -> Obsidian Local REST API plugin
#                   -> vault on disk
#
# Consequence: Obsidian must be INSTALLED AND RUNNING with the Local REST API
# plugin enabled. This is not a headless setup. Every dependency below is
# required because the chain breaks without any one of them.
#
# Usage:
#   bash Luna/System/preflight.sh
#   bash Luna/System/preflight.sh --vault /path/to/target
#
# Exit codes:  0 = ready   1 = blocked

set -uo pipefail

VAULT_TARGET=""
while [ $# -gt 0 ]; do
    case "$1" in
        --vault) VAULT_TARGET="${2:-}"; shift 2 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

FAILURES=0
WARNINGS=0

ok()   { printf '  [ OK ]  %s\n' "$1"; }
warn() { printf '  [WARN]  %s\n' "$1"; [ -n "${2:-}" ] && printf '          %s\n' "$2"; WARNINGS=$((WARNINGS+1)); }
bad()  { printf '  [FAIL]  %s\n' "$1"; [ -n "${2:-}" ] && printf '          %s\n' "$2"; FAILURES=$((FAILURES+1)); }

case "$(uname -s)" in
    Darwin) PLATFORM="macos" ;;
    Linux)  PLATFORM="linux" ;;
    *)      PLATFORM="other" ;;
esac

if [ "$PLATFORM" = "macos" ]; then
    MCP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
else
    MCP_CONFIG="$HOME/.config/Claude/claude_desktop_config.json"
fi

echo ""
echo "Memory Palace preflight"
echo "  platform: ${PLATFORM}"
echo "  stack:    palace-mcp -> Local REST API -> Obsidian"
echo ""

# --- Base toolchain ---------------------------------------------------------
echo "Toolchain:"

if command -v python3 >/dev/null 2>&1 \
   && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    ok "python3 $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
else
    bad "python3 3.9+ not found" "All vault tooling depends on it."
fi

if command -v git >/dev/null 2>&1; then
    ok "git $(git --version | awk '{print $3}')"
else
    bad "git not found" "Needed for versioning and the pre-commit hook."
fi

if command -v uv >/dev/null 2>&1; then
    ok "uv $(uv --version 2>/dev/null | awk '{print $2}')"
else
    bad "uv not found" "palace-mcp runs via uv. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# --- Agent host -------------------------------------------------------------
echo ""
echo "Agent host (at least one required):"

HOST_FOUND=0
if command -v claude >/dev/null 2>&1; then ok "Claude Code CLI"; HOST_FOUND=1
else warn "Claude Code CLI not found" "npm install -g @anthropic-ai/claude-code"; fi

if [ "$PLATFORM" = "macos" ] && [ -d "/Applications/Claude.app" ]; then
    ok "Claude Desktop"; HOST_FOUND=1
elif [ "$PLATFORM" = "macos" ]; then
    warn "Claude Desktop not found in /Applications"
fi

[ "$HOST_FOUND" -eq 0 ] && bad "no agent host found" "Nothing can read the vault without one."

# --- Obsidian: REQUIRED on this architecture --------------------------------
echo ""
echo "Obsidian (required - the REST API lives inside the app):"

OBSIDIAN_INSTALLED=0
if { [ "$PLATFORM" = "macos" ] && [ -d "/Applications/Obsidian.app" ]; } \
   || command -v obsidian >/dev/null 2>&1 \
   || [ -d "$HOME/.var/app/md.obsidian.Obsidian" ]; then
    OBSIDIAN_INSTALLED=1
    ok "Obsidian installed"
else
    bad "Obsidian not installed" "Required: the Local REST API plugin runs inside the app."
fi

if [ "$OBSIDIAN_INSTALLED" -eq 1 ]; then
    if pgrep -x "Obsidian" >/dev/null 2>&1 || pgrep -f "Obsidian" >/dev/null 2>&1; then
        ok "Obsidian is running"
    else
        bad "Obsidian is NOT running" "The REST API only responds while the app is open."
    fi
fi

# --- Local REST API ---------------------------------------------------------
echo ""
echo "Local REST API:"

OBSIDIAN_PORT="${OBSIDIAN_PORT:-27123}"
API_KEY=""

if [ -f "$MCP_CONFIG" ] && command -v python3 >/dev/null 2>&1; then
    API_KEY="$(python3 - "$MCP_CONFIG" <<'PY'
import json, sys
try:
    cfg = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
for spec in (cfg.get("mcpServers", {}) or {}).values():
    for k, v in ((spec or {}).get("env", {}) or {}).items():
        if "API_KEY" in k.upper():
            print(v); sys.exit(0)
PY
)"
fi

if [ -n "$API_KEY" ]; then
    ok "API key found in MCP config"
else
    bad "no OBSIDIAN_API_KEY in MCP config" "Obsidian > Settings > Local REST API > copy the key into the server's env block."
fi

if command -v curl >/dev/null 2>&1; then
    if curl -s -f -m 5 "http://127.0.0.1:${OBSIDIAN_PORT}/" >/dev/null 2>&1; then
        ok "REST API responding on port ${OBSIDIAN_PORT}"

        # The check that proves the mechanism, not just the config.
        if [ -n "$API_KEY" ]; then
            code="$(curl -s -o /dev/null -w '%{http_code}' -m 5 \
                    -H "Authorization: Bearer ${API_KEY}" \
                    "http://127.0.0.1:${OBSIDIAN_PORT}/vault/" 2>/dev/null)"
            case "$code" in
                200) ok "authenticated vault read succeeded (end-to-end)" ;;
                401|403) bad "API key rejected (HTTP ${code})" "Key in MCP config does not match the plugin." ;;
                *) warn "unexpected response from /vault/ (HTTP ${code})" ;;
            esac
        fi
    else
        bad "nothing responding on port ${OBSIDIAN_PORT}" "Enable the Local REST API plugin in Obsidian, or set OBSIDIAN_PORT."
    fi
else
    warn "curl not found - cannot verify the REST API"
fi

# --- palace-mcp -------------------------------------------------------------
echo ""
echo "palace-mcp server:"

if [ -f "$MCP_CONFIG" ] && command -v python3 >/dev/null 2>&1; then
    python3 - "$MCP_CONFIG" <<'PY'
import json, os, sys
try:
    cfg = json.load(open(sys.argv[1]))
except Exception as exc:
    print("  [WARN]  MCP config unparseable: %s" % exc); sys.exit(0)

servers = cfg.get("mcpServers", {}) or {}
if not servers:
    print("  [FAIL]  no mcpServers configured"); sys.exit(0)

for name, spec in servers.items():
    spec = spec or {}
    paths = [os.path.expanduser(str(a)) for a in (spec.get("args") or [])
             if str(a).startswith(("/", "~"))]
    if paths:
        for p in paths:
            exists = os.path.isdir(p) or os.path.isfile(p)
            print("  [%s]  %s -> %s%s" % (" OK " if exists else "FAIL", name, p,
                                          "" if exists else "   (missing)"))
    else:
        print("  [ OK ]  %s (command: %s)" % (name, spec.get("command", "?")))
PY
else
    bad "no MCP config found" "Expected at: ${MCP_CONFIG}"
fi

# --- Target directory -------------------------------------------------------
if [ -n "$VAULT_TARGET" ]; then
    echo ""
    echo "Target vault:"
    EXPANDED="${VAULT_TARGET/#\~/$HOME}"
    ABS="$(cd "$EXPANDED" 2>/dev/null && pwd || echo "$EXPANDED")"
    if [ -d "$EXPANDED/Luna" ]; then
        warn "a vault already exists here" "$ABS/Luna - init would need --force"
    elif [ -e "$EXPANDED" ] && [ -n "$(ls -A "$EXPANDED" 2>/dev/null)" ]; then
        warn "directory exists and is not empty" "$ABS"
    elif [ -e "$EXPANDED" ]; then
        ok "empty directory ready: $ABS"
    else
        [ -w "$(dirname "$EXPANDED")" ] && ok "will be created: $ABS" \
                                        || bad "parent not writable" "$(dirname "$EXPANDED")"
    fi
    echo ""
    echo "  Note: this vault must be the one Obsidian currently has OPEN."
    echo "  The REST API serves the active vault, not an arbitrary path."
fi

# --- Summary ----------------------------------------------------------------
echo ""
echo "-------------------------------------------------------"
if [ "$FAILURES" -gt 0 ]; then
    echo "  BLOCKED: ${FAILURES} failure(s), ${WARNINGS} warning(s)."
    echo "-------------------------------------------------------"
    exit 1
fi
echo "  READY: 0 failures, ${WARNINGS} warning(s)."
echo "-------------------------------------------------------"
exit 0
