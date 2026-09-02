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

## Interview protocol

Whether run standalone or from `/personal:planit` / `/personal:projectit`, the session asks
**one question at a time** — never a batch:

- One `AskUserQuestion` call, with exactly **one** entry in its `questions` array. Wait for the
  answer before asking the next. Batching questions is bewildering and defeats the point of
  walking the design tree one dependency at a time.
- Give each question **2–4 concrete options** so it's answerable with a single keystroke. Put your
  recommended answer first and suffix its label with `(Recommended)`. The user can always pick
  "Other" to type a free-form answer.
- Drop to plain prose only when the question genuinely has no enumerable answers (e.g. "paste the
  error you're seeing") — and even then, still only one question per turn.
- Look facts up in the codebase rather than asking. Only *decisions* go to the user.
