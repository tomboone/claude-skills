# Respond to /reviewit's findings: implement valid fixes, push back on unnecessary ones, push to the PR branch, and post the disposition as a comment.
# Usage: /personal:addressit {TICKET_ID}

## Step 1 — Resolve the PR for this ticket

Find the open PR whose head branch is for `{TICKET_ID}`:

```bash
gh pr list --state open --json number,headRefName,title --limit 50
```

Pick the PR whose `headRefName` contains `{TICKET_ID}` (case-insensitive); fall back to a title containing the ID. If multiple match, list them and ask which to use. If none match, stop and emit `STATUS: BLOCKED` as the very last line. Call the chosen number `PR_NUMBER`.

(If the user passes a bare PR number instead of a ticket ID, use it directly as `PR_NUMBER`.)

## Step 2 — Load review context and the live PR state

**Ticket intent (cached bundle).** Load-or-generate the review context bundle for `{TICKET_ID}` as defined in `plugins/personal/review-context-convention.md`.

**Live PR state.**
```bash
gh pr view PR_NUMBER                                             # title, body
gh pr diff PR_NUMBER                                             # current full diff
gh pr view PR_NUMBER --comments                                  # full conversation thread
gh api repos/{owner}/{repo}/pulls/PR_NUMBER/comments --paginate  # inline review-thread comments
```

Check out the PR branch locally so you can make changes:
```bash
gh pr checkout PR_NUMBER
```
If checkout fails, stop and emit `STATUS: BLOCKED` as the very last line.

## Step 3 — Identify the findings to address

Take the **most recent** `## Code Review` comment posted by `/personal:reviewit` as the set of findings. Also read any prior `## Review Response` comments and inline replies so you do not re-litigate items already resolved or already disputed in an earlier round.

If there is no `## Code Review` comment at all, there is nothing to address — stop and emit `STATUS: BLOCKED` as the very last line (review hasn't run yet).

## Step 4 — Evaluate and act (Superpowers receiving-code-review)

Invoke the `superpowers:receiving-code-review` skill and apply it to each finding, using the context bundle (Linear intent + spec/plan) and the live diff as ground truth:

- **Verify before implementing.** Check each finding against codebase reality and the ticket's intent.
- **Implement valid fixes** one at a time; test each as you go.
- **Push back — and hold ground — on findings that are wrong, unnecessary, out of scope for the ticket, or conflict with the spec/plan.** Do NOT implement a change just to satisfy the reviewer; record technical reasoning instead. No performative agreement, no gratitude — see the skill.

Track each finding's disposition: **Fixed** (what changed) or **Pushed back** (the reasoning).

## Step 5 — Commit and push fixes

If you made code changes:

1. Generate a one-line Conventional Commit message describing the fixes (imperative, ≤72 chars), with `{TICKET_ID}` as a **trailing parenthetical**: `fix(scope): address review findings ({TICKET_ID})`. **No co-author line. No footer in the commit message.**
2. Stage and commit the fix changes. Do NOT stage the context bundle (it is gitignored per the convention doc).
3. Push to the PR branch:
   ```bash
   git push
   ```

If you made no code changes (pushed back on everything), skip this step.

## Step 6 — Post the response comment

Post a top-level PR comment summarizing the disposition (always end with the footer):

```bash
gh pr comment PR_NUMBER --body "..."
```

Format:

```
## Review Response

### Fixed
[Per item: the finding and what changed — or "None"]

### Pushed back
[Per item: the finding and the technical reason it wasn't implemented — or "None"]

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

## Step 7 — Emit STATUS

As the **very last line of your response**, emit exactly one:

- `STATUS: ADDRESSED` — you committed and pushed at least one fix (a re-review is warranted).
- `STATUS: PUSHED_BACK` — you made no code changes and disputed all findings, with reasoning posted.
- `STATUS: BLOCKED` — you could not operate (no PR, no `## Code Review` comment, or checkout failed).

Before that line, tell the user (one line) to clear context and run `/personal:reviewit {TICKET_ID}` again if ADDRESSED, or that the review is at an impasse needing their input if PUSHED_BACK.
