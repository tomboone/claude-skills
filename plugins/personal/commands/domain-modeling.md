---
description: Build and sharpen a project's domain model — terminology, CONTEXT.md, and ADRs
---

Run the installed `domain-modeling` skill (from the `mattpocock/skills` marketplace) to clarify
terms, identify bounded contexts, and capture decisions as they crystallize.

## How the pipeline uses it

`/personal:planit` (Step 4) and `/personal:projectit` (Phase 1) run this **alongside
`/personal:grilling`**, updating `CONTEXT.md` and any ADRs inline as decisions settle rather than
deferring them to a write-up pass.

Usable standalone whenever codebase terminology, a `CONTEXT.md`, or an ADR needs work.
