# Memory vault

This repository is a structured memory vault. The operating contract — stance,
routing, and write rules — lives in `{{VAULT_DIR}}/System/BOOT.md` and is loaded
globally via an import, so it is not repeated here.

`{{VAULT_DIR}}/System/connect.py` installs that import. Run it once per machine.

## Why this file is short

Duplicating the contract here would create a second copy that drifts from the
first. One source, imported. If you are reading this and do not have the
contract loaded, read `{{VAULT_DIR}}/System/BOOT.md` now.

## Working in this repository

Regenerate the routing index after adding or renaming a note:

```
python3 {{VAULT_DIR}}/System/manifest.py
```

Validate before committing:

```
python3 {{VAULT_DIR}}/System/lint.py             # schema, duplication, dead links, orphans
python3 {{VAULT_DIR}}/System/manifest.py --check # manifest freshness
```

Both run automatically via the pre-commit hook, which also regenerates the
manifest — refusing when it cannot do so safely, such as during a partial
commit where the regenerated index would describe notes the commit does not
contain.

Set routing keywords surgically rather than rewriting a file:

```
python3 {{VAULT_DIR}}/System/covers.py "<path>" "terms, more terms"
```

Check that no personal content has leaked into the portable tooling:

```
bash {{VAULT_DIR}}/System/audit.sh
```

## Machinery and content

`{{VAULT_DIR}}/System/`, `{{VAULT_DIR}}/Views/` structure, `{{VAULT_DIR}}/Index.md`,
and this file are **machinery** — portable to other machines, and must contain no
personal content. Use generic language when editing them: no names, no employer,
no specific project titles.

`{{VAULT_DIR}}/Context/`, `{{VAULT_DIR}}/Projects/`, `{{VAULT_DIR}}/Sessions/`,
`{{VAULT_DIR}}/Archive/`, and `Views/manifest.tsv` are **content** — they never
leave this machine.

## Environment

Machine-specific settings live in `.loci-local.json` (gitignored). See
`.loci-local.json.example`. Paths here are relative to the repository root;
scripts resolve it with `git rev-parse --show-toplevel`.
