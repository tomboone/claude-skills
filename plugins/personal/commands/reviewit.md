# Review the PR for a Linear ticket using the Superpowers code-reviewer subagent and post findings as a PR comment.
# Usage: /personal:reviewit {TICKET_ID}

## Step 1 — Resolve the PR for this ticket

Find the open PR whose head branch is for `{TICKET_ID}`:

```bash
gh pr list --state open --json number,headRefName,title --limit 50
```

Pick the PR whose `headRefName` contains `{TICKET_ID}` (case-insensitive); if none match there, fall back to a title containing the ID. If multiple match, list them and ask the user which to use. If none match, stop and tell the user there's no open PR for `{TICKET_ID}` (did they run `/personal:shipit {TICKET_ID}`?). Call the chosen number `PR_NUMBER`.

(If the user passes a bare PR number instead of a ticket ID, use it directly as `PR_NUMBER`.)

## Step 2 — Load review context and fetch the live PR state

**Ticket intent (cached bundle).** Load-or-generate the review context bundle for `{TICKET_ID}` as defined in `plugins/personal/review-context-convention.md`: if the bundle file exists, read it; otherwise gather the Linear ticket + related/project/milestone context and the spec/plan files, write the bundle, then read it. This is the full intent the implementation should be measured against — not just the spec.

**Live PR state.**
```bash
gh pr view PR_NUMBER          # title, body
gh pr diff PR_NUMBER          # full diff
```

### Prior review activity (so this pass builds on earlier rounds)

Fetch any existing review conversation so the reviewer knows what was already raised and how it was resolved — otherwise each `/reviewit` run starts blind and may re-flag findings that were already fixed or deliberately accepted:

```bash
gh pr view PR_NUMBER --comments                                  # conversation thread, incl. prior `## Code Review` comments this command posted
gh api repos/{owner}/{repo}/pulls/PR_NUMBER/comments --paginate  # inline (line-level) review-thread comments
gh api repos/{owner}/{repo}/pulls/PR_NUMBER/reviews  --paginate  # formal review summaries (approve / request-changes)
```

(`gh api` resolves `{owner}`/`{repo}` from the current repo automatically.)

From these, build `PRIOR_REVIEW_CONTEXT`: a short digest of each previously-raised finding and its apparent current state — focus on the most recent `## Code Review` block this command posted plus any human replies. For each prior item, note whether the thread shows it was **fixed**, **still open**, or **intentionally accepted/deferred** by the user. If there are no prior comments, leave `PRIOR_REVIEW_CONTEXT` empty.

## Step 3 — Get SHAs

```bash
BASE_SHA=$(gh pr view PR_NUMBER --json baseRefOid --jq '.baseRefOid')
HEAD_SHA=$(gh pr view PR_NUMBER --json headRefOid --jq '.headRefOid')
```

## Step 4 — Invoke Superpowers code review

Invoke the `superpowers:requesting-code-review` skill, providing:
- `WHAT_WAS_IMPLEMENTED`: derived from the PR title and body
- `PLAN_OR_REQUIREMENTS`: the review context bundle from Step 2 (Linear ticket intent + spec/plan); fall back to the PR body only if no bundle context could be gathered. **If `PRIOR_REVIEW_CONTEXT` is non-empty, append it to this field** under a `## Prior review history` heading — the reviewer template has no dedicated slot, so this is how the history reaches the reviewer.
- `BASE_SHA`: from above
- `HEAD_SHA`: from above
- `DESCRIPTION`: one-sentence summary of the change

When prior review history is present, instruct the reviewer to treat those findings as already-raised: for each, inspect the current diff to confirm whether it is now resolved and note its status (fixed / still open / intentionally deferred) rather than rediscovering it from scratch. Only surface a prior item as a fresh finding if it remains unaddressed, and do **not** re-flag anything the thread shows the user accepted or deferred.

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

If prior review history was available, briefly note in the comment which previously-raised items are now resolved (e.g. a short "Previously raised, now fixed" line), so the thread shows how the review evolved across rounds.

**If there are Critical or Important issues:** tell the user what they are and that they should be addressed before merging. Then, as the **very last line of your response**, emit:

```
STATUS: CHANGES_REQUESTED
```

**If the assessment is clean (no Critical or Important issues):** tell the user to clear context and run `/personal:mergeit {TICKET_ID}` when ready. Then, as the **very last line of your response**, emit:

```
STATUS: APPROVED
```
