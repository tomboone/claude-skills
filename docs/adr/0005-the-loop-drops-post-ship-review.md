# The loop is implement → ship → merge; post-ship review is manual-only

**Supersedes the loop-facing half of [ADR 0002](0002-two-pass-code-review-is-intentional.md).**

The loop used to run `implementit → shipit → (reviewit ↔ addressit)* → mergeit`, with the review ↔ address alternation bounded by `--max-rounds`. It now runs `implementit → shipit → mergeit`.

## Why

`/implement` already ends with its own `/code-review` pass. ADR 0002 argued that the post-ship `/personal:reviewit` pass earned its keep as "the public, durable gate." In practice the loop's economics changed:

- `implementit` now runs on **Opus at high effort** rather than Sonnet. It works from a spec, not from a pre-written plan that only needs transcribing, so the model doing the writing is also the strongest model in the pipeline — and its pre-ship review-and-fix pass is correspondingly better than the Sonnet post-ship pass that was second-guessing it.
- The `reviewit ↔ addressit` cycle was 2–5 extra headless invocations per ticket, each cold-starting its own context, for a verdict that was usually `APPROVED` on the first round.
- The two failure modes it introduced — `PUSHED_BACK` impasses and rounds-exhausted stalls — were the loop's most common `NEEDS_HUMAN` dispositions, and they stalled tickets whose code was fine.

## What this does *not* change

The pre-ship `/code-review` inside `/implement` stays, and ADR 0002's closing instruction still holds with more force than before: **do not remove it.** It is now the only code review in the loop. What it *acts on* was later narrowed to hard violations and genuine defects — see `0006-implementit-applies-review-findings-by-severity.md`.

`/personal:reviewit` and `/personal:addressit` remain as commands. They're still the right tool for reviewing a PR by hand, and the per-ticket flow documented for humans still includes them. They are simply no longer orchestrated.

## Consequence for `/personal:mergeit`

`mergeit` used to *require* a `## Code Review` comment with Assessment "Ready to merge", and emitted `MERGE_BLOCKED` when none existed. Since loop-driven PRs now legitimately have no such comment, that gate is softened: an explicit **"Needs changes"** still blocks, but a **missing** review comment no longer does — CI is the gate. A hand-run `/personal:reviewit` still produces a verdict `mergeit` will honor.
