---
description: Grill the user relentlessly about a plan, design, or decision to stress-test it before building
---

Run the installed `grilling` skill (from the `mattpocock/skills` marketplace) on the plan, design,
or decision at hand.

## How the pipeline uses it

`/personal:planit` (Step 4) and `/personal:projectit` (Phase 1) both run a grilling session
**alongside `/personal:domain-modeling`**, framed on the ticket or project context they have already
gathered. Neither skill produces a spec file on its own — the calling command writes the spec once
the session reaches shared understanding.

Usable standalone on any plan you want stress-tested.
