# Review the PR for a Linear ticket using the Superpowers code-reviewer subagent and post findings as a PR comment.
# Usage: /personal:reviewit {TICKET_ID}

## Step 1 — Resolve the PR for this ticket

Find the open PR whose head branch is for `{TICKET_ID}`:

```bash
gh pr list --state open --json number,headRefName,title --limit 50
```

Pick the PR whose `headRefName` contains `{TICKET_ID}` (case-insensitive); if none match there, fall back to a title containing the ID. If multiple match, list them and ask the user which to use. If none match, stop and tell the user there's no open PR for `{TICKET_ID}` (did they run `/personal:shipit {TICKET_ID}`?). Call the chosen number `PR_NUMBER`.

(If the user passes a bare PR number instead of a ticket ID, use it directly as `PR_NUMBER`.)

## Step 2 — Resolve the docs directory and fetch context

Determine `DOCS_DIR` (override via `specs_dir` in CLAUDE.md; else `<umbrella>/docs` for umbrella layouts or `<repo-root>/.claude/docs` for single repos). Read the spec for this ticket from `DOCS_DIR/superpowers/specs/` (the file whose name contains `{TICKET_ID}`) if one exists — this is the plan the implementation should be measured against.

Then:
```bash
gh pr view PR_NUMBER          # title, body
gh pr diff PR_NUMBER          # full diff
```

## Step 3 — Get SHAs

```bash
BASE_SHA=$(gh pr view PR_NUMBER --json baseRefOid --jq '.baseRefOid')
HEAD_SHA=$(gh pr view PR_NUMBER --json headRefOid --jq '.headRefOid')
```

## Step 4 — Invoke Superpowers code review

Invoke the `superpowers:requesting-code-review` skill, providing:
- `WHAT_WAS_IMPLEMENTED`: derived from the PR title and body
- `PLAN_OR_REQUIREMENTS`: the spec file content if it exists, otherwise the PR body
- `BASE_SHA`: from above
- `HEAD_SHA`: from above
- `DESCRIPTION`: one-sentence summary of the change

## Step 5 — Post findings as a PR comment and emit STATUS

When the reviewer subagent returns its findings, post them as a PR review comment:
```bash
gh pr comment PR_NUMBER --body "..."
```

Format the comment as (always end with the footer):

```
## Code Review

**Assessment:** [Ready to merge / Needs changes]

### Critical
[List or "None"]

### Important
[List or "None"]

### Minor
[List or "None"]

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

**If there are Critical or Important issues:** tell the user what they are and that they should be addressed before merging. Then, as the **very last line of your response**, emit:

```
STATUS: CHANGES_REQUESTED
```

**If the assessment is clean (no Critical or Important issues):** tell the user to clear context and run `/personal:mergeit {TICKET_ID}` when ready. Then, as the **very last line of your response**, emit:

```
STATUS: APPROVED
```
