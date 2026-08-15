# loci-palace

Persistent, routable memory for AI coding assistants — as plain Markdown you own.

Named for the *method of loci*: memory anchored to places you can navigate back to. The vault is the places; a generated manifest is the map.

## The problem

You use an assistant daily. Every session starts from nothing. You re-explain
your stack, your constraints, and the decision you already made twice.

You could keep notes and point the assistant at them. But an unstructured pile
of Markdown makes things *worse*: the assistant searches, finds a stale note
alongside a current one, and answers confidently from the wrong one.

And each client keeps its own memory, if it keeps any at all. What you told the
terminal agent is invisible to the desktop app.

## What this is

A vault with four properties an unstructured folder does not have:

**A schema that is enforced.** Every note declares `type`, `status`, `updated`,
and `tags`. A linter and a pre-commit hook check it. Conventions that are only
written down get violated silently — this one cannot be.

**A routing index instead of search.** `manifest.tsv` lists every note with a
curated `covers` line describing *the questions that note answers*. The
assistant reads one bounded index and opens exactly one file. Search costs more
as the vault grows and surfaces stale notes next to current ones; an index does
neither.

**One memory across every client.** The same vault, reachable from a chat app,
a terminal agent, and an editor extension — from any directory, or none.

**A boundary between machinery and content.** Tooling is portable. Your notes
are not, and cannot be shipped by accident.

Plain Markdown throughout. No database, no service, no lock-in. Delete the
tooling and you still have your notes.

## Requirements

- Python 3.9+ and git
- An MCP server that can reach a local folder, registered with your client
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

## Making it reachable from every client

This is the part that is easy to get subtly wrong, and the failure is quiet: the
vault works in one directory and appears not to exist anywhere else.

Two independent mechanisms are needed.

### 1. Register the MCP server at **user** scope

```bash
claude mcp add <name> -s user -- <server command>
```

**`-s user` is the whole thing.** The default scope is `local`, which only works
in the directory where you ran the command. That is almost always the reason a
vault seems unreachable from elsewhere.

Editor extensions inherit a user-scoped registration. They need no separate
setup.

This package does not register the server for you: the server is a separate
project, users run different ones, and registration needs credentials that a
scaffolding tool has no business handling.

### 2. Install the global instructions

```bash
python3 <vault>/System/connect.py            # dry run - shows the block
python3 <vault>/System/connect.py --apply    # write it
```

This writes a marked block into your global instructions file
(`~/.claude/CLAUDE.md`) telling clients the vault exists, how to route through
the manifest, and which phrasings mean *consult the vault* rather than *store a
new fact*.

It writes **only** between sentinel markers, backs the file up first, and is a
dry run unless you pass `--apply`. Your own instructions in that file are left
byte for byte intact. `--remove` takes the block back out.

Registering the server makes the vault *reachable*. The instructions make the
assistant *reach for it*. Both are needed; the second is the one people forget.

### 3. Verify

Ask a client something **only the vault knows**, from an unrelated directory.

Choose the question carefully: "what shell do I use?" is a bad test, because
clients inject platform and shell into their own system prompt and will answer
correctly without ever touching the vault. A good test has exactly one path to
the right answer.

Watch for the tool call, not just the answer. A correct answer with no tool call
means something other than the vault supplied it.

## What you get

```
my-vault/
  CLAUDE.md          ← how the assistant should use this vault
  .loci.json         ← vault folder name, machinery version
  <YourFolder>/
    Index.md         ← boot protocol, folder map, session protocols
    Context/         ← standing facts. CRITICAL_FACTS.md is the identity note.
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
assistant will read it and believe it, and the manifest will route to it
confidently.

Aim for about 150 tokens. Write facts that **change the answer**:

| Weak | Strong |
|---|---|
| "I like clean code" | "Reject solutions that add a dependency for something stdlib can do" |
| "I'm a developer" | "Tech lead; I review more than I write, so lead with the trade-off" |
| "I use a Mac" | "Shell is fish — `set x`, not `x=`" |

It is loaded on demand rather than at session start — deliberately. With the
server at user scope your clients open in every directory, and preloading
personal identity into a session about an unrelated codebase is cost with no
benefit.

## Keeping it healthy

```bash
python3 <vault>/System/lint.py            # schema, duplication, dead links, orphans
python3 <vault>/System/manifest.py        # regenerate the routing index
python3 <vault>/System/manifest.py --weak # notes whose covers won't route
python3 <vault>/System/covers.py <note> "terms"   # set routing keywords
python3 <vault>/System/audit.sh           # is any personal content in the tooling?
python3 <vault>/System/connect.py         # re-check the global instructions
```

The pre-commit hook runs the linter and regenerates the manifest, refusing when
it cannot do so safely — for instance during a partial commit, where the
regenerated index would describe notes the commit does not contain.

## Design principles

These were not designed up front. Each is the residue of something that went
wrong.

1. **The vault is the source of truth.** Memory lives in Markdown, not in a
   tool — and not in a client's private store that the other clients cannot see.
2. **Curated beats generated.** The assistant synthesises; you keep final say on
   structure. No scheduled agents rewriting your notes unattended.
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
same system and none of your data — so a work machine and a personal machine can
share tooling and share nothing else.

## Not included

No source ingestion, no web research, no scheduled agents, no embeddings. Those
are real features of other tools and deliberately absent here — they trade
curation for volume, and this system is built on the opposite bet.

## Contributing

Run `audit.sh` before opening a pull request. It checks the tooling for personal
strings, which are easy to leak into a doc comment without noticing.

## Licence

See `LICENSE`.
