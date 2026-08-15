---
type: context
status: active
updated: {{DATE}}
tags: [context, critical, boot]
covers: who am I, my name, my role, my preferences, my constraints, how I like to work, my stack, my tools
---

<!-- TEMPLATE-UNFILLED: delete this line once you have filled this note in.
     The linter treats it as an error until removed, on purpose: an unfilled
     placeholder is worse than an absent fact, because the assistant will
     believe it and the manifest will route to it confidently. -->

# Critical Facts

**This file is read at the start of every session.** It is the single most
important note in the vault. Everything else is found through the manifest;
this is always loaded.

**Budget: aim for 150 tokens — roughly 12 short lines.** If a fact is not worth
spending part of every future conversation on, it belongs in another `Context/`
note or a project note instead.

Delete every line you do not fill in.

---

- **Name / what to call you** —
- **Where you are** — city, country, timezone if it matters
- **Role** — job title and what you actually spend your time on
- **What to call the assistant** — if you want a name for it
- **Languages** — and which one you want replies in
- **Units** — metric or imperial
- **Stack / domain** — the 5–8 technologies or subject areas that come up most
- **Shell** — bash, zsh, fish. Affects every command you are given.
- **Hard constraints** — dietary, accessibility, legal, budget. Things that
  should never have to be re-explained.
- **Working style** — how you want to be talked to. Be specific: "give me
  trade-offs, not recommendations" is useful; "be helpful" is not.
- **Vault access** — how the assistant reaches this vault, in one line

---

## How to write a good line

Write facts that **change the answer**, not facts that describe you.

| Weak | Strong |
|---|---|
| "I like clean code" | "Reject solutions that add a dependency for something stdlib can do" |
| "I'm a developer" | "Tech lead; I review more than I write, so lead with the trade-off" |
| "I'm health conscious" | "No pork, no alcohol — never suggest either" |
| "I use a Mac" | "Shell is fish — `set x`, not `x=`" |

A useful test: **would a wrong answer to this question waste your time?** If
not, leave it out.

## What does NOT belong here

- Anything that changes month to month — that is a project note
- Long background or history — a separate `Context/` note
- Anything you would not want loaded into every single conversation

## Related
[[Index]] · [[System/Schema]]
