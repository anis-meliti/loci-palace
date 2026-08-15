#!/usr/bin/env python3
"""
Manifest generator. MACHINERY - contains no vault content.

Produces <vault>/Views/manifest.tsv: one line per note, so the assistant can
route to a known path instead of grepping to find one.

NOTE: manifest.py is machinery and is exportable.
      manifest.tsv is CONTENT (real paths and titles) and is never exported.

The `covers` column drives routing. Precedence:
  1. A `covers:` field in the note's frontmatter (curated - always wins)
  2. Auto-generated from tags + H2 headings (fallback)

Curation lives in the note, never in the generated TSV, because the TSV is
overwritten on every run.

Usage:
    python3 <vault>/System/manifest.py            # write the manifest
    python3 <vault>/System/manifest.py --check    # exit 1 if stale
    python3 <vault>/System/manifest.py --stdout   # print, write nothing
    python3 <vault>/System/manifest.py --weak     # list weak covers

Works against an empty vault: emits a header-only manifest.

No dependencies. Python 3.9+.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vaultlib as V  # noqa: E402

DEFAULT_SOURCE = "vault"
COLUMNS = ("source", "path", "type", "status", "updated", "title", "covers")

MAX_COVERS = 12
WEAK_THRESHOLD = 3  # fewer terms than this == probably unroutable

STOPWORDS = {
    "related", "summary", "overview", "notes", "next", "steps", "next steps",
    "what", "why", "how", "the", "and", "for", "with", "open", "items",
    "problem", "design", "phases", "goal", "related notes",
}


def manifest_rel(repo_root):
    return V.vault_rel(repo_root, "Views", "manifest.tsv")


def clean_field(value):
    """TSV-safe: no tabs, no newlines, collapsed whitespace."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\t", " ")).strip()


def auto_covers(text, fm):
    """Fallback keyword line from tags + H2 headings."""
    terms = []

    for tag in V.parse_tags(fm.get("tags", "")):
        t = tag.strip().lower()
        if t and t not in STOPWORDS and t not in terms:
            terms.append(t)

    for heading in V.H2.findall(V.strip_code(text)):
        h = heading.strip().lower()
        h = re.sub(r"[`*_\[\]]", "", h)
        h = re.sub(r"\s*\(.*?\)\s*", " ", h).strip()
        if not h or h in STOPWORDS or len(h) > 48:
            continue
        if h not in terms:
            terms.append(h)

    return ", ".join(terms[:MAX_COVERS])


def build_covers(text, fm):
    """Curated `covers:` frontmatter wins; otherwise auto-generate."""
    curated = fm.get("covers", "").strip()
    if curated:
        return curated, True
    return auto_covers(text, fm), False


def build_rows(repo_root):
    notes = V.collect_notes(repo_root, required=False)
    source = V.vault_dir(repo_root, required=False) or DEFAULT_SOURCE
    rows = []

    for rel, text in notes.items():
        fm, problem = V.parse_frontmatter(text)
        covers, curated = ("", False) if problem else build_covers(text, fm)
        rows.append({
            "source": source.lower(),
            "path": rel.replace(os.sep, "/"),
            "type": clean_field(fm.get("type", "")) if not problem else "",
            "status": clean_field(fm.get("status", "")) if not problem else "",
            "updated": clean_field(fm.get("updated", "")) if not problem else "",
            "title": clean_field(V.note_title(text, rel)),
            "covers": clean_field(covers),
            "_curated": curated,
        })

    rows.sort(key=lambda r: r["path"])
    return rows


def render(rows):
    lines = ["\t".join(COLUMNS)]
    for r in rows:
        lines.append("\t".join(clean_field(r[c]) for c in COLUMNS))
    return "\n".join(lines) + "\n"


def report_weak(rows):
    weak = []
    for r in rows:
        if r["_curated"]:
            continue
        terms = [t for t in r["covers"].split(",") if t.strip()]
        if len(terms) < WEAK_THRESHOLD:
            weak.append((r["path"], r["covers"]))

    if not weak:
        print("No weak covers. Every note has curated or sufficient routing terms.")
        return

    print(f"{len(weak)} note(s) with weak covers - add a `covers:` frontmatter field:\n")
    for path, covers in weak:
        print(f"  {path}")
        print(f"      covers: {covers or '(empty)'}")
    print("\nCurate with a line like:")
    print("  covers: settled questions, rejected tools, why we chose X")


def main():
    repo_root = V.find_repo_root()
    rel_path = manifest_rel(repo_root)
    target = os.path.join(repo_root, rel_path)

    rows = build_rows(repo_root)
    content = render(rows)

    if "--weak" in sys.argv:
        report_weak(rows)
        return

    if "--stdout" in sys.argv:
        sys.stdout.write(content)
        return

    if "--check" in sys.argv:
        try:
            with open(target, encoding="utf-8") as fh:
                current = fh.read()
        except OSError:
            current = None

        if current == content:
            print(f"manifest up to date ({len(rows)} notes)")
            sys.exit(0)

        print("")
        print("Manifest is stale. A stale manifest routes confidently to the wrong")
        print("place, which is worse than having none. Regenerate and stage it:")
        print("")
        print(f"    python3 {V.vault_rel(repo_root, 'System', 'manifest.py')}")
        print(f"    git add {rel_path}")
        print("")
        sys.exit(1)

    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(content)

    curated = sum(1 for r in rows if r["_curated"])
    print(f"wrote {rel_path} ({len(rows)} notes, {curated} with curated covers)")


if __name__ == "__main__":
    main()
