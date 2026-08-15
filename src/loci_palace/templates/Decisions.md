---
type: context
status: active
updated: {{DATE}}
tags: [context, decisions]
covers: why we decided, why we rejected, settled questions, past choices, what we picked, tools evaluated
---

# Decision Log

One-line dated entries for settled questions. Newest first. **Overwrite-only** — never append, or entries duplicate.

This is the highest-value note in the vault after `CRITICAL_FACTS`. It stops the assistant relitigating things you have already decided, and stops you re-deriving reasoning you have already done. Write an entry the moment a question stops being open.

**Format:** date, the decision, and the reason in one line. The reason matters more than the decision — six months on you will remember *what* you chose and not *why*.

- **{{DATE}}** — Vault created with `loci init`. Structure, schema, and routing follow the defaults in [[System/Schema]].

<!-- Add entries above this line, newest first. Examples of the shape:

- **2026-03-14** — Chose Postgres over Mongo: relational queries dominate and the ops story is simpler for one person.
- **2026-03-02** — No scheduled agents writing to this vault: curated beats generated, and unsupervised rewrites are unreviewable.
- **2026-02-20** — Rejected <tool>: solved a problem we do not have and added a dependency we would have to maintain.

-->

## Related
[[Index]] · [[Context/CRITICAL_FACTS]] · [[System/Schema]]
