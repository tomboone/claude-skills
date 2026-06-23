# Wait for CI to pass, then squash merge the PR for a Linear ticket, clean up branches, and sync to main.
# Usage: /personal:mergeit {TICKET_ID}

## Step 1 — Resolve the PR for this ticket

Find the open PR whose head branch is for `{TICKET_ID}`:

```bash
gh pr list --state open --json number,headRefName,title --limit 50
```

Pick the PR whose `headRefName` contains `{TICKET_ID}` (case-insensitive); fall back to a title containing the ID. If multiple match, list them and ask which to use. If none match, stop and tell the user there's no open PR for `{TICKET_ID}`. Call the chosen number `PR_NUMBER`.

(If the user passes a bare PR number instead of a ticket ID, use it directly as `PR_NUMBER`.)

## Step 2 — Check for blocking review findings

Run `gh pr view PR_NUMBER --comments` and scan for the most recent Code Review comment (posted by `/personal:reviewit`). If the assessment is "Needs changes", stop and tell the user to address the findings first. If no review comment exists, warn the user that review hasn't been run and ask them to confirm they want to proceed anyway.

## Step 3 — Wait for CI

Poll `gh pr checks PR_NUMBER` every 30 seconds. Show a brief status line each poll. If any check fails, stop and report which check failed and its log URL. Do not proceed.

## Step 4 — Squash merge

Once all checks pass:
```bash
gh pr merge PR_NUMBER --squash --delete-branch
```

The squash commit message should use the PR title as the subject — already in Conventional Commit format with `{TICKET_ID}` as a trailing parenthetical (e.g. `feat(ingestion): add endpoint ({TICKET_ID})`). Do not add a co-author line.

## Step 5 — Clean up and sync

Switch to main locally, pull to sync, and confirm the branch is gone both locally and remotely.

## Step 6 — Report done

Show the squash commit hash and confirm the branch is cleaned up. One line.
