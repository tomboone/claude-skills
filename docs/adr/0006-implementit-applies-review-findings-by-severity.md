# `/implementit` applies review findings by severity, not blindly

**Amends [ADR 0002](0002-two-pass-code-review-is-intentional.md) and [ADR 0005](0005-the-loop-drops-post-ship-review.md).**

`/personal:implementit` Step 5 used to direct `/implement` to run its internal `/code-review` pass "with `--fix` — auto-apply findings rather than merely reporting them." It now directs it to apply **hard violations of documented standards and genuine defects**, and to leave the Fowler smell heuristics alone unless one is directly implicated in a real defect.

## Why

Two things were wrong with the old directive.

**`--fix` is not a flag.** `/code-review` is a read-only reporting skill: it spawns a Standards sub-agent and a Spec sub-agent, prints their findings under two headings, and explicitly instructs *"Do not merge or rerank findings."* There is no `--fix` argument, no severity field, and no confidence threshold anywhere in it. The model could only read the directive as prose, and the prose said "auto-apply findings."

**What it was auto-applying included judgement calls.** The Standards axis always carries a baseline of twelve Fowler code smells, which the skill itself brackets as *"Always a judgement call... never a hard violation."* Each ships with a prescribed remedy — rename it, extract the shared shape, give the concept its own type, replace with polymorphism, split the module. Blind auto-apply therefore meant performing a dozen categories of speculative refactoring on every ticket, from a review that deliberately refuses to rank its own findings. (The separate marketplace `code-review` plugin filters at 80 confidence for exactly this reason; this skill has no such filter, because it was designed for a person to read.)

## Cost — the hypothesis that motivated this change, and how it failed

This change was originally made on a cost argument. **That argument did not survive measurement.** The correctness argument above stands on its own; the cost argument is recorded here so it isn't re-litigated.

The hypothesis: `implementit` was the loop's dominant expense, and the refactor cascade was why. A six-ticket run measured `implementit` at **$29.17 of $31.18 total — 93.5%**, with 25.5M cache-read tokens (~4.2M per ticket) against only ~94k cache-write and ~31k output per ticket. That read-to-write ratio is the signature of many turns over a large context, which is what a cascade of accepted refactorings would produce. The supporting observation: running `/implement` by hand at the same model and effort, with `/clear` between tickets, cost noticeably less — and still fixed the problems it found.

The first ticket run after this change (NEU-747, plugin 0.16.2) came back at:

| | 6-ticket average, before | NEU-747, after |
|---|---|---|
| `implementit` cost | $4.86 | **$4.87** |
| cache read | ~4.2M | 4.14M |
| output tokens | ~31.5k | 28.7k |

No movement. One ticket is not conclusive — the prior six ranged $3.18–$7.98, so per-ticket variance is wide — but there is no signal in the predicted direction, and NEU-747 landed on the old mean almost exactly.

So the smell cascade was **not** the cost driver. The remaining explanation is the boring one: this is what Opus at high effort costs to run a full agentic implement against a repo of this size, and the ~4M cache-read tokens per ticket are inherent to a long multi-turn session over a large context rather than to any one instruction. Treat `implementit` cost as a property of the model/effort choice, not as a bug to be prompt-engineered away — if it needs to come down, the lever is model or effort routing (which re-opens the ADR 0005 bet), not the review directive.

## What this does not change

The pre-ship review pass stays, and stays mandatory — ADR 0005 made it the only code review in the loop, and that is unchanged. This ADR narrows *what the pass acts on*, not whether it runs.

ADR 0002's claim that blind auto-apply is "safe and desirable" because there is no adversarial party to push back against does not survive. It was reasoning about a review that emits things worth applying; against a smell baseline, blind auto-apply means applying judgement calls without the judgement. The half of that ADR that still stands is the instruction never to remove the pre-ship pass.
