# Manual steps are walked one at a time by `/finishit`, now or later

The manual-steps walkthrough used to be one block of text at the end of a `/doit`, `/mergeit` or
no-code `/implementit` report, with every step written out in full. In practice it often pointed at
a runbook ("follow `docs/runbooks/…`") instead of giving the runbook's commands. That happened even
though `manual-steps-convention.md` already said not to. The runbook could be hard to find, or hard
to view usably, from wherever the user was working. And when a command depended on output from an
earlier step, a block written up front could only leave a placeholder.

## Decision

- **A new command, `/finishit {TICKET_ID}`, walks the steps one per response.** It gives the full
  commands for a step, waits for the user's confirmation or pasted output, checks it against the
  step's expected result, and only then gives the next step. Values from earlier output go straight
  into later commands. A step that fails stops the walkthrough until it's resolved. For commands
  that run locally and exit, it suggests Claude Code's `!` prefix, so the output lands in the
  conversation without copy-paste.
- **The closing commands ask "now or later"** instead of writing out the whole walkthrough. They
  still find the steps, using the same sources and rules as before. They post them to the ticket as
  a checklist comment, show a one-line-per-step outline, and ask. *Now* runs `/finishit` inline.
  *Later* stops, pointing at `/finishit {TICKET_ID}`. When there are no steps besides Done, nothing
  is asked. A `--no-merge` run isn't asked either, because its first step, the merge, is in someone
  else's hands.
- **The Linear comment is the progress record.** Each step is a checkbox, and `/finishit` ticks
  each one as it is verified. Running it again resumes at the first unticked step, from a fresh
  context. Claude never ticks the Done line, and never moves the status (ADR 0010 is unchanged).
- **A runbook's execution is broken into its individual steps** in the list. "Run the runbook" is
  no longer an acceptable step.

## Why a separate command

The answer "later" needs an entry point that works after `/clear`. Like `/implementit`, `/shipit`
and `/mergeit`, `/finishit` resolves everything from the ticket ID and on-disk or Linear state. So
it serves both the inline case and the deferred one, and all three closing commands share one
implementation instead of each carrying its own.

## Why it doesn't conflict with "never prompt" mid-`/doit`

ADR 0008 kept the "never prompt" rules because a question in the middle of `/doit` stalls a run
the user expected to finish on its own. The "now or later" question comes after the merge, when
the run *has* finished. It is the last thing `/doit` does, so it stalls nothing.

## Rejected alternatives

- **Keep the single block, and tighten the wording against pointing at runbooks.** The rule already
  existed and wasn't followed reliably. Writing a long runbook out in full at the end of a long run
  is the pressure that produces the shortcut. One step per response removes that pressure, and it
  is the only way a command can use output the user hasn't produced yet.
- **Always walk the steps inline, without asking.** A deploy window, a teammate's approval or a
  production change often can't happen right after the merge. The walkthrough would also run in
  the full context of the implementation, which is the most expensive place to run it.
- **Track progress in a local file.** That wouldn't survive a different machine or session the way
  the ticket comment does, and the ticket is where the user already looks for what's left.

## Cost

A ticket with manual steps now takes one extra Linear comment edit per step, and a back-and-forth
per step instead of one read-through. That is deliberate. Each step is checked before the next
one depends on it.
