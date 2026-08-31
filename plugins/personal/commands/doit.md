---
description: Take one unblocked Linear ticket from planned to merged — implement → ship → merge — in a single interactive session
argument-hint: "{TICKET_ID} [--base <branch>] [--no-merge]"
---

**CRITICAL: Follow every step in order. Do not skip or reorder steps. Do not jump ahead to
implementation.**

This is the **attended** counterpart to `plugins/personal/scripts/loop.py`: the same
`implementit → shipit → mergeit` state machine, run inline in one Claude Code session on one ticket,
instead of headlessly across a wave via `claude -p`. Run it, let it finish, `/clear` (or `/compact`),
then run it again on the next ticket. See `docs/adr/0007-doit-is-the-attended-single-ticket-pipeline.md`.

**Execute the phases in this session.** Do not spawn sub-agents for them, do not shell out to
`claude -p`, and do not re-launch the pipeline any other way. Running all three phases in one context
is the entire point: phase 2 and phase 3 reuse state phase 1 already resolved (branch name, base,
spec, diff), which is what makes this cheaper than three cold-started headless runs.

Invoke each phase with the **Skill tool** — `Skill({skill: "personal:implementit"})` and so on. A
command loaded that way is injected into *this* conversation and runs inline, in this context, with
everything the earlier phases resolved still visible; it does not start a sub-agent. That is what
makes the warm-context saving real rather than aspirational. The **Overrides** in each phase below
take precedence over anything the loaded command says about stopping or handing off.

## Step 0 — Preflight: confirm the ticket is workable

Fetch `{TICKET_ID}` via the Linear MCP. Then:

1. **Ticket exists.** If it doesn't resolve, stop and say so. Emit `STATUS: BLOCKED`.
2. **Blockers are done.** Check the ticket's `blockedBy` relations. If any blocking issue is not in a
   `Done`/completed state, stop — do **not** start implementing. Name each unfinished blocker (ID,
   title, current status) and emit `STATUS: BLOCKED` as the very last line.
3. **Do not require the `loop-ready` label.** That label is `loop.py`'s triage filter — it answers
   "may an unattended wave pick this up?", which is not the question here, because you picked the
   ticket by hand. A hand-created ticket with no label is a perfectly valid `/personal:doit` target.
   Do not check for it and do not warn about its absence.

Say in one line what you're about to do (ticket ID, title, and whether merging is in scope), then go
straight into phase 1 — no confirmation gate.

## Step 1 — Phase 1: implement

Invoke `personal:implementit` via the Skill tool for `{TICKET_ID}`, threading `--base <branch>`
through if `/personal:doit` was invoked with it.

**Overrides.**
- Its closing instruction to "tell the user to clear context and run `/personal:shipit`" does **not**
  apply — you are the thing that runs `/personal:shipit`, immediately, in this same context.
- Its "Do not invoke `/personal:shipit`" line is likewise overridden here. It exists to keep
  `implementit` single-purpose when run standalone; `/personal:doit` is the composed pipeline.
- Everything else stands unchanged — in particular the pre-ship `/personal:code-review` pass and its
  severity scoping (ADR 0006) are **mandatory** and must not be skipped or trimmed for speed.

**Outcomes.**
- Emitted `STATUS: NO_PLAN` → stop the whole run. Report which sources were checked, tell the user to
  run `/personal:planit {TICKET_ID}`, and emit `STATUS: NO_PLAN` as your very last line.
- Did not reach `STATUS: IMPLEMENTED` for any other reason (error, ambiguity, stopped early) → stop.
  Report what happened and emit `STATUS: FAILED`.
- Reached `STATUS: IMPLEMENTED` → continue to phase 2. **Do not** echo the phase's `STATUS:` sentinel
  as a standalone final line of its own; only the run-level sentinel in Step 4 is emitted.

Carry forward, without re-deriving them later: the **branch name**, the resolved **base**, and which
**spec/plan** files were used.

## Step 2 — Phase 2: ship

Invoke `personal:shipit` via the Skill tool for `{TICKET_ID}`, threading the same `--base <branch>`
if it was supplied.

**Overrides.**
- Its Step 1 guard rails (not on main, branch name contains the ticket ID) are already satisfied by
  phase 1, which just created that branch. Confirm from context in one line; don't re-interrogate git
  for it.
- Its Step 5 base resolution is already answered — reuse the base carried forward from phase 1.
  Only run the `release/*` discovery in Step 5 if phase 1 somehow left the base unresolved.
- Its closing "tell the user to clear context and run `/personal:mergeit`" does **not** apply.
- Do **not** run `/personal:reviewit` — the post-ship review remains manual and opt-in (ADR 0005),
  same as under the loop. If a PR warrants it, the user runs it by hand after this command finishes.

**Outcomes.**
- No PR created → stop, report why, emit `STATUS: FAILED`.
- PR created → capture the **PR number**, **PR URL**, and **base branch**, and continue. If
  `--no-merge` was passed, skip phase 3 and go to Step 4.

## Step 3 — Phase 3: merge

Invoke `personal:mergeit` via the Skill tool for `{TICKET_ID}`.

**Overrides.**
- Its Step 1 PR resolution is already answered — use the PR number and base captured in phase 2.
  Do not re-resolve them through `pr-resolution-convention.md`.
- Its Step 2 review-verdict check still applies as written: an explicit "Needs changes" verdict
  blocks; a missing `## Code Review` comment does not.
- Its CI handling (Steps 3a–3c) applies **in full, unchanged**. Do not shorten the waits and do not
  merge past an unregistered or failing check. CI is the merge gate.

**Outcomes.**
- `STATUS: MERGE_BLOCKED` → stop. Report the blocking reason (failed check + log URL, no check
  registered, or a "Needs changes" verdict) and emit `STATUS: MERGE_BLOCKED` as your very last line.
  The branch and PR are left intact for the user to pick up.
- Merged → continue to Step 4.

## Step 4 — Report

Print one compact block — no phase-by-phase retelling, the user watched it happen:

```
{TICKET_ID} — <ticket title>
Branch:  <branch name>  (base: <base>)
PR:      <PR URL>  (<merged | open>)
Merge:   <commit sha>, <squash|merge> into <base>   # omit when not merged
Next:    /clear, then /personal:doit <next ticket>
```

If the pre-ship review left any judgement-call smells unfixed (ADR 0006), list them here in one
line each — this is the one place the user sees them, since the PR is already merged.

Do not touch the Linear ticket's status; the GitHub↔Linear connector owns that.

Then, as the **very last line of your response**, emit exactly one run-level sentinel:

| Situation | Sentinel |
|---|---|
| Merged | `STATUS: MERGED` |
| PR open, `--no-merge` was passed | `STATUS: READY_FOR_REVIEW` |
| Merge blocked (CI, or "Needs changes") | `STATUS: MERGE_BLOCKED` |
| No design context found | `STATUS: NO_PLAN` |
| Unmet blocker, or ticket not found | `STATUS: BLOCKED` |
| Anything else stopped the run | `STATUS: FAILED` |

## Flags

| Flag | Effect |
|---|---|
| `--base <branch>` | Force the branch/PR base. Threaded to both `/personal:implementit` and `/personal:shipit`. Without it, phase 1 resolves the base itself (`loop_base:` hint → current integration branch → repo default). |
| `--no-merge` | Stop after the PR is opened. Mirrors `loop.py`'s `--merge` being opt-in — use it on repos where PRs need team approval. |

## Token discipline

The reason this command exists is that three phases in one warm context cost less than three cold
`claude -p` runs. Protect that:

- **Never re-read a file you already read** in an earlier phase (spec, plan, PR template, `CLAUDE.md`).
- **Never re-derive resolved state** — branch, base, PR number, project type. Each is resolved once
  and carried forward, per the Overrides above.
- **Don't re-summarize** the implementation for the ship phase; the diff and the plan are already in
  context, so `shipit`'s commit message and PR body come straight from what you know.
- Keep phase transitions to one line. The final report in Step 4 is the only summary.
