---
description: Review changes since a fixed point against this repo's standards and the ticket's spec, with the severity scoping the pipeline applies
argument-hint: "<base | PR number>"
---

Run the installed `code-review` skill (from the `mattpocock/skills` marketplace) over the changes
since `<base>`, then apply the two rules below. This wrapper exists because both of those rules are
**this repo's policy about a third-party skill** — the skill is vendored and not ours to edit, and
the policy has to live somewhere both `/personal:implementit` and `/personal:reviewit` can point at.

The skill reports along two axes — **Standards** (does the code follow this repo's documented coding
standards?) and **Spec** (does the code match what the originating ticket asked for?) — in parallel
sub-agents, side by side. It reports; it does not fix.

## Sub-agent model routing

Run the **Standards** sub-agent on **Haiku**. It is checklist matching against documented rules and
a fixed smell list — rubric work, not open-ended judgement.

Keep the **Spec** sub-agent on the **session's own model**. Deciding whether an implementation
honours the intent of a spec is exactly the judgement Standards does not require.

This matters most under `/personal:implementit`, which runs on Opus at high effort and whose
`code-review` pass is the loop's only code review (`docs/adr/0005-the-loop-drops-post-ship-review.md`).
Without the routing, the Standards axis is Opus-priced for checklist work.

## Severity scoping — when a caller acts on the findings

`/personal:implementit` and `/personal:doit` **apply** findings rather than merely reporting them.
When acting on this review's output:

- **Apply** hard violations of a documented repo standard, and genuine defects.
- **Do not refactor** for the Fowler smell heuristics the Standards axis also reports (Mysterious
  Name, Duplicated Code, Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, Shotgun
  Surgery, Divergent Change, Speculative Generality, Message Chains, Middle Man, Refused Bequest) —
  the skill explicitly marks these as *"always a judgement call, never a hard violation."* Act on one
  only when it is directly implicated in a real defect; otherwise list it in the summary and leave
  the code alone.

**Why.** The skill is a read-only reporting tool — no `--fix` flag, no severity field, no confidence
threshold — because it was written for a human to read and exercise judgement over. Blind-applying
everything means applying a dozen judgement-call refactorings (rename, extract a type, replace with
polymorphism, split the module) that the skill deliberately declines to rank. That is both a quality
risk and the loop's single largest token cost — see
`docs/adr/0006-implementit-applies-review-findings-by-severity.md`.

`/personal:reviewit` is the exception: it **reports** findings verbatim into a PR comment and applies
nothing, so the scoping above does not bind it. The model routing still does.
