# PR resolution convention

`/reviewit`, `/addressit`, and `/mergeit` resolve the pull request for a ticket the same way. This is the single source of truth for that procedure.

## Resolve `PR_NUMBER` for `{TICKET_ID}`

Find the open PR whose head branch is for `{TICKET_ID}`:

```bash
gh pr list --state open --json number,headRefName,title --limit 50
```

Pick the PR whose `headRefName` contains `{TICKET_ID}` (case-insensitive); fall back to a title containing the ID. If multiple match, list them and ask which to use. Call the chosen number `PR_NUMBER`.

If the user passed a bare PR number instead of a ticket ID, use it directly as `PR_NUMBER`.

If **no** open PR matches, do not continue — the calling command applies its own no-match behavior (see that command's Step 1).
