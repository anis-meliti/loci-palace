#!/usr/bin/env python3
"""
Set the `covers:` routing field on a note. MACHINERY - contains no vault content.

Surgical: rewrites exactly one frontmatter line and leaves every other byte
untouched. Avoids full-file rewrites, which risk transcription errors on long
notes and are how working config gets silently dropped.

Usage:
    python3 Luna/System/covers.py <note-path> "terms, more terms"
    python3 Luna/System/covers.py <note-path> --show
    python3 Luna/System/covers.py <note-path> --clear

Deliberately does NOT bump `updated:`.
`covers` is routing metadata, not content. Bumping `updated` would reset the
staleness signal that Views/Projects.base depends on - a note untouched for
126 days would look fresh because someone improved its keywords.

No dependencies. Python 3.9+.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vaultlib as V  # noqa: E402


def locate_frontmatter(lines):
    """Return (open_idx, close_idx) of the frontmatter fence, or (None, None)."""
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "":
            continue
        if line.rstrip() == "---":
            start = i
        break
    if start is None:
        return None, None

    for j in range(start + 1, len(lines)):
        if lines[j].rstrip() == "---":
            return start, j
    return None, None


def set_covers(path, value):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()

    lines = text.split("\n")
    open_i, close_i = locate_frontmatter(lines)

    if open_i is None:
        print(f"error: {path} has no parseable frontmatter", file=sys.stderr)
        return 1

    existing = None
    for i in range(open_i + 1, close_i):
        if lines[i].split(":", 1)[0].strip() == "covers":
            existing = i
            break

    if value is None:
        if existing is None:
            print(f"no covers field: {path}")
            return 0
        del lines[existing]
        action = "cleared"
    elif existing is not None:
        lines[existing] = f"covers: {value}"
        action = "updated"
    else:
        lines.insert(close_i, f"covers: {value}")
        action = "added"

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"{action}: {path}")
    return 0


def show_covers(path):
    with open(path, encoding="utf-8") as fh:
        fm, problem = V.parse_frontmatter(fh.read())
    if problem:
        print(f"{path}: {problem}")
        return 1
    print(f"{path}\n  covers: {fm.get('covers', '(none)')}")
    return 0


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2

    repo_root = V.find_repo_root()
    rel = args[0]
    path = rel if os.path.isabs(rel) else os.path.join(repo_root, rel)

    if not os.path.isfile(path):
        print(f"error: no such file: {rel}", file=sys.stderr)
        return 1

    if "--show" in args:
        return show_covers(path)
    if "--clear" in args:
        return set_covers(path, None)

    rest = [a for a in args[1:] if not a.startswith("--")]
    if not rest:
        print("error: no covers value given", file=sys.stderr)
        return 2

    return set_covers(path, " ".join(rest).strip())


if __name__ == "__main__":
    sys.exit(main())
