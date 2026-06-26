# Wait for CI to pass, then squash merge the PR for a Linear ticket, clean up branches, and sync to main.
# Usage: /personal:mergeit {TICKET_ID}

## Step 1 — Resolve the PR for this ticket

Resolve `PR_NUMBER` for `{TICKET_ID}` as defined in `plugins/personal/pr-resolution-convention.md`. If no open PR matches, stop and tell the user there's no open PR for `{TICKET_ID}`.

## Step 2 — Check the review verdict (headless-safe, never prompt)

Run `gh pr view PR_NUMBER --comments` and find the most recent `## Code Review` comment posted by `/personal:reviewit`.

- If its **Assessment is "Ready to merge"** (the last `/reviewit` verdict was `APPROVED`), proceed.
- If it is **"Needs changes"**, or there is **no** `## Code Review` comment, do **not** prompt — stop and emit `STATUS: MERGE_BLOCKED` as the very last line, noting why (unaddressed findings / review not run).

## Step 3 — Wait for CI (bounded)

Poll `gh pr checks PR_NUMBER` every 30 seconds, showing a brief status line each poll, up to a 30-minute cap. If any check fails, or the cap is reached with checks still pending, stop and emit `STATUS: MERGE_BLOCKED` as the very last line, reporting which check failed/stalled and its log URL. Do not proceed.

## Step 4 — Squash merge

Once all checks pass:
```bash
gh pr merge PR_NUMBER --squash --delete-branch
```

The squash commit message should use the PR title as the subject — already in Conventional Commit format with `{TICKET_ID}` as a trailing parenthetical (e.g. `feat(ingestion): add endpoint ({TICKET_ID})`). Do not add a co-author line.

## Step 5 — Clean up and sync

Switch to main locally, pull to sync, and confirm the branch is gone both locally and remotely.

Delete the per-ticket review context bundle for `{TICKET_ID}` (path per `plugins/personal/review-context-convention.md`) if it exists — it is no longer needed once the PR is merged.

Do not touch the Linear ticket's status; the GitHub↔Linear connector closes it automatically on merge.

## Step 6 — Report done

Show the squash commit hash and confirm the branch and context bundle are cleaned up (one line). Then, as the **very last line of your response**, emit `STATUS: MERGED`.
