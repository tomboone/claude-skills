# Running code review twice per ticket (pre-ship and post-ship) is intentional, not redundant

> **Partially superseded by [ADR 0005](0005-the-loop-drops-post-ship-review.md).** The loop no
> longer runs the post-ship pass — it is `implementit → shipit → mergeit`, and `/personal:reviewit`
> is a manual command now. The part of this ADR that still stands, and stands harder, is the closing
> instruction: **do not remove the pre-ship `/code-review` pass inside `/implement`.** It is the
> only code review the loop performs. Read the rest as the history of why the second pass existed.
>
> **Also amended by [ADR 0006](0006-implementit-applies-review-findings-by-severity.md).** The
> "blind auto-apply is safe and desirable" claim below does not survive: `/code-review` has no
> `--fix` flag, and its Standards axis reports judgement-call smell heuristics that must not be
> auto-refactored. The pass now applies findings scoped by severity.

`/implement` runs `/code-review --fix` internally before a PR exists (pre-ship review); `/personal:reviewit` then runs `/review` against the opened PR (post-ship review) — the same underlying review logic, usually against the same diff. At a glance this looks like paying for the same review twice.

We kept both on purpose. They do different jobs:

- **Pre-ship** is private and auto-fixing (`--fix`). There's no adversarial party yet, so blind auto-apply is safe and desirable — it catches and fixes obvious findings before they ever reach a human or the loop's state machine.
- **Post-ship** is the public, durable gate: it produces the `## Code Review` PR comment and the `STATUS` sentinel that `loop.py` and `/personal:mergeit` structurally depend on. It cannot be replaced by the pre-ship pass because that pass runs before the PR exists.

The apparent duplication is the *cheap* path, not the wasteful one: when pre-ship review already fixed everything, post-ship review comes back clean almost immediately and `loop.py` skips the `addressit` round entirely. The alternative — skip pre-ship review, rely solely on post-ship — would force every ticket through at least one full `reviewit → addressit → reviewit` round-trip (three separate headless invocations) instead of occasionally zero.

Do not remove the pre-ship `/code-review --fix` pass inside `/implement` to "avoid running review twice" — that trade goes the wrong way.
