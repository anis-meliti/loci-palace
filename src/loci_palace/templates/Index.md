---
type: index
status: active
updated: {{DATE}}
tags: [index, moc, boot]
covers: how the vault works, folder structure, boot protocol, where things live, session end protocol, compaction, distillation, write rules, vault map
---

# {{VAULT_DIR}} — Index

Map of the vault. The operating contract lives in [[System/BOOT]] and is loaded
globally via an import — this note is reference, not instruction.

## Boot

1. [[System/BOOT]] — stance, routing, and write rules. Always loaded.
2. [[Context/CRITICAL_FACTS]] — identity. Read when a question depends on personal context.
3. `Views/manifest.tsv` — match the question against the `covers` column, open that one note.

The manifest exists so nothing has to *search* to find a file. Searching works, but it costs more every time the vault grows and returns stale notes alongside current ones. A bounded index does not.

Fall back to searching only when no `covers` line matches — and say so, because a miss means that note needs curating.

## Folder map

```
{{VAULT_DIR}}/
  Index.md      ← you are here
  Context/      ← standing facts about you. Overwrite-only.
  Projects/     ← per-project state, curated, wiki-linked
  Sessions/     ← dated conversation summaries, one file per session
  System/       ← machinery: BOOT, Schema, vaultlib, lint, manifest, covers, hooks
  Views/        ← derived state: .base files, manifest.tsv
  Archive/      ← completed or stale notes, moved during compaction
```

## Write rules

Read [[System/Schema]] before writing. In short:

- `type`, `status`, `updated`, `tags` as the **first bytes of the file** — never in a code fence
- `Context/`, `Index.md`, `System/`: full overwrite only, never append
- `Sessions/`: one new file per conversation
- The assistant rewrites only inside generated sentinel blocks
- Bump `updated:` on content writes; never for `covers`-only edits
- No absolute paths, and never hardcode the vault directory name
- Prefer surgical edits to full rewrites
- After adding or renaming a note: `python3 {{VAULT_DIR}}/System/manifest.py`

## Derived state — do not hand-maintain

- `Views/manifest.tsv` — routing index for every note
- `Views/Projects.base` — project status and staleness
- `Views/Health.base` — schema violations

Never hand-write a status that a view already derives. A hand-maintained index rots silently; a derived one cannot.

## Machinery vs content

`System/`, `Views/` structure, this Index, and root `CLAUDE.md` are **machinery** — portable via `System/connect.py` and the package, and must contain no personal content.

`Context/`, `Projects/`, `Sessions/`, `Archive/`, and `Views/manifest.tsv` are **content** — they stay on this machine.

Check with `bash {{VAULT_DIR}}/System/audit.sh`.

## Session end protocol (distillation)

1. Write `Sessions/YYYY-MM-DD <Topic>.md`
2. Update affected `Projects/` notes — inside generated blocks where present
3. Add settled choices to [[Context/Decisions]]
4. Update `Context/` only if standing facts changed
5. Regenerate the manifest
6. Update this Index only if folders or protocol changed

Without this, every session starts from nothing and the vault becomes a pile of transcripts.

## Compaction protocol (every ~10 sessions)

1. Read session notes since the last compaction
2. Fold durable facts into `Context/`
3. Move stale sessions and `status: done` projects to `Archive/`
4. Run `python3 {{VAULT_DIR}}/System/lint.py` and clear all errors
5. Regenerate the manifest

## Health

```
python3 {{VAULT_DIR}}/System/lint.py
python3 {{VAULT_DIR}}/System/manifest.py --check
```

Both run automatically at commit via `System/hooks/pre-commit`.

## Related
[[System/BOOT]] · [[Context/CRITICAL_FACTS]] · [[Context/Decisions]] · [[System/Schema]]
