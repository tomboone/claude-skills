---
name: pr-desc
description: Use when the user wants to generate a PR title and description from the current branch's changes. Invoked via /pr-desc, optionally followed by a base ref or prose instructions to refine the output.
---

# PR Description Generator

Generate a PR title and markdown description by analyzing the diff between the current branch and its base.

**Announce at start:** "Generating PR description..."

## Args

The user may pass optional text after `/pr-desc`:
- A git ref (SHA or branch name) to use as an explicit diff base — skip stacked PR auto-detection
- Prose instructions to refine the description (e.g., "focus on the API changes", "ignore test refactoring")
- Both

To distinguish a ref from prose: run `git rev-parse --verify <token> 2>/dev/null` on tokens that look like they could be refs. If it resolves, treat it as a base override.

## Process

### Step 1: Determine the Diff Base

**Detect the default branch:**

```bash
gh repo view --json defaultBranchRef --jq '.defaultBranchRef.name'
```

Use `origin/<result>` as the initial base candidate. Fetch it first:

```bash
git fetch origin <default-branch> --quiet
```

**If the user provided an explicit base ref in args:** use that ref as the base. Skip to Step 2.

**Otherwise, detect stacked PRs:**

1. Find where this branch diverges from the default branch:
   ```bash
   git merge-base HEAD origin/<default>
   ```

2. Get all open PRs in the repo:
   ```bash
   gh pr list --state open --json headRefName,baseRefName,number --limit 50
   ```

3. For each open PR, fetch its head branch and compute the merge-base with HEAD:
   ```bash
   git fetch origin <headRefName> --quiet
   git merge-base HEAD origin/<headRefName>
   ```

4. If any open PR's merge-base with HEAD is **more recent** (a descendant of the default-branch merge-base), use that PR's head branch as the diff base instead. "More recent" means the merge-base commit is reachable from the default-branch merge-base but not equal to it — verify with:
   ```bash
   git merge-base --is-ancestor <default-merge-base> <pr-merge-base>
   ```

5. If multiple candidate parent PRs are found, pick the one whose merge-base is closest to HEAD (most recent ancestor).

6. Report which base was chosen:
   - If stacked: "Detected stacked PR on top of #<number> (`<branch>`), diffing against that branch."
   - If not stacked: "Diffing against `origin/<default>`."

### Step 2: Gather Context

Run all three commands using the determined base:

```bash
git log <base>..HEAD --pretty=format:"%h %s"
git diff <base>..HEAD --stat
git diff <base>..HEAD
```

Read all three outputs before generating anything.

**Incorporate conversation and plan context:**

Before generating the title and description, check for context from the current conversation that can inform the *why* and *motivation* behind the changes:

- **Implementation plan**: If there is an active plan (from `superpowers:writing-plans`, `superpowers:executing-plans`, or similar), use the plan's goal, motivation, acceptance criteria, and relevant step descriptions to frame the Summary and Changes sections.
- **Conversation history**: If the current session includes discussion about the problem being solved, the feature being added, or design decisions made, use that context for a more accurate and informative description.
- **Task context**: If tasks were created during the session, reference task descriptions for additional context on purpose and scope.

The diff shows *what* changed; conversation and plan context often better explain *why*. Use both.

### Step 3: Generate the Title

Write a PR title:
- Under 70 characters
- Conventional style (imperative mood, e.g., "Add user authentication endpoint")
- Print it directly in the response as a heading: `### <title>`

### Step 4: Generate the Description

Write the description to `/tmp/pr-description.md` using the **Write tool** (not Bash/echo). Overwrite any existing content.

Structure:

```markdown
## Summary
- <bullet points summarizing the changes>
- <scale the number of bullets to the size of the changeset>

## Changes
- <bulleted list of meaningful changes, grouped logically>
- <focus on what changed and why, not line-by-line diffs>

## Test plan
- [ ] <bulleted checklist of testing considerations>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

If the user passed prose refinement instructions in the args, adjust the description's focus, scope, or emphasis accordingly.

### Step 5: Confirm

After writing the file, open it in the user's default app:

```bash
open /tmp/pr-description.md
```

Print: "Description written to `/tmp/pr-description.md`"

## Important

- Always use the **Write tool** for the description file, never Bash echo/cat. This ensures clean markdown without shell escaping issues.
- Always **fetch** remote branches before computing merge-bases to ensure up-to-date refs.
- If `gh` commands fail (e.g., no GitHub remote), fall back to `origin/<default>` as the base and note the limitation.
- Do not create or modify any git commits, branches, or PRs. This skill is read-only.
