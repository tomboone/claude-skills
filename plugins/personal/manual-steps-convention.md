# Manual-steps convention

A merged PR is not the same thing as a finished ticket. Migrations still have to be run against a
deployed database, secrets still have to be set, a runbook the ticket delivered still has to be
carried out, and a no-code ticket is nothing *but* manual work. This convention makes the command
that ends a ticket's run say, unprompted, exactly what is left — and then walk the user through it
one step at a time, now or later.

**Used by:**

- **The closing commands** — `/mergeit` (after a successful merge), `/doit` (at the end of every run
  that produced work or found the ticket to be no-code), and `/implementit` (when it stops with
  `STATUS: NO_CODE` outside `/doit`). They find the steps, record them on the ticket, and ask
  whether to work through them now. A command running under `/doit` leaves all of this to `/doit`,
  so it happens exactly once.
- **`/finishit`** — the step-by-step walkthrough itself. It runs inline when the user answers
  "now", or on its own later, from a fresh context, by ticket ID.

## Closing a run

A closing command does these in order:

1. **Find the steps** (below).
2. **No steps besides Done?** End the report with a `### Manual steps to close {TICKET_ID}`
   section holding one line saying so and why, e.g.
   `No other steps — no migrations, config or deploy steps; main deploys automatically on merge.`,
   followed by the Done step. Post no comment and ask nothing. The user should never have to ask
   whether anything is left.
3. **Otherwise, post the Linear comment** (below), then end the report with a
   `### Manual steps to close {TICKET_ID}` section that is an **outline only**: one numbered line
   per step — what it does and where it runs — then the Done step, then the comment's URL. No
   command blocks here. The full detail lives in the comment and is given step by step by
   `/finishit`. Writing every step out in full at the end of a long run is what produced
   walkthroughs that said "follow the runbook" instead of giving its commands.
4. **Ask "now or later"** with `AskUserQuestion`, for example: *"{TICKET_ID} has 4 manual steps
   left (deploy, migration, secret, smoke test). Work through them now, one at a time?"*
   - **Now — walk me through them**: invoke `finishit` via the Skill tool for `{TICKET_ID}`. It
     runs inline in this context. Its Step 0 is already answered, because the step list and the
     comment's ID are in context. `/finishit`'s `STATUS:` sentinel then ends the response in
     place of the closing command's own. The report above already records how the run ended.
   - **Later — I'll run `/finishit` myself**: say
     `Next: /clear, then /finishit {TICKET_ID} when you're ready — the steps are on the ticket.`
     and end with the closing command's own sentinel. Later is also the cheaper choice:
     `/finishit` starts from a fresh context instead of carrying the whole run.

   **Exception — the PR isn't merged** (a `/doit --no-merge` run): don't ask. The first step is
   getting the PR reviewed and merged, and that is in someone else's hands. Say
   `Next: once PR #<n> merges, run /finishit {TICKET_ID}` and end with the command's sentinel.

## The last step is always "move it to Done"

Merging moves the ticket to **Merged**, not Done
([ADR 0010](../../docs/adr/0010-done-means-the-manual-steps-are-finished.md)). So every outline,
comment and walkthrough ends with:

> **Last step — move {TICKET_ID} to Done** in Linear (`<ticket URL>`), once every step above is
> verified.

For a `--no-merge` run, the PR has to merge first. For a no-code ticket, the ticket never had a PR, so
it is still in whatever status it started in. Either way, moving it to Done is the user's step.
**Never move the status yourself**, and never offer to, even after the user reports the steps
are done.

## Find the steps — check, don't assume

Work through every source below before deciding the list is complete:

1. **The ticket.** Its description, acceptance criteria and any `Definition of done` checkboxes. Every
   item the merged code does not satisfy by itself is a candidate manual step.
2. **The spec/plan.** Rollout, deployment, migration, configuration, data backfill and "after merge"
   sections.
3. **The diff.** Look for things that do nothing until someone acts on them:
   - new environment variables, config keys or secrets;
   - database migrations;
   - infrastructure-as-code changes that need an `apply`;
   - new scheduled jobs, queues or webhooks;
   - dependency or tooling installs other machines need;
   - feature flags that start off;
   - registrations with external services (OAuth apps, DNS, API keys);
   - data fixes or backfills;
   - scripts, runbooks or docs the ticket expects someone to *execute*.
4. **Deployment.** Read `.github/workflows/` (and any deploy config the repo documents) to decide
   whether merging into this base deploys automatically. If it doesn't, deploying is step 1, written
   out with its exact command.
5. **`--no-merge` runs.** The first steps are getting the PR reviewed and merged — the PR URL, and
   `/mergeit {TICKET_ID}` or the exact `gh pr merge` command — followed by everything above.

**A runbook is not done when it merges.** If the ticket delivers a runbook, script or procedure whose
*execution* is the ticket's goal, carrying it out is the manual work. **Break it into its own
steps in the list**, one entry per runbook step, each with its commands. "Run the runbook" is never
a step, and neither is a pointer to the file. The user may not be able to find it, or view it
usably, from where they are working.

## Write each step so it can be followed without guessing

This applies to every step in the comment and to every step `/finishit` presents. Number the steps
in the order they must happen. For each one give:

- **What and why**, in one line.
- **Where it runs**, exactly one of:
  - `Local — <absolute repo path>` for this machine;
  - `Deployed — <environment/host>`, plus the exact command that gets you there (`ssh …`,
    `kubectl exec …`, `fly ssh console -a …`, a cloud shell);
  - `UI — <service>`, with the starting URL where it's knowable.
- **The exact commands**, in a fenced block, ready to paste. Fill in every value you can know: file
  paths, migration names, env-var names, the branch, the PR number, the app or cluster name. Use a
  `<PLACEHOLDER>` only for values you cannot know (secrets, credentials, a value the user chooses,
  output of an earlier step), and say where each one comes from: "the `STRIPE_WEBHOOK_SECRET` shown
  in Stripe → Developers → Webhooks → *endpoint* → Signing secret", or "the revision ID printed by
  step 2".
- **For a UI step**, the click path with the exact menu labels, field names and values to enter. Not
  "configure the webhook in Stripe".
- **How to verify it worked**: a command, with the expected output, or the observable result.

**Ground every command in the repo.** Take commands from the repo's `Makefile`, `package.json`
scripts, `justfile`, `pyproject.toml`, README, `CLAUDE.md`, deploy configs, or the runbook itself. A
command the repo wraps should be given in its wrapped form (`make migrate`, not the tool
underneath). **Never invent a command.** If the exact command or target can't be determined, say
precisely what is unknown and the quickest way to find out ("the repo doesn't say how production is
deployed; check the hosting dashboard or ask whoever owns `infra/`"). Don't paper over the gap with
a vague instruction like "run the migrations in production".

**Keep secrets out of the chat.** Where a step sets a secret, write the command so the value is
not printed and not left in shell history: read it from a prompt (`read -rs VAR`) or pipe it on
stdin (`--stdin`, `-`), rather than putting it inline.

Never run a step against a deployed environment, or one that is hard to reverse, without the
user's explicit go-ahead for that step.

## The Linear comment

The comment is the durable record. The chat goes away at `/clear`, and a ticket sitting in
**Merged** is where the user will look later for what's left. It is also how `/finishit` knows
where to resume. Post it whenever at least one step besides Done remains, and never otherwise.
Use this shape:

```markdown
## Manual steps to close {TICKET_ID}

Run `/finishit {TICKET_ID}` to be walked through these one at a time. Each box is ticked once its
step is verified.

- [ ] 1. Deploy `main` to production — Deployed (fly)
- [ ] 2. Run migration `0042_add_widgets` — Deployed (fly)
- [ ] 3. Set `STRIPE_WEBHOOK_SECRET` — UI (Stripe), then Deployed (fly)
- [ ] Last: move {TICKET_ID} to Done — you, once everything above is verified

### 1. Deploy `main` to production

<what and why, where it runs, the exact commands, how to verify — per the section above>

### 2. …

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

The checklist holds one line per step. The `###` sections hold each step in full, so the comment
can still be followed without Claude. `/finishit` updates this same comment as it goes, with
`save_comment` and the comment's ID. It ticks a step's box once that step is verified and adds a
note to a skipped step's line. It never ticks the Done line. Ticking that box is the user's job,
like the status change itself.
