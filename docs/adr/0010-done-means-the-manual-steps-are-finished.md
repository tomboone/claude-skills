# Merging moves a ticket to Merged; the user moves it to Done

The GitHub↔Linear connector used to move a ticket to **Done** when its PR merged. That made Done mean
"the code merged", which is wrong for any ticket with work left after the merge: a migration to run
against production, a secret to set, a runbook the ticket delivered that still has to be carried
out. The ticket showed as finished while the work wasn't.

## Decision

- **The Linear team's "on PR merge" automation targets a started-type status, `Merged`**, instead of
  Done. This is a workflow setting in Linear, not something the plugin does. The plugin's commands
  still never set a status.
- **Done is set by the user, by hand.** Every manual-steps walkthrough
  (`plugins/personal/manual-steps-convention.md`) ends with "move {TICKET_ID} to Done", including
  when there are no other steps. Claude never moves the status itself and never offers to, even
  after the user says the steps are done. The global rule against flipping statuses stays absolute.

## Rejected alternatives

- **Non-closing keywords in the PR body** (`Part of {TICKET_ID}`). Linear documents these as linking
  a PR without closing the ticket on merge. But this pipeline also puts the ticket ID in the branch
  name and the PR title, and Linear's docs don't say which wins. It would also make `/shipit` decide,
  before merge, whether manual steps remain, which is a judgement better made after the merge, from
  the walkthrough.
- **Leave Done on merge and rely on the Linear comment.** That keeps the false "finished" signal,
  which is the problem this ADR exists to fix.

## Cost

Every ticket now needs one manual status change, even when nothing else is left. That is deliberate:
the moment a person confirms the ticket is finished is the moment it becomes Done.
