---
type: system
status: active
updated: {{DATE}}
tags: [system, schema, conventions]
covers: how to write a note, frontmatter rules, required fields, type values, status values, sentinel markers, what the assistant may overwrite, write rules, validation, covers field
---

# Vault Schema

The contract every note in `{{VAULT_DIR}}/` follows. Binding on both you and the assistant.

Conventions only work when something checks them. Everything here is enforced by `System/lint.py` and the pre-commit hook — nothing relies on remembering.

## Required frontmatter

Every note. Must be the **first bytes of the file** — never inside a code fence.

```yaml
---
type: <see below>
status: <see below>
updated: YYYY-MM-DD
tags: [at, least, one]
---
```

Frontmatter inside a fence is the most damaging mistake available: the editor parses **zero** properties, so the note becomes invisible to views, queries, and property search while looking completely normal.

## Optional frontmatter

| Field | Purpose |
|---|---|
| `covers` | Curated routing keywords for `Views/manifest.tsv` |

Write `covers` as **the questions this note answers**, not a description of the note.

Auto-generated `covers` (from tags and headings) describes what a note *is*. Routing needs what it *answers*. A decision log auto-generating to `context, decisions` matches no plausible question; curated to `why we rejected X, tools evaluated, settled questions` it routes on the first try.

Set it surgically, never by rewriting the file:

```
python3 {{VAULT_DIR}}/System/covers.py "<path>" "terms, more terms"
```

`manifest.py --weak` lists candidates, but it counts terms and cannot judge whether they are routable. Use judgement.

## `type` vocabulary (closed set)

| Value | Meaning | Location |
|---|---|---|
| `index` | Navigation entry point | `{{VAULT_DIR}}/Index.md` |
| `context` | Standing facts about you | `{{VAULT_DIR}}/Context/` |
| `project` | A project's state | `{{VAULT_DIR}}/Projects/` |
| `session` | One conversation's distillation | `{{VAULT_DIR}}/Sessions/` |
| `system` | Vault machinery | `{{VAULT_DIR}}/System/` |
| `plan` | Time-bound plan | anywhere |

## `status` vocabulary (closed set)

| Value | Meaning |
|---|---|
| `active` | Being worked on now |
| `paused` | Deliberately parked, will resume |
| `idea` | Specced but no work started |
| `done` | Complete; candidate for `Archive/` |

## When NOT to bump `updated`

`updated:` means *the content changed*. It feeds the staleness column in `Views/Projects.base`.

**Do not bump it for routing-metadata-only edits** — `covers` changes in particular. Improving a note's keywords is not work on the thing it describes, and a bulk curation pass would otherwise reset every staleness signal to zero. `covers.py` never touches `updated`.

## Banned patterns

- `date:` — use `updated:`. Freshness matters; creation date does not.
- Frontmatter inside a fence — see above
- Trailing assistant chatter ("This document captures…", "By following this spec…")
- Missing `type` — breaks every derived view
- **Absolute paths** — machine-specific. Use vault-relative paths.
- **The vault directory name inside machinery** — it is configurable

## Sentinel markers

The assistant may rewrite **only** what sits inside a generated block. Everything else is yours.

```markdown
<!-- @generated:status -->
Content the assistant owns and may fully replace.
<!-- /@generated:status -->

<!-- @user -->
Your notes. Never modified, even during compaction.
<!-- /@user -->
```

- Unmarked content is treated as yours — the assistant asks rather than rewrites
- Every generated block needs a name, so partial regeneration is possible
- Comments are invisible in reading view
- Unbalanced blocks fail the lint

This is the structural answer to "did the assistant clobber my edit."

## Machinery vs content

**Machinery** — `System/`, `Views/` structure, `Index.md`, root `CLAUDE.md`. Portable between machines. Must contain no personal content: no names, no employer, no specific project titles.

**Content** — `Context/`, `Projects/`, `Sessions/`, `Archive/`, `Views/manifest.tsv`. Never leaves the machine it was created on.

`System/export.sh` ships machinery only, from an allowlist. An allowlist rather than a denylist because a denylist fails open — add a content directory and it would ship silently.

## Write conventions

- `Context/`, `Index.md`, `System/`: **full overwrite only, never append.** Appending to overwrite-only notes stacks duplicate copies that are easy to miss and hard to unpick.
- `Sessions/`: one new file per conversation; appending within the same session is fine
- Every note ends with a `## Related` wiki-link footer
- Bump `updated:` on every content write. A stale date is a lie; a falsely fresh one is worse.
- **Prefer surgical edits to full rewrites.** A whole-file rewrite can silently drop content you did not mean to touch.
- After adding or renaming a note: `python3 {{VAULT_DIR}}/System/manifest.py`

## Validation

| Tool | Catches |
|---|---|
| `Views/Health.base` | Schema violations, staleness — visual |
| `System/lint.py` | Duplication, dead links, orphans, fenced frontmatter, sentinel balance, unfilled templates |
| `System/manifest.py --check` | Stale manifest |
| `System/export.sh --dry-run` | What machinery would leave this machine |
| `System/hooks/pre-commit` | Lint + manifest freshness, enforced at commit |

All validators share scope via `System/vaultlib.py` — only `{{VAULT_DIR}}/**/*.md`. Files outside are host config, not notes.

## Related
[[Index]] · [[Context/Decisions]]
