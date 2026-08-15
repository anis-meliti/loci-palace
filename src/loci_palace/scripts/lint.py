#!/usr/bin/env python3
"""
Vault linter. MACHINERY - contains no vault content.

Scope, frontmatter parsing, and vault-directory resolution come from vaultlib
so this cannot drift from manifest.py or the .base views.

Catches:
  - UNFILLED TEMPLATES still carrying their placeholder marker
  - frontmatter trapped inside a code fence (the editor parses ZERO properties)
  - DUPLICATED note bodies (the append bug)
  - dead [[wikilinks]]
  - orphan notes (nothing links to them)
  - banned `date:` field
  - invalid type/status vocabulary
  - unclosed sentinel markers

Code spans and fenced blocks are stripped before scanning, so documentation
*about* markers or YAML is not mistaken for the real thing.

IMPORTANT - reporting honestly:
  This script always prints WHICH directory it scanned, and treats an
  unresolvable vault directory as a hard error rather than an empty result.
  A checker that silently finds nothing is indistinguishable from a checker
  that finds no problems, and the second is a lie.

Usage:
    python3 <vault>/System/lint.py
    python3 <vault>/System/lint.py --quiet         # errors only, exit 1 if any
    python3 <vault>/System/lint.py --allow-empty   # 0 notes is not an error

No dependencies. Python 3.9+.
"""

import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vaultlib as V  # noqa: E402

SENTINEL_OPEN = re.compile(r"<!--\s*@generated:([\w-]+)\s*-->")
SENTINEL_CLOSE = re.compile(r"<!--\s*/@generated:([\w-]+)\s*-->")

# Scaffolded templates carry this marker INSIDE AN HTML COMMENT. It is an ERROR
# until deleted: an unfilled placeholder is worse than an absent fact, because
# the manifest routes to it confidently and the assistant believes what it finds.
#
# Matching only inside a comment is deliberate. A bare substring match also fires
# on notes that *document* the marker - roadmaps, schemas, session logs. That
# false positive has now occurred four times in this codebase in different forms
# (sentinel regex, escaped pipes, frontmatter delimiters, this). The rule:
# match the structure, never the token.
TEMPLATE_MARKER = re.compile(r"<!--[^>]*TEMPLATE-UNFILLED", re.DOTALL)

STACKED_FM = re.compile(
    r"^---[ \t]*\n(?:[ \t]*[\w-]+[ \t]*:[^\n]*\n)+[ \t]*---[ \t]*$",
    re.MULTILINE,
)

ERROR, WARN = "ERROR", "WARN"


def check_duplication(clean_text):
    """Detect the append bug. Operates on code-stripped text."""
    problems = []
    _, body = V.split_frontmatter(clean_text)

    extra = STACKED_FM.findall(body)
    if extra:
        problems.append(
            (ERROR, f"{len(extra)} extra frontmatter block(s) in body - appended, not overwritten")
        )

    headings = [h.strip() for h in V.H1.findall(body)]
    for h in sorted(set(headings)):
        if headings.count(h) > 1:
            problems.append((ERROR, f"H1 '{h}' appears {headings.count(h)}x - duplicated body"))

    return problems


def lint(repo_root):
    # required=True: an unresolvable vault directory is a hard error, not an
    # empty scan. That is the difference between "clean" and "I found nothing".
    notes = V.collect_notes(repo_root, required=True)
    findings = defaultdict(list)

    basenames = {}
    for rel in notes:
        basenames.setdefault(os.path.splitext(os.path.basename(rel))[0], []).append(rel)

    linked_to = set()

    for rel, text in sorted(notes.items()):
        clean = V.strip_code(text)
        fm, problem = V.parse_frontmatter(text)

        if TEMPLATE_MARKER.search(clean):
            findings[rel].append(
                (ERROR, "still a template - fill it in and delete the marker comment")
            )

        if problem:
            findings[rel].append((ERROR, problem))
        else:
            for key in V.REQUIRED:
                if key not in fm:
                    findings[rel].append((ERROR, f"missing required frontmatter: {key}"))
            if "date" in fm:
                findings[rel].append((WARN, "uses banned `date:` - rename to `updated:`"))
            t = fm.get("type")
            if t and t not in V.VALID_TYPE:
                findings[rel].append((ERROR, f"invalid type '{t}' (allowed: {sorted(V.VALID_TYPE)})"))
            s = fm.get("status")
            if s and s not in V.VALID_STATUS:
                findings[rel].append((ERROR, f"invalid status '{s}' (allowed: {sorted(V.VALID_STATUS)})"))
            if t == "project" and not s:
                findings[rel].append((WARN, "project note has no status"))

        findings[rel].extend(check_duplication(clean))

        opens = SENTINEL_OPEN.findall(clean)
        closes = SENTINEL_CLOSE.findall(clean)
        for name in set(opens) | set(closes):
            if opens.count(name) != closes.count(name):
                findings[rel].append((ERROR, f"unbalanced sentinel block '@generated:{name}'"))

        for raw in V.WIKILINK.findall(clean):
            target = V.link_target(raw)
            if not target:
                continue
            stem = os.path.splitext(os.path.basename(target))[0]
            if stem in basenames:
                linked_to.update(basenames[stem])
            else:
                findings[rel].append((WARN, f"dead wikilink: [[{target}]]"))

    for rel in notes:
        if rel in linked_to:
            continue
        if os.path.basename(rel) == "Index.md":
            continue
        if os.sep + "Sessions" + os.sep in os.sep + rel:
            continue
        findings[rel].append((WARN, "orphan - no other note links here"))

    return notes, findings


def main():
    quiet = "--quiet" in sys.argv
    allow_empty = "--allow-empty" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    repo_root = V.find_repo_root(args[0] if args else None)
    name = V.vault_dir(repo_root)          # exits 2 if unresolvable

    notes, findings = lint(repo_root)

    errors = sum(1 for f in findings.values() for lvl, _ in f if lvl == ERROR)
    warns = sum(1 for f in findings.values() for lvl, _ in f if lvl == WARN)

    for rel in sorted(findings):
        items = findings[rel]
        if quiet:
            items = [i for i in items if i[0] == ERROR]
        if not items:
            continue
        print(f"\n{rel}")
        for level, msg in items:
            print(f"  [{level}] {msg}")

    # Always state WHAT was scanned. A count with no scope is not a result.
    print(f"\nscanned {name}/ - {len(notes)} notes, {errors} errors, {warns} warnings")

    if not notes and not allow_empty:
        print("")
        print(f"  No notes found in {name}/.")
        print("  Expected for a freshly scaffolded vault; pass --allow-empty")
        print("  to treat that as success. Otherwise the vault directory is")
        print("  probably misconfigured - check .loci.json.")
        sys.exit(1)

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
