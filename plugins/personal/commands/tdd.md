---
description: Test-driven development — build a feature or fix a bug test-first, red-green-refactor
---

Run the installed `tdd` skill (from the `mattpocock/skills` marketplace): write a failing test
first, make it pass, then refactor.

## How the pipeline uses it

`/personal:implementit` invokes this **at pre-agreed seams where applicable** — the seams the
ticket's spec or plan already identified — writing the failing test first wherever the repo's own
conventions call for it. It is not a blanket instruction to test-drive every line of a ticket, and
it does not override a repo whose `CLAUDE.md` prescribes something else.

Usable standalone for any TDD session.
