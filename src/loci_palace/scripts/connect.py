#!/usr/bin/env python3
"""
Connect assistant clients to this vault. MACHINERY - contains no vault content.

Writes a marked block into the global instructions file (~/.claude/CLAUDE.md)
so that CLI and editor clients know the vault exists and how to route to it,
from any directory - or from none at all.

WHAT THIS DOES NOT DO
---------------------
It does not register an MCP server. That is deliberate:

  - the MCP server is a separate project, not part of this package
  - different users run different servers (filesystem, REST-wrapper, custom)
  - registration needs credentials, and a scaffolding tool should not handle
    secrets

It prints the guidance instead. Reachability is yours to configure; routing
instructions are what this automates.

SAFETY
------
The global instructions file usually already contains the user's own content.
This writes ONLY between sentinel markers and leaves everything else byte for
byte intact - the same rule the vault applies to generated blocks.

Dry run is the default. Nothing is written without --apply.

Usage:
    python3 <vault>/System/connect.py            # show what would change
    python3 <vault>/System/connect.py --apply    # write the block
    python3 <vault>/System/connect.py --remove   # remove the block
    python3 <vault>/System/connect.py --global-file PATH

No dependencies. Python 3.9+.
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vaultlib as V  # noqa: E402

BEGIN = "<!-- loci:begin - managed by connect.py, edit outside these markers -->"
END = "<!-- loci:end -->"

DEFAULT_GLOBAL = os.path.expanduser("~/.claude/CLAUDE.md")


def build_block(vault_abs, vault_dir):
    return f"""{BEGIN}
## Memory vault

Persistent memory for this user lives in a vault at:

    {vault_abs}

Reach it with the vault MCP tools (read/write/search/list). Use those tools
rather than the filesystem: the vault is usually not the working directory,
and may not be reachable as a path at all.

**Finding things.** Read `{vault_dir}/Views/manifest.tsv` and match the question
against the `covers` column, then open that one note. Do not search the vault
for a file whose path the manifest already gives you.

**Identity.** `{vault_dir}/Context/CRITICAL_FACTS.md` holds who this user is,
their constraints and preferences. Read it when a question depends on personal
context. It is not preloaded, by design.

**These phrasings mean "consult the vault", not "store a new fact":**
"remember X", "what do you know about X", "where are we on X",
"why did we decide X", "continue X", "what's the status of X".

**Before writing.** Read `{vault_dir}/System/Schema.md`. It is binding.
Never append to `{vault_dir}/Context/`, `{vault_dir}/Index.md`, or
`{vault_dir}/System/` - those are overwrite-only. After adding or renaming a
note, regenerate the manifest.

**Do not use native memory features.** This vault is the only memory store.
A second store that is invisible to the other clients defeats the purpose.
{END}"""


def read_file(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def splice(existing, block):
    """Replace an existing marked block, or append one. Never touches the rest."""
    if existing is None:
        return block + "\n", "created"

    if BEGIN in existing and END in existing:
        head = existing.split(BEGIN, 1)[0]
        tail = existing.split(END, 1)[1]
        return head + block + tail, "updated"

    if BEGIN in existing or END in existing:
        return None, "corrupt"

    sep = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    return existing + sep + block + "\n", "appended"


def remove_block(existing):
    if existing is None or BEGIN not in existing:
        return None, "absent"
    if END not in existing:
        return None, "corrupt"
    head = existing.split(BEGIN, 1)[0]
    tail = existing.split(END, 1)[1]
    return (head.rstrip("\n") + "\n" + tail.lstrip("\n")), "removed"


def detect_clients():
    """Report which clients are present. Informational only."""
    found = []
    if shutil.which("claude"):
        found.append("Claude Code CLI")
    if os.path.isdir("/Applications/Claude.app"):
        found.append("Claude Desktop")
    for name, path in (
        ("VS Code", "~/.vscode/extensions"),
        ("Cursor", "~/.cursor/extensions"),
    ):
        d = os.path.expanduser(path)
        if os.path.isdir(d):
            try:
                if any("claude" in e.lower() for e in os.listdir(d)):
                    found.append(f"{name} (Claude extension)")
            except OSError:
                pass
    return found


def main():
    apply_ = "--apply" in sys.argv
    remove = "--remove" in sys.argv

    target = DEFAULT_GLOBAL
    if "--global-file" in sys.argv:
        i = sys.argv.index("--global-file")
        if i + 1 < len(sys.argv):
            target = os.path.expanduser(sys.argv[i + 1])

    repo_root = V.find_repo_root()
    vault_dir = V.vault_dir(repo_root)
    vault_abs = os.path.abspath(repo_root)

    print()
    print("Connect clients to this vault")
    print(f"  vault:  {vault_abs}  (folder: {vault_dir}/)")
    print(f"  global: {target}")
    print()

    clients = detect_clients()
    if clients:
        print("Clients detected on this machine:")
        for c in clients:
            print(f"  - {c}")
    else:
        print("  No Claude clients detected. The block can still be written.")
    print()

    existing = read_file(target)

    if remove:
        new, action = remove_block(existing)
        if action == "absent":
            print("  No managed block found - nothing to remove.")
            return 0
        if action == "corrupt":
            print("  Markers are unbalanced. Fix by hand; refusing to guess.", file=sys.stderr)
            return 1
        if not apply_:
            print("  Would REMOVE the managed block. Re-run with --apply.")
            return 0
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(new)
        print(f"  Removed the managed block from {target}")
        return 0

    block = build_block(vault_abs, vault_dir)
    new, action = splice(existing, block)

    if action == "corrupt":
        print("  Markers are unbalanced in the existing file.", file=sys.stderr)
        print("  Fix by hand; refusing to guess where the block ends.", file=sys.stderr)
        return 1

    verb = {"created": "CREATE", "updated": "UPDATE", "appended": "APPEND"}[action]
    print(f"  Would {verb} the managed block → {target}")
    if existing and action == "appended":
        print(f"  Existing content ({len(existing)} bytes) will be left untouched.")
    print()

    if not apply_:
        print("--- block ---")
        print(block)
        print("--- end ---")
        print()
        print("Dry run. Re-run with --apply to write it.")
        return 0

    os.makedirs(os.path.dirname(target), exist_ok=True)
    if existing is not None:
        shutil.copy2(target, target + ".bak")
        print(f"  backup: {target}.bak")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(new)
    print(f"  Wrote the managed block to {target}")

    print()
    print("-------------------------------------------------------")
    print("  Still to do, by hand: register an MCP server that can")
    print("  reach this vault, at USER scope so it works from any")
    print("  directory. For Claude Code:")
    print()
    print("      claude mcp add <name> -s user -- <server command>")
    print()
    print("  The default scope is 'local' and only works in the")
    print("  directory where it was added - that is the usual reason")
    print("  a vault appears unreachable from elsewhere.")
    print()
    print("  Editor extensions inherit the user-scoped registration;")
    print("  they need no separate setup.")
    print()
    print("  Verify: ask a client something only the vault knows,")
    print("  from an unrelated directory. Avoid questions the client")
    print("  can answer from its own environment.")
    print("-------------------------------------------------------")
    return 0


if __name__ == "__main__":
    sys.exit(main())
