# loci-palace

Persistent, routable memory for AI coding assistants — as plain Markdown you own.

Named for the *method of loci*: memory anchored to places you can navigate back to. The vault is the places; a generated manifest is the map.

## The problem

You use an assistant daily. Every session starts from nothing. You re-explain
your stack, your constraints, and the decision you already made twice.

You could keep notes and point the assistant at them. But an unstructured pile
of Markdown makes things *worse*: the assistant searches, finds a stale note
alongside a current one, and answers confidently from the wrong one.

## What this is

A vault with three properties an unstructured folder does not have:

**A schema that is enforced.** Every note declares `type`, `status`, `updated`,
and `tags`. A linter and a pre-commit hook check it. Conventions that are only
written down get violated silently — this one cannot be.

**A routing index instead of search.** `manifest.tsv` lists every note with a
curated `covers` line describing *the questions that note answers*. The
assistant reads one bounded index and opens exactly one file. Search costs more
as the vault grows and surfaces stale notes next to current ones; an index does
neither.

**A boundary between machinery and content.** Tooling is portable. Your notes
are not, and cannot be shipped by accident.

It is plain Markdown throughout. No database, no service, no lock-in. Delete
the tooling and you still have your notes.

## Requirements

- Python 3.9+ and git
- An assistant that can read and write local files — via MCP, a CLI agent, or
  an editor integration
- Optionally [Obsidian](https://obsidian.md), for the `.base` views

`loci preflight` checks all of it and names anything missing.

## Install

```bash
pip install loci-palace     # or: uv tool install loci-palace
```

## Use

```bash
loci preflight              # verify the environment first
loci init ~/my-vault        # scaffold (asks what to call the vault folder)
loci doctor                 # diagnose an existing vault
```

`init` creates the structure, installs the tooling, writes the templates, and
sets up git with the pre-commit hook. Then it stops and tells you the one thing
it cannot do: fill in who you are.

## What you get

```
my-vault/
  CLAUDE.md          ← how the assistant should use this vault
  .loci.json         ← vault folder name, machinery version
  <YourFolder>/
    Index.md         ← boot protocol, folder map, session protocols
    Context/         ← standing facts. CRITICAL_FACTS.md is read every session.
    Projects/        ← per-project state
    Sessions/        ← one note per conversation
    System/          ← the tooling and the schema
    Views/           ← manifest.tsv and derived .base views
    Archive/
```

The vault folder name is yours to choose. There is no default, because it is a
choice rather than something the tool can compute.

## The one thing you must do

`Context/CRITICAL_FACTS.md` ships as prompts, not defaults, and the linter
reports an error until you fill it in and delete the marker.

That is deliberate. An unfilled placeholder is worse than an absent fact: the
assistant will read it every session and believe it, and the manifest will
route to it confidently.

Aim for about 150 tokens. Write facts that **change the answer**:

| Weak | Strong |
|---|---|
| "I like clean code" | "Reject solutions that add a dependency for something stdlib can do" |
| "I'm a developer" | "Tech lead; I review more than I write, so lead with the trade-off" |
| "I use a Mac" | "Shell is fish — `set x`, not `x=`" |

## Keeping it healthy

```bash
python3 <vault>/System/lint.py            # schema, duplication, dead links, orphans
python3 <vault>/System/manifest.py        # regenerate the routing index
python3 <vault>/System/manifest.py --weak # notes whose covers won't route
python3 <vault>/System/covers.py <note> "terms"   # set routing keywords
python3 <vault>/System/audit.sh           # is any personal content in the tooling?
```

The pre-commit hook runs the linter and regenerates the manifest, refusing when
it cannot do so safely — for instance during a partial commit, where the
regenerated index would describe notes the commit does not contain.

## Design principles

These were not designed up front. Each one is the residue of something that
went wrong.

1. **The vault is the source of truth.** Memory lives in Markdown, not in a tool.
2. **Curated beats generated.** The assistant synthesises; you keep final say
   on structure. No scheduled agents rewriting your notes unattended.
3. **Conventions must be enforced by tooling, not prose.** A rule nobody checks
   is not a rule. A schema was documented here for months and violated by seven
   of eight notes the first time anything looked.
4. **Overwrite standing context; never append.** Appending to overwrite-only
   notes stacks duplicates that are easy to miss and hard to unpick.
5. **The assistant writes only inside `@generated` blocks.** Everything else is
   yours, structurally.
6. **A spot-check is not a verification.** Check every file, or say you did not.
7. **Correct output is not proof of a correct mechanism.** A system can answer
   perfectly while doing something entirely different from what you documented.
8. **A checker that finds nothing must not look like a checker that finds no
   problems.** Always report the scope, not just the count.
9. **Prefer surgical edits to full rewrites.** A whole-file rewrite silently
   drops what you did not mean to touch.
10. **Machinery is portable; content never leaves its machine.**

## Machinery and content

**Machinery** — `System/`, `Views/` structure, `Index.md`, `CLAUDE.md`.
Portable. Contains no personal content by rule, and `audit.sh` checks it against
a local list of private terms.

**Content** — `Context/`, `Projects/`, `Sessions/`, `Archive/`, `manifest.tsv`.
Never travels.

This package is machinery only. Installing it on a second machine gives you the
same system and none of your data, which is the point: a work machine and a
personal machine can share tooling and share nothing else.

## Not included

No source ingestion, no web research, no scheduled agents, no embeddings. Those
are real features of other tools and deliberately absent here — they trade
curation for volume, and this system is built on the opposite bet.

## Contributing

Run `audit.sh` before opening a pull request. It checks the tooling for personal
strings, which is easy to leak into a doc comment without noticing.

## Licence

See `LICENSE`.
