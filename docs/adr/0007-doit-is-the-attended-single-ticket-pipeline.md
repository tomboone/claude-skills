# `/personal:doit` is the attended single-ticket pipeline, alongside the loop

`/personal:doit {TICKET_ID}` runs `implementit → shipit → mergeit` inline in one interactive Claude
Code session, taking a single unblocked ticket from planned to merged. It is **not** a replacement
for `plugins/personal/scripts/loop.py` and does not change it — both drive the same state machine,
and both stay.

## Why

The loop's cost profile made it impractical to leave running. In practice a loop run burned a
5-hour token window in four hours or less and pushed the 7-day window close to its limit. Running
the same three commands **by hand** in a Claude Code session — `/personal:implementit`,
`/personal:shipit`, `/personal:mergeit`, then `/clear` before the next ticket — reliably got more
tickets done per token and never hit the 5-hour cap.

Two candidate explanations for the gap, neither yet measured:

1. **Cold starts.** The loop launches each step as its own `claude -p` process. Every step pays a
   full cold context — re-reading the repo, the spec, `CLAUDE.md`, the diff — where an attended
   session already has all of it warm. ADR 0006 measured `implementit` alone at ~4.2M cache-read
   tokens per ticket; `shipit` and `mergeit` each cold-starting on top of that is pure duplication.
2. **Something still unfixed in the headless path** that inflates context beyond the cold-start cost.

`/personal:doit` does not attempt to diagnose which. It just makes the cheaper flow a single
command: the user picks the ticket and clears context between tickets (the two things they were
already doing manually), and the command does the three-phase chaining that was the tedious part.

## What is given up

Unattended operation. The loop's whole value is walking away and coming back to finished work;
`/personal:doit` finishes one ticket and stops, and the user drives the next one. That trade is
the point — the loop's autonomy was costing more tokens than it was worth at current limits.

Also given up: wave discovery. The loop triages `loop-ready` tickets and re-discovers what each
merge unblocks. `/personal:doit` takes exactly one ticket ID, given by the user.

## Design choices worth recording

**It runs the phases inline, not in sub-agents.** Sub-agents would cap peak context, but each would
re-resolve branch, base, PR number, and spec from scratch, and their output tokens are billed too —
reintroducing the cold-start cost this command exists to avoid. The command explicitly forbids
sub-agents and `claude -p` for its phases, and carries resolved state forward between them.

**It checks blockers but not the `loop-ready` label.** `loop-ready` answers "may an unattended wave
pick this up?" — a question with no meaning when a human just typed the ticket ID. Blocker status
still matters, because implementing against an unmerged dependency wastes a full `implementit` pass
regardless of who chose the ticket.

**It keeps every gate the loop keeps.** The mandatory pre-ship `/code-review` pass (ADR 0006), CI as
the merge gate, `MERGE_BLOCKED` rather than a forced merge, and post-ship `/personal:reviewit`
staying manual (ADR 0005) all carry over unchanged. The only thing that changed is who starts each
ticket and where the phases run.

**It emits the same `STATUS:` sentinels.** Nothing consumes them today — the loop does not call
`/personal:doit`. They are kept so the status contract stays uniform across the plugin's commands,
and so a future orchestrator could drive this command without a new parser.
