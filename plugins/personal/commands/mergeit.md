# Wait for CI to pass, then merge the PR for a Linear ticket, clean up branches, and sync the base branch.
# Usage: /personal:mergeit {TICKET_ID}

## Step 1 — Resolve the PR for this ticket

Resolve `PR_NUMBER` for `{TICKET_ID}` as defined in `plugins/personal/pr-resolution-convention.md`. If no open PR matches, stop and tell the user there's no open PR for `{TICKET_ID}`.

Also capture the PR's base branch — you need it in Steps 4 and 5:

```bash
gh pr view PR_NUMBER --json baseRefName --jq .baseRefName
```

Call that `BASE`.

## Step 2 — Check the review verdict (headless-safe, never prompt)

Run `gh pr view PR_NUMBER --comments` and look for the most recent `## Code Review` comment posted by `/personal:reviewit`.

- If one exists and its **Assessment is "Needs changes"**, do **not** prompt — stop and emit `STATUS: MERGE_BLOCKED` as the very last line, noting the unaddressed findings.
- If one exists and its **Assessment is "Ready to merge"**, proceed.
- If there is **no** `## Code Review` comment, proceed. The loop no longer runs `/personal:reviewit` — `/implement` performs its `/code-review --fix` pass before the PR is opened, so a loop-driven PR legitimately has no review comment and CI is the gate. (Run `/personal:reviewit {TICKET_ID}` by hand first if you want a recorded verdict on this PR.)

## Step 3 — Wait for CI (bounded)

Poll `gh pr checks PR_NUMBER` every 30 seconds, showing a brief status line each poll, up to a 30-minute cap. If any check fails, or the cap is reached with checks still pending, stop and emit `STATUS: MERGE_BLOCKED` as the very last line, reporting which check failed/stalled and its log URL. Do not proceed.

## Step 4 — Merge, using the strategy that matches `BASE`

The merge strategy depends on what the PR targets. Resolve the repo's default branch:

```bash
git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##'
```

(fall back to `git remote show origin | sed -n 's/.*HEAD branch: //p'` if unset). Call it `DEFAULT`.

- **`BASE` is a `release/*` branch** (i.e. `BASE` != `DEFAULT`) → **squash merge**. Each ticket lands on the release branch as exactly one commit, so the release branch reads as a clean list of tickets.

  ```bash
  gh pr merge PR_NUMBER --squash --delete-branch
  ```

  The squash commit message should use the PR title as the subject — already in Conventional Commit format with `{TICKET_ID}` as a trailing parenthetical (e.g. `feat(ingestion): add endpoint ({TICKET_ID})`).

- **`BASE` is the default branch** (`BASE` == `DEFAULT`) → **merge commit**. This preserves the individual commits, which matters when a release branch (or a longer-lived work branch) integrates into `main`.

  ```bash
  gh pr merge PR_NUMBER --merge --delete-branch
  ```

Do not add a co-author line in either case.

## Step 5 — Clean up and sync

Check out `BASE` locally and pull to sync — **not** `main` unconditionally; a release-branch run must leave you on the release branch so the next ticket branches from the state this one just merged into. Confirm the PR branch is gone both locally and remotely.

Delete the per-ticket review context bundle for `{TICKET_ID}` (path per `plugins/personal/review-context-convention.md`) if it exists — it is no longer needed once the PR is merged.

Do not touch the Linear ticket's status; the GitHub↔Linear connector closes it automatically on merge.

## Step 6 — Report done

Show the merge commit hash, which strategy was used and why (`squash` into `release/*`, `merge` into `DEFAULT`), and confirm the branch and context bundle are cleaned up (one line). Then, as the **very last line of your response**, emit `STATUS: MERGED`.
