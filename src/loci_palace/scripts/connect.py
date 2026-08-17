#!/usr/bin/env python3
"""
Connect assistant clients to this vault. MACHINERY - contains no vault content.

Two installation paths, one source of truth.

  Clients that support @import (Claude Code CLI, editor extensions):
      an import line pointing at System/BOOT.md is written into the global
      instructions file. BOOT.md is re-read every session, so edits take
      effect immediately and nothing goes stale.

  Clients that do not (Desktop chat):
      BOOT.md's contents are printed for pasting into
      Settings -> Profile -> Personal Preferences. This path DOES go stale;
      re-paste after editing BOOT.md.

WHY AN IMPORT RATHER THAN A COPY
--------------------------------
An earlier version inlined the whole instruction into the global file. That
works and then quietly diverges: the vault is edited, the copy is not. An
import has one source.

The cost of an import is that the ENTIRE target file is loaded every session.
That is why BOOT.md is pure payload with no commentary - rationale lives in
System/Runtime Architecture.md, which is not imported.

WHAT THIS DOES NOT DO
---------------------
It does not register an MCP server: the server is a separate project, users
run different ones, and registration needs credentials a scaffolding tool
should not handle. It prints the guidance instead.

SAFETY
------
The global instructions file usually already contains the user's own content.
This writes ONLY between sentinel markers and leaves the rest byte for byte
intact. Dry run is the default.

Usage:
    python3 <vault>/System/connect.py            # show what would change
    python3 <vault>/System/connect.py --apply    # write the import line
    python3 <vault>/System/connect.py --paste    # print the Desktop block
    python3 <vault>/System/connect.py --remove
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
BOOT_REL = ("System", "BOOT.md")


def boot_path(repo_root):
    return V.vault_path(repo_root, *BOOT_REL)


def build_block(repo_root):
    """The managed block: an import line, and nothing else."""
    return (
        f"{BEGIN}\n"
        f"@{boot_path(repo_root)}\n"
        f"{END}"
    )


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
    found = []
    if shutil.which("claude"):
        found.append(("Claude Code CLI", "import"))
    if os.path.isdir("/Applications/Claude.app"):
        found.append(("Claude Desktop", "paste"))
    for name, path in (
        ("VS Code", "~/.vscode/extensions"),
        ("Cursor", "~/.cursor/extensions"),
    ):
        d = os.path.expanduser(path)
        if os.path.isdir(d):
            try:
                if any("claude" in e.lower() for e in os.listdir(d)):
                    found.append((f"{name} (Claude extension)", "import"))
            except OSError:
                pass
    return found


def boot_body(repo_root):
    """BOOT.md minus its frontmatter - what a paste-only client needs."""
    text = read_file(boot_path(repo_root))
    if text is None:
        return None
    _, body = V.split_frontmatter(text)
    return body.strip()


def approx_tokens(text):
    return max(1, len(text) // 4)


def main():
    apply_ = "--apply" in sys.argv
    remove = "--remove" in sys.argv
    paste = "--paste" in sys.argv

    target = DEFAULT_GLOBAL
    if "--global-file" in sys.argv:
        i = sys.argv.index("--global-file")
        if i + 1 < len(sys.argv):
            target = os.path.expanduser(sys.argv[i + 1])

    repo_root = V.find_repo_root()
    vault_dir = V.vault_dir(repo_root)
    boot = boot_path(repo_root)

    if not os.path.isfile(boot):
        print(f"error: {vault_dir}/System/BOOT.md not found", file=sys.stderr)
        print("       connect.py installs an import pointing at it.", file=sys.stderr)
        return 2

    body = boot_body(repo_root)

    if paste:
        print()
        print("Paste this into Settings -> Profile -> Personal Preferences")
        print(f"(Desktop cannot import; re-paste after editing {vault_dir}/System/BOOT.md)")
        print()
        print("--- begin ---")
        print(body)
        print("--- end ---")
        print()
        print(f"~{approx_tokens(body)} tokens, loaded in every conversation.")
        return 0

    print()
    print("Connect clients to this vault")
    print(f"  vault:  {os.path.abspath(repo_root)}  (folder: {vault_dir}/)")
    print(f"  boot:   {vault_dir}/System/BOOT.md  (~{approx_tokens(body)} tokens)")
    print(f"  global: {target}")
    print()

    clients = detect_clients()
    if clients:
        print("Clients detected:")
        for name, method in clients:
            how = "import (stays current)" if method == "import" else "paste (goes stale)"
            print(f"  - {name:34s} {how}")
    else:
        print("  No clients detected. The import can still be installed.")
    print()

    existing = read_file(target)

    if remove:
        new, action = remove_block(existing)
        if action == "absent":
            print("  No managed block found - nothing to remove.")
            return 0
        if action == "corrupt":
            print("  Markers unbalanced. Fix by hand; refusing to guess.", file=sys.stderr)
            return 1
        if not apply_:
            print("  Would REMOVE the managed block. Re-run with --apply.")
            return 0
        shutil.copy2(target, target + ".bak")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(new)
        print(f"  Removed the managed block from {target}")
        return 0

    block = build_block(repo_root)
    new, action = splice(existing, block)

    if action == "corrupt":
        print("  Markers unbalanced in the existing file.", file=sys.stderr)
        print("  Fix by hand; refusing to guess where the block ends.", file=sys.stderr)
        return 1

    verb = {"created": "CREATE", "updated": "UPDATE", "appended": "APPEND"}[action]
    print(f"  Would {verb} the managed block → {target}")
    if existing and action == "appended":
        print(f"  Existing content ({len(existing)} bytes) left untouched.")
    print()
    print("--- block ---")
    print(block)
    print("--- end ---")
    print()

    if not apply_:
        print("Dry run. Re-run with --apply to write it.")
        print("For Desktop, run with --paste to get the block to copy.")
        return 0

    os.makedirs(os.path.dirname(target), exist_ok=True)
    if existing is not None:
        shutil.copy2(target, target + ".bak")
        print(f"  backup: {target}.bak")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(new)
    print(f"  Wrote the import line to {target}")

    print()
    print("-------------------------------------------------------")
    print("  First session after this, the client may ask you to")
    print("  approve reading an external import. Approve it once.")
    print()
    print("  Still to do by hand: register an MCP server that can")
    print("  reach this vault, at USER scope so it works from any")
    print("  directory. For Claude Code:")
    print()
    print("      claude mcp add <name> -s user -- <server command>")
    print()
    print("  The default scope is 'local' and only works where it")
    print("  was added - the usual reason a vault seems unreachable.")
    print()
    print("  Desktop chat cannot import. Run --paste and paste the")
    print("  block into Settings -> Profile -> Personal Preferences.")
    print()
    print("  Verify: ask a client something only the vault knows,")
    print("  from an unrelated directory. Avoid questions the client")
    print("  can answer from its own environment.")
    print("-------------------------------------------------------")
    return 0


if __name__ == "__main__":
    sys.exit(main())
