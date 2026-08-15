#!/usr/bin/env python3
"""
Shared vault primitives. MACHINERY - contains no vault content.

Imported by lint.py, manifest.py, and covers.py so the validators cannot drift
apart on scope, frontmatter parsing, or root resolution.

The vault directory name is NOT hardcoded. It is resolved, in order:
  1. `vault_dir` in .loci.json at the repo root   (explicit, tracked)
  2. the single directory containing System/      (detected)
  3. error

Hardcoding it would bake one user's assistant name into machinery shipped to
everyone else.

Must work against an empty vault: no note is assumed to exist.

No dependencies. Python 3.9+.
"""

import json
import os
import re
import subprocess
import sys

CONFIG_FILE = ".loci.json"

# Bumped when the machinery contract changes, so two instances can be compared
# without diffing content.
#   7.0.0-a  manifest routing, vaultlib, covers
#   7.1.0-b  registry, per-machine config, machinery export with leak scan
#   0.1.0    repackaged as loci-palace; vault directory name made configurable
MACHINERY_VERSION = "0.1.0"

VALID_TYPE = {"index", "context", "project", "session", "system", "plan"}
VALID_STATUS = {"active", "paused", "idea", "done"}
REQUIRED = ("type", "updated", "tags")

RESERVED_DIRS = {".git", ".obsidian", "dist", "node_modules", "src", "__pycache__"}

FENCE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)
H2 = re.compile(r"^##\s+(.+)$", re.MULTILINE)
WIKILINK = re.compile(r"\[\[([^\[\]]+)\]\]")


# --------------------------------------------------------------------------
# location
# --------------------------------------------------------------------------

def find_repo_root(start=None):
    """Resolve the repo root. Never hardcode an absolute path."""
    start = start or os.getcwd()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start, capture_output=True, text=True, check=True,
        )
        root = out.stdout.strip()
        if root:
            return root
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass

    cur = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(cur, CONFIG_FILE)) or _detect_vault_dir(cur):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.abspath(start)
        cur = parent


def _detect_vault_dir(repo_root):
    """The single non-reserved directory containing System/, or None."""
    try:
        entries = sorted(os.listdir(repo_root))
    except OSError:
        return None
    found = [
        d for d in entries
        if not d.startswith(".")
        and d not in RESERVED_DIRS
        and os.path.isdir(os.path.join(repo_root, d, "System"))
    ]
    return found[0] if len(found) == 1 else None


def vault_dir(repo_root, required=True):
    """Resolve the vault directory name for this repo."""
    cfg_path = os.path.join(repo_root, CONFIG_FILE)
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as fh:
                name = (json.load(fh) or {}).get("vault_dir")
            if name:
                return name
        except (OSError, ValueError):
            pass

    detected = _detect_vault_dir(repo_root)
    if detected:
        return detected

    if required:
        print(
            f"error: cannot determine the vault directory under {repo_root}\n"
            f"       add {CONFIG_FILE} with {{\"vault_dir\": \"YourFolder\"}}, "
            f"or run `loci init`",
            file=sys.stderr,
        )
        sys.exit(2)
    return None


def vault_path(repo_root, *parts):
    """Absolute path inside the vault directory."""
    return os.path.join(repo_root, vault_dir(repo_root), *parts)


def vault_rel(repo_root, *parts):
    """Repo-relative POSIX path inside the vault directory."""
    return "/".join((vault_dir(repo_root),) + parts)


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def strip_code(text):
    """Remove fenced blocks and inline code spans."""
    return INLINE_CODE.sub("", FENCE.sub("", text))


def split_frontmatter(text):
    """Return (frontmatter_text, body). Body excludes the leading FM block."""
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return "", stripped
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        return "", stripped
    return parts[1], parts[2]


def parse_frontmatter(text):
    """Return (dict, problem_or_None). Detects fenced frontmatter explicitly."""
    stripped = text.lstrip()

    if stripped.startswith("```"):
        after = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if after.lstrip().startswith("---"):
            return {}, "frontmatter is inside a code fence - the editor parses NO properties"
        return {}, "no frontmatter (file opens with a code fence)"

    if not stripped.startswith("---"):
        return {}, "no frontmatter"

    raw, _ = split_frontmatter(text)
    if not raw:
        return {}, "malformed frontmatter (unterminated block)"

    fm = {}
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip().strip("\"'")
    return fm, None


def parse_tags(value):
    """Parse a frontmatter tags value: [a, b] or a, b -> ['a', 'b']."""
    if not value:
        return []
    value = value.strip().lstrip("[").rstrip("]")
    return [t.strip().strip("\"'") for t in value.split(",") if t.strip()]


def link_target(raw):
    """Extract the file target from a wikilink body, handling \\| and #refs."""
    target = re.split(r"\\?\|", raw, 1)[0]
    target = re.split(r"[#^]", target, 1)[0]
    return target.strip().rstrip("\\").strip()


# --------------------------------------------------------------------------
# collection
# --------------------------------------------------------------------------

def collect_notes(repo_root, required=True):
    """
    Collect .md files inside the vault directory only, as {relpath: text}.

    Scope rule, shared with the .base views' path filter: files outside the
    vault directory (CLAUDE.md, AGENTS.md, README) are host config, not notes.

    Returns {} for an empty vault rather than failing.
    """
    notes = {}
    name = vault_dir(repo_root, required=required)
    if not name:
        return notes

    root = os.path.join(repo_root, name)
    if not os.path.isdir(root):
        if required:
            print(f"error: no '{name}/' directory under {repo_root}", file=sys.stderr)
            sys.exit(2)
        return notes

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in sorted(filenames):
            if not fn.endswith(".md"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, repo_root)
            try:
                with open(full, encoding="utf-8") as fh:
                    notes[rel] = fh.read()
            except OSError as exc:
                print(f"  could not read {rel}: {exc}", file=sys.stderr)
    return notes


def note_title(text, rel_path):
    """First H1, else the filename stem."""
    m = H1.search(strip_code(text))
    if m:
        return m.group(1).strip()
    return os.path.splitext(os.path.basename(rel_path))[0]
