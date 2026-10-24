# `/projectit` flags spec gaps with a `planit` label, and `/implementit` honours it

`loop-ready` used to mark every `/projectit` ticket as safe to implement off the project-wide spec
([ADR 0004](0004-implementit-falls-back-to-the-project-spec.md)), and the user could untick it at the
Phase-3 gate. [ADR 0008](0008-retire-the-headless-loop.md) removed the label along with the loop. That
left the opposite question unanswered: which tickets does the project spec *not* cover?

## Decision

- **`/projectit` checks every drafted work ticket** against the project-wide spec plus its
  milestone's shared contracts, using `/planit`'s Step 3 standard: what and why, acceptance
  criteria, key decisions, and explicitly deferred unknowns. Any ticket that falls short gets the
  `planit` label. The reason is shown at the Phase-3 gate, where the user can override the flag or
  close the gap in the spec on the spot.
- **`/implementit` won't fall back to the project spec on a labelled ticket.** It stops with
  `NO_PLAN`, so `/doit` stops too, and both tell the user to run `/planit`.
- **`/planit` removes the label** once it has judged the ticket implementation-ready or written its
  per-ticket spec, even when it decides the project spec was enough after all.

## Why there's a check at all

`/projectit` can't guarantee full coverage. Project-shaping is breadth-first by design: it shapes a
whole project in one pass and deliberately leaves per-ticket detail alone. ADR 0004's fallback trusts
the spec's coverage of each ticket without anyone checking it. The check is that missing judgement,
moved forward to the one moment when the whole spec and every ticket are in context together.

## What it doesn't catch

Dependency drift ([ADR 0003](0003-planit-keeps-its-per-ticket-gate.md)): a blocker that ships
differently from what the spec assumed. This can't be known until the blocker merges, so the check
doesn't flag tickets just for having `blockedBy` relations. The label means "the spec has a gap
today", not "this ticket is risky".

## Rejected alternatives

- **Close every gap inside `/projectit`.** That would turn one breadth-first pass into a per-ticket
  grilling for every weak ticket, which is `/planit`'s job. `/planit` also does it better later,
  because by then it can read the shipped code of merged blockers. The gate still lets the user close
  a small gap on the spot when the answer is quick.
- **An advisory label that nothing reads.** It would go stale the moment `/planit` ran, and nothing
  would stop `/doit` from implementing a flagged ticket off a spec already judged insufficient.
  Enforcement in `/implementit` plus removal in `/planit` keeps the label true.
