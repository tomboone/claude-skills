# Manual-steps walkthrough convention

A merged PR is not the same thing as a finished ticket. Migrations still have to be run against a
deployed database, secrets still have to be set, a runbook the ticket delivered still has to be
carried out, and a no-code ticket is nothing *but* manual work. This convention makes the command
that ends a ticket's run say, unprompted, exactly what is left and exactly how to do it.

**Used by:** `/mergeit` (after a successful merge), `/doit` (at the end of every run that produced
work or found the ticket to be no-code), and `/implementit` (when it stops with `STATUS: NO_CODE`
outside `/doit`). A command running under `/doit` leaves the walkthrough to `/doit`, so it appears
exactly once.

## Always emit the section

End the report with a `### Manual steps to close {TICKET_ID}` section, **even when there are no
other steps**. In that case write one line saying so and why, e.g.
`No other steps — no migrations, config or deploy steps; main deploys automatically on merge.`
The user should never have to ask whether anything is left.

## The last step is always "move it to Done"

Merging moves the ticket to **Merged**, not Done
([ADR 0010](../../docs/adr/0010-done-means-the-manual-steps-are-finished.md)). So the walkthrough
always ends with:

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
*execution* is the ticket's goal, carrying it out is the manual work. Walk through executing it, step
by step with its commands. Don't just point at the file.

## Write each step so it can be followed without guessing

Number the steps in the order they must happen. For each one give:

- **What and why**, in one line.
- **Where it runs**, exactly one of:
  - `Local — <absolute repo path>` for this machine;
  - `Deployed — <environment/host>`, plus the exact command that gets you there (`ssh …`,
    `kubectl exec …`, `fly ssh console -a …`, a cloud shell);
  - `UI — <service>`, with the starting URL where it's knowable.
- **The exact commands**, in a fenced block, ready to paste. Fill in every value you can know: file
  paths, migration names, env-var names, the branch, the PR number, the app or cluster name. Use a
  `<PLACEHOLDER>` only for values you cannot know (secrets, credentials, a value the user chooses),
  and say where each one comes from: "the `STRIPE_WEBHOOK_SECRET` shown in Stripe → Developers →
  Webhooks → *endpoint* → Signing secret".
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

Offer to run any step that is **local and non-destructive** from this session. Never run a step
against a deployed environment, or one that is hard to reverse, without the user's explicit go-ahead.

## Make it durable

When at least one step besides "move it to Done" remains, also post the walkthrough as a comment
on the Linear ticket, headed `## Manual steps to close {TICKET_ID}` and ending with the Claude Code
attribution footer. The chat goes away at `/clear`, and a ticket sitting in **Merged** is where the
user will look later for what's left. Post nothing when there are no other steps.
