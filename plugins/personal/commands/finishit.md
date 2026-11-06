---
name: finishit
description: Walk through a Linear ticket's remaining manual steps one at a time — exact commands, waiting for your confirmation or pasted output before each next step
argument-hint: "{TICKET_ID}"
---

**CRITICAL: Follow every step in order. Present one manual step per response, never several.**

This is the step-by-step walkthrough for what's left to close a ticket after its code has merged
(or, for a no-code ticket, instead of code): deploys, migrations, secrets, external-service setup,
executing a delivered runbook. The rules for *finding* the steps and *writing* each one live in
`plugins/personal/manual-steps-convention.md`. This command is the part where the user carries
them out, one at a time, with Claude checking each result before moving on.

It runs two ways:

- **Inline**, when `/doit`, `/mergeit` or `/implementit` asked "now or later" and the user picked
  now. The step list and the Linear comment's ID are already in context. Skip Step 0 and don't
  re-fetch anything.
- **On its own**, as `/finishit {TICKET_ID}` in a fresh session. It resolves everything from the
  ticket ID, and it resumes where an earlier walkthrough stopped.

**All GitHub operations go through the `gh` CLI** — never a GitHub MCP server. See
`plugins/personal/github-cli-convention.md`.

## Step 0 — Load the step list (skip when running inline)

1. Fetch `{TICKET_ID}` via the Linear MCP. If it doesn't resolve, stop, say so, and emit
   `STATUS: BLOCKED` as the very last line. If it is already in a completed (Done) state, say so
   and emit `STATUS: FINISHED`. The user has already judged the ticket finished.
2. Read its comments (`list_comments`) and take the **most recent** one headed
   `## Manual steps to close {TICKET_ID}`. Its checklist is the step list. Ticked lines are done,
   and lines carrying a skip note were skipped. Keep the comment's ID for updates.
3. **No such comment** (it predates this command, or the closing run never got that far): build
   the list yourself, following the convention's "Find the steps" section. For the diff, find the
   ticket's PR with `gh pr list --state all --search "{TICKET_ID}" --json number,state,headRefName,title,url`
   and read it with `gh pr diff <number>`. If that PR is still open, step 1 is getting it reviewed
   and merged. Then post the comment exactly as the convention specifies.
4. **Nothing left but Done**: say so in one line, give the Done step (Step 4), and emit
   `STATUS: FINISHED`.

## Step 1 — Show where things stand (once)

Print the checklist in one compact block, marking done steps `✓` and skipped ones `–`, then say
which step you're starting at, e.g. `Starting at step 3 of 5 — steps 1–2 were verified on an
earlier run.` If the user wants a done step redone, they can say so. Then go straight to Step 2 in
the same response. Don't ask whether to begin; choosing "now", or typing the command, was the
answer to that.

## Step 2 — Present one step

Give **one** step, written per the convention's "Write each step so it can be followed without
guessing":

```
### Step 3 of 5 — Run migration 0042_add_widgets
Why:    the new widgets table doesn't exist in production until this runs.
Where:  Deployed — production (fly), via `fly ssh console -a acme-api`
```

followed by the fenced command block, then `Expect:` and what success looks like.

- **Re-ground the step now.** Re-read the source the step comes from: the runbook section, the
  `Makefile` target, the deploy config. Don't copy the comment's text forward unchecked. The
  comment may have been written at the end of a long run, or before something changed.
- **Fill in what earlier steps revealed.** If an earlier step printed a revision ID, hostname,
  instance name or URL, put the real value in this step's command. Never leave a `<PLACEHOLDER>`
  for something already in the conversation. If a value the command needs can only come from a
  command the user hasn't run yet, make that command its own step first.
- **Secrets stay out of the chat.** Write the command so the secret is read from a prompt or stdin.
  Never ask the user to paste a secret.

End the response with one short line saying what you need back. Then **stop and wait**:

- **A command step:** "Run it and paste the output." When the command runs on this machine and
  exits on its own, add: "In Claude Code you can type `! <command>` instead, so the output lands
  here directly." Don't suggest `!` for interactive sessions (an `ssh` or `fly ssh console` shell,
  a database console). The user runs those in their own terminal and pastes the result.
- **A local, non-destructive command:** also offer "or say **run it** and I'll run it here".
- **A UI step:** "Say **done** once it's saved, and tell me what <the check> shows."
- **Always:** "**skip** to skip this step, **stop** to pause and resume later."

Don't present the next step in the same response, however trivial it looks. Seeing each result
before the next step is the point of the walkthrough.

## Step 3 — Check the result, then move on

When the user replies:

- **Output matches what was expected:** tick the step's box in the Linear comment (`save_comment`
  with the comment's ID, `- [ ] 3.` → `- [x] 3.`). Confirm in one line, then present the next step
  (Step 2) in the same response.
- **"run it":** run the command yourself, only if it is local and non-destructive. Show the output
  and judge it the same way. For anything deployed or hard to reverse, run it only if the user asks
  for that specific step, and confirm the exact command and target before you do.
- **"done" with nothing to check against:** if the step's check is a read-only command you can
  run locally, run it. Otherwise give the check command and ask for its output. Don't tick a step
  on a bare "done" when it has an observable check. For a UI step, the user describing what they
  see counts as the check.
- **Output doesn't match, or the command failed:** don't move on. Say exactly what in the output
  differs from what was expected and the most likely cause, then give one diagnostic or fix command
  and wait for its result, same as a step. Steps that depend on this one wait until it's resolved.
  If it can't be resolved in this session, pause (Step 5) and say what's blocking it.
- **The output reveals more work** (a second pending migration, a config key the diff didn't
  show): add it as a new step at the right point in the list. Update the comment's checklist and
  add its `###` section, and say you did.
- **Pasted output contains a secret** (token, key, password, connection string with credentials):
  don't repeat it, and never write it into the comment. Point it out. If it's a production
  credential, suggest rotating it, since it is now in the conversation transcript.
- **"skip":** append `(skipped <YYYY-MM-DD>: <reason, if given>)` to that line in the comment,
  leaving the box unticked. If a later step depends on the skipped one, say which, then continue.
- **"stop":** go to Step 5.

## Step 4 — Finish

When every step is ticked or skipped, update the comment. Add
`**All steps verified <YYYY-MM-DD>.**` under its heading, or
`**Steps verified <YYYY-MM-DD>; skipped: 2, 4.**` when any were skipped. Then give the last step:

> **Last step — move {TICKET_ID} to Done** in Linear (`<ticket URL>`), once every step above is
> verified.

If anything was skipped, say plainly that the ticket isn't finished until those steps are dealt
with. Whether to move it anyway is the user's call. **Never move the status yourself, and never
offer to** (ADR 0010).

Then, as the **very last line of your response**, emit `STATUS: FINISHED`.

## Step 5 — Pause

The comment's ticks are already current, because each was written as its step was verified. Say
where things stand and how to resume:

```
Paused at step 3 of 5 (run migration 0042_add_widgets).
Resume with: /finishit {TICKET_ID}  — it picks up from step 3.
```

If a failed step is the reason for pausing, say in one line what has to be true before resuming.
Then, as the **very last line of your response**, emit `STATUS: PAUSED`.

## Token discipline

- One step per response keeps each turn small. Don't reprint the whole checklist after Step 1. The
  `Step N of M` header is enough to show progress.
- Re-read only the source section for the step at hand, not the whole runbook every turn.
- Never re-fetch the ticket or the comment mid-walkthrough. Keep the comment ID and update it
  in place.
