# The headless loop is retired; `/doit` is the only orchestrator

**Supersedes the "both stay" half of [ADR 0007](0007-doit-is-the-attended-single-ticket-pipeline.md).**

`plugins/personal/scripts/loop.py` (and `test_loop.py`) are deleted. `/doit` is now the only way
the plugin chains `implementit → shipit → mergeit`.

## Why

ADR 0007 recorded that a loop run burned a 5-hour token window in four hours or less, and that the
same three commands run by hand — then `/doit` — got more tickets done per token. Once `/doit`
existed, the loop's remaining value was unattended operation and wave discovery, and neither was
worth the token cost at current limits. Keeping it meant maintaining a Python orchestrator, its
tests, its Pushover/`.env` plumbing, and a stream of "the loop threads this" caveats in every
command for a path nobody ran.

## Consequences

- **`loop-ready` is no longer applied.** `/projectit` used to put it on every work ticket as the
  loop's triage filter, deselectable at the Phase-3 gate. With no triage there is nothing for it to
  gate, so the label and the deselect step are gone. Tickets that already carry it are unaffected
  and can be cleaned up in Linear at leisure.
- **`repo:<name>` stays.** `/projectit` still applies it; it is a useful Linear filter on its own,
  even though the loop was its only programmatic consumer.
- **`loop_base:` keeps its name.** `/implementit` and `/shipit` still read it as a base-branch hint.
  Renaming it would silently break every repo whose `CLAUDE.md` already sets it.
- **`STATUS:` sentinels stay.** `/doit` reads the phase sentinels to decide whether to continue, and
  they keep the status contract uniform across commands.
- **The "never prompt" rules stay.** They were written for headless runs, but they matter just as much
  mid-`/doit`, where a question in phase 2 stalls a run the user expected to finish on its own.
- **ADR 0005's decision carries over to `/doit`.** Post-ship `/reviewit` remains manual-only; the
  pre-ship `/code-review` inside `/implementit` is still the pipeline's only automatic review.
