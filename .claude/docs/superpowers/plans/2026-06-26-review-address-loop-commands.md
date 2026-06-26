# Review/Address Loop Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/addressit` command and make `/reviewit`, `/mergeit`, `/shipit`, `/implementit` ready for a fully autonomous implement→ship→review↔address→merge loop, without touching `loop.py`.

**Architecture:** Six prompt files in `plugins/personal/` plus a version bump. A new shared convention doc defines a per-ticket "ticket intent" context bundle that `/reviewit` and `/addressit` both load-or-generate and `/mergeit` deletes on merge. Each command emits a fixed `STATUS:` sentinel as its last line so a future `loop.py` can key off it. No runtime code; verification is cross-file consistency checks.

**Tech Stack:** Markdown slash-command definitions, `gh` CLI, Linear MCP, the Superpowers `requesting-code-review` / `receiving-code-review` skills.

## Global Constraints

- Commit messages: Conventional Commits; **no** Linear parenthetical (this repo has no ticket for this work); **no** co-author line; **no** 🤖 footer in commit messages.
- The 🤖 footer (`🤖 Generated with [Claude Code](https://claude.com/claude-code)`) IS required on every PR comment the commands post.
- Every command emits its `STATUS:` sentinel as the **very last line** of its response (matches existing `implementit`/`reviewit` convention; `loop.py` does substring checks).
- Context bundle path: `<DOCS_DIR>/superpowers/context/<TICKET_ID>-review-context.md`; gitignored for single-repo layouts; deleted by `/mergeit` on merge.
- Shared convention doc path: `plugins/personal/review-context-convention.md`.
- Plugin version: `plugins/personal/.claude-plugin/plugin.json` bumps `0.4.0 → 0.5.0`.
- **Do NOT modify `plugins/personal/scripts/loop.py` or `test_loop.py`.**
- Status sentinel strings (exact): `STATUS: IMPLEMENTED`, `STATUS: NO_PLAN`, `STATUS: SHIPPED`, `STATUS: APPROVED`, `STATUS: CHANGES_REQUESTED`, `STATUS: ADDRESSED`, `STATUS: PUSHED_BACK`, `STATUS: BLOCKED`, `STATUS: MERGED`, `STATUS: MERGE_BLOCKED`.
- Shared PR-comment headings (exact): `## Code Review` (posted by `/reviewit`), `## Review Response` (posted by `/addressit`).

---

### Task 1: Shared review-context convention doc

**Files:**
- Create: `plugins/personal/review-context-convention.md`

**Interfaces:**
- Produces: the bundle path `<DOCS_DIR>/superpowers/context/<TICKET_ID>-review-context.md`, its contents contract, and its generate-or-load / gitignore / delete-on-merge lifecycle. Tasks 2, 3, and 4 reference this doc by path.

- [ ] **Step 1: Write the convention doc**

Create `plugins/personal/review-context-convention.md` with exactly this content:

```markdown
# Review context convention

`/reviewit`, `/addressit`, and `/mergeit` share one bundle of "ticket intent" so they review and respond from the same understanding. This doc is the single source of truth for what that bundle contains, where it lives, and how it is managed.

## The context bundle

**Path:** `<DOCS_DIR>/superpowers/context/<TICKET_ID>-review-context.md`

`DOCS_DIR` resolves exactly as in `/personal:implementit`:
1. `specs_dir` override in any loaded `CLAUDE.md`, else
2. umbrella layout → `<umbrella>/docs`, else
3. single-repo layout → `<repo-root>/.claude/docs`.

The `<TICKET_ID>` in the filename keeps bundles for different tickets from colliding when runs overlap.

## Contents (stable intent only)

Gather once, via the Linear MCP and the local spec/plan files, and write under clear headings:

- **Linear ticket:** id, title, description, current state.
- **Linear hierarchy & relations:** the ticket's project, its milestone, its parent and sub-issues, and its `blockedBy` / `blocks` / related issues (id + title + state for each).
- **Spec & plan:** the spec file and the plan file whose names contain `<TICKET_ID>`, searched in BOTH layouts (`<DOCS_DIR>/superpowers/{specs,plans}/` and the flat `<DOCS_DIR>/{specs,plans}/`). If the plan references a milestone spec (a line beginning `**Milestone spec:** `), include that too.

This is reference context — not the live diff.

## Live, never cached

Do NOT put the PR diff or the comment thread in the bundle — they change between rounds. `/reviewit` and `/addressit` always fetch those live (`gh pr diff`, `gh pr view --comments`, the inline-comments / reviews APIs).

## Lifecycle

- **Generate-or-load:** before reviewing/responding, check for the bundle file. If present, read it. If absent, gather the contents above, write it, then read it. Regenerate only when missing.
- **Gitignore (single-repo layouts only):** when `DOCS_DIR` is inside the code repo, the bundle must never be committed into the PR. Before writing it, ensure the repo's `.gitignore` contains an entry covering `.claude/docs/superpowers/context/` (add it if missing). Umbrella layouts keep `DOCS_DIR` outside the code repo, so this does not apply.
- **Delete on merge:** `/mergeit` deletes the bundle file after a successful merge.
```

- [ ] **Step 2: Verify the doc is complete**

Run: `grep -c -E 'Path:|Generate-or-load|Gitignore|Delete on merge|Live, never cached' plugins/personal/review-context-convention.md`
Expected: `5` (all five anchor phrases present).

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/review-context-convention.md
git commit -m "feat(personal): add review-context convention for /reviewit and /addressit"
```

---

### Task 2: Wire `/reviewit` to the context bundle

**Files:**
- Modify: `plugins/personal/commands/reviewit.md` (Step 2 intro; Step 4 `PLAN_OR_REQUIREMENTS` line)

**Interfaces:**
- Consumes: the bundle path + lifecycle from Task 1.
- Produces: the bundle file when it runs first (so `/addressit` and `/mergeit` find it). Status vocabulary unchanged (`APPROVED` / `CHANGES_REQUESTED`).

- [ ] **Step 1: Replace the Step 2 intro to load-or-generate the bundle**

In `plugins/personal/commands/reviewit.md`, replace this block:

```
## Step 2 — Resolve the docs directory and fetch context

Determine `DOCS_DIR` (override via `specs_dir` in CLAUDE.md; else `<umbrella>/docs` for umbrella layouts or `<repo-root>/.claude/docs` for single repos). Read the spec for this ticket from `DOCS_DIR/superpowers/specs/` (the file whose name contains `{TICKET_ID}`) if one exists — this is the plan the implementation should be measured against.

Then:
```

with:

```
## Step 2 — Load review context and fetch the live PR state

**Ticket intent (cached bundle).** Load-or-generate the review context bundle for `{TICKET_ID}` as defined in `plugins/personal/review-context-convention.md`: if the bundle file exists, read it; otherwise gather the Linear ticket + related/project/milestone context and the spec/plan files, write the bundle, then read it. This is the full intent the implementation should be measured against — not just the spec.

**Live PR state.**
```

(Leave the existing `gh pr view` / `gh pr diff` fenced block and the entire `### Prior review activity` subsection that follows it untouched.)

- [ ] **Step 2: Update the Step 4 `PLAN_OR_REQUIREMENTS` line to use the bundle**

Replace this line:

```
- `PLAN_OR_REQUIREMENTS`: the spec file content if it exists, otherwise the PR body. **If `PRIOR_REVIEW_CONTEXT` is non-empty, append it to this field** under a `## Prior review history` heading — the reviewer template has no dedicated slot, so this is how the history reaches the reviewer.
```

with:

```
- `PLAN_OR_REQUIREMENTS`: the review context bundle from Step 2 (Linear ticket intent + spec/plan); fall back to the PR body only if no bundle context could be gathered. **If `PRIOR_REVIEW_CONTEXT` is non-empty, append it to this field** under a `## Prior review history` heading — the reviewer template has no dedicated slot, so this is how the history reaches the reviewer.
```

- [ ] **Step 3: Verify the edits landed and the status vocabulary is intact**

Run: `grep -E 'review-context-convention|Load review context|the review context bundle from Step 2' plugins/personal/commands/reviewit.md`
Expected: at least the convention-doc reference and the new Step 2 heading and Step 4 line appear.

Run: `grep -c -E 'STATUS: APPROVED|STATUS: CHANGES_REQUESTED' plugins/personal/commands/reviewit.md`
Expected: `2` (both unchanged).

- [ ] **Step 4: Commit**

```bash
git add plugins/personal/commands/reviewit.md
git commit -m "feat(personal): give /reviewit full ticket + spec/plan context via shared bundle"
```

---

### Task 3: Create `/addressit`

**Files:**
- Create: `plugins/personal/commands/addressit.md`

**Interfaces:**
- Consumes: the `## Code Review` comment posted by `/reviewit`; the bundle from Task 1.
- Produces: a `## Review Response` comment; fix commits pushed to the PR branch; `STATUS: ADDRESSED` / `STATUS: PUSHED_BACK` / `STATUS: BLOCKED`.

- [ ] **Step 1: Write the command**

Create `plugins/personal/commands/addressit.md` with exactly this content:

```markdown
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
```

- [ ] **Step 2: Verify the command's contract surface**

Run: `grep -c -E 'STATUS: ADDRESSED|STATUS: PUSHED_BACK|STATUS: BLOCKED' plugins/personal/commands/addressit.md`
Expected: `4` (BLOCKED appears in Steps 1/2/3 fallbacks and the Step 7 list; ADDRESSED and PUSHED_BACK once each in Step 7 — confirm all three strings are present; exact count may exceed 4, which is fine. The check is that the grep is non-zero for each).

Run: `grep -E 'review-context-convention|## Review Response|receiving-code-review' plugins/personal/commands/addressit.md`
Expected: all three present.

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/commands/addressit.md
git commit -m "feat(personal): add /addressit to respond to review findings"
```

---

### Task 4: Make `/mergeit` loop-ready

**Files:**
- Modify: `plugins/personal/commands/mergeit.md` (Steps 2, 3, 5, 6)

**Interfaces:**
- Consumes: the most recent `## Code Review` verdict from `/reviewit`; the bundle path from Task 1.
- Produces: `STATUS: MERGED` / `STATUS: MERGE_BLOCKED`; deletes the bundle on success.

- [ ] **Step 1: Replace Step 2 with a headless-safe verdict check**

Replace:

```
## Step 2 — Check for blocking review findings

Run `gh pr view PR_NUMBER --comments` and scan for the most recent Code Review comment (posted by `/personal:reviewit`). If the assessment is "Needs changes", stop and tell the user to address the findings first. If no review comment exists, warn the user that review hasn't been run and ask them to confirm they want to proceed anyway.
```

with:

```
## Step 2 — Check the review verdict (headless-safe, never prompt)

Run `gh pr view PR_NUMBER --comments` and find the most recent `## Code Review` comment posted by `/personal:reviewit`.

- If its **Assessment is "Ready to merge"** (the last `/reviewit` verdict was `APPROVED`), proceed.
- If it is **"Needs changes"**, or there is **no** `## Code Review` comment, do **not** prompt — stop and emit `STATUS: MERGE_BLOCKED` as the very last line, noting why (unaddressed findings / review not run).
```

- [ ] **Step 2: Replace Step 3 with a bounded CI wait**

Replace:

```
## Step 3 — Wait for CI

Poll `gh pr checks PR_NUMBER` every 30 seconds. Show a brief status line each poll. If any check fails, stop and report which check failed and its log URL. Do not proceed.
```

with:

```
## Step 3 — Wait for CI (bounded)

Poll `gh pr checks PR_NUMBER` every 30 seconds, showing a brief status line each poll, up to a 30-minute cap. If any check fails, or the cap is reached with checks still pending, stop and emit `STATUS: MERGE_BLOCKED` as the very last line, reporting which check failed/stalled and its log URL. Do not proceed.
```

- [ ] **Step 3: Replace Step 5 to delete the bundle and note auto-close**

Replace:

```
## Step 5 — Clean up and sync

Switch to main locally, pull to sync, and confirm the branch is gone both locally and remotely.
```

with:

```
## Step 5 — Clean up and sync

Switch to main locally, pull to sync, and confirm the branch is gone both locally and remotely.

Delete the per-ticket review context bundle for `{TICKET_ID}` (path per `plugins/personal/review-context-convention.md`) if it exists — it is no longer needed once the PR is merged.

Do not touch the Linear ticket's status; the GitHub↔Linear connector closes it automatically on merge.
```

- [ ] **Step 4: Replace Step 6 to emit the status sentinel**

Replace:

```
## Step 6 — Report done

Show the squash commit hash and confirm the branch is cleaned up. One line.
```

with:

```
## Step 6 — Report done

Show the squash commit hash and confirm the branch and context bundle are cleaned up (one line). Then, as the **very last line of your response**, emit `STATUS: MERGED`.
```

- [ ] **Step 5: Verify the new contract surface**

Run: `grep -c -E 'STATUS: MERGE_BLOCKED' plugins/personal/commands/mergeit.md`
Expected: `2` (Step 2 and Step 3).

Run: `grep -E 'STATUS: MERGED|review-context-convention|never prompt' plugins/personal/commands/mergeit.md`
Expected: all three present.

- [ ] **Step 6: Commit**

```bash
git add plugins/personal/commands/mergeit.md
git commit -m "feat(personal): make /mergeit loop-ready (headless verdict check + status + bundle cleanup)"
```

---

### Task 5: Branch `/implementit` from up-to-date `origin/main`

**Files:**
- Modify: `plugins/personal/commands/implementit.md` (Step 4)

**Interfaces:**
- Produces: work branches rooted on `origin/main` so each ticket starts from prior merges. Status vocabulary unchanged.

- [ ] **Step 1: Replace Step 4's branch-creation paragraph**

Replace:

```
Check out the branch from main (or the current release branch if one exists and is the appropriate base — check with the user if ambiguous).
```

with:

```
**Branch from up-to-date `main`.** Sync the base first so each ticket starts from every prior ticket's merged state (fewer downstream conflicts):
```bash
git fetch origin main
git checkout -b feat/{TICKET_ID}-short-description origin/main
```
If a release branch is the appropriate base instead (one exists and is the active release), fetch and branch from `origin/<release-branch>` the same way. In headless mode default to `origin/main`; only ask the user if genuinely ambiguous and a user is present.
```

- [ ] **Step 2: Verify**

Run: `grep -E 'git fetch origin main|checkout -b feat/\{TICKET_ID\}-short-description origin/main' plugins/personal/commands/implementit.md`
Expected: both lines present.

Run: `grep -c -E 'STATUS: IMPLEMENTED|STATUS: NO_PLAN' plugins/personal/commands/implementit.md`
Expected: `2` (unchanged).

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/commands/implementit.md
git commit -m "feat(personal): branch /implementit from up-to-date origin/main"
```

---

### Task 6: Emit `STATUS: SHIPPED` from `/shipit`

**Files:**
- Modify: `plugins/personal/commands/shipit.md` (Step 8)

**Interfaces:**
- Produces: `STATUS: SHIPPED` as the last line (PR URL output unchanged; `loop.py` keys on the URL).

- [ ] **Step 1: Replace Step 8**

Replace:

```
## Step 8 — Hand off

Show the PR URL. Tell the user to clear context and run `/personal:reviewit {TICKET_ID}` when ready. Stop here — do not wait for CI, do not merge.
```

with:

```
## Step 8 — Hand off

Show the PR URL. Tell the user to clear context and run `/personal:reviewit {TICKET_ID}` when ready. Stop here — do not wait for CI, do not merge.

Then, as the **very last line of your response**, emit `STATUS: SHIPPED`. (The headless loop orchestrator keys on the PR URL; this sentinel keeps the status contract uniform across commands.)
```

- [ ] **Step 2: Verify**

Run: `grep -c 'STATUS: SHIPPED' plugins/personal/commands/shipit.md`
Expected: `1`.

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/commands/shipit.md
git commit -m "feat(personal): emit STATUS: SHIPPED from /shipit"
```

---

### Task 7: Version bump + cross-file consistency check

**Files:**
- Modify: `plugins/personal/.claude-plugin/plugin.json`

- [ ] **Step 1: Bump the version**

In `plugins/personal/.claude-plugin/plugin.json`, change `"version": "0.4.0",` to `"version": "0.5.0",`.

- [ ] **Step 2: Cross-file consistency check (the whole contract)**

Run: `grep -rl 'review-context-convention' plugins/personal/commands/`
Expected: `reviewit.md`, `addressit.md`, `mergeit.md` all listed (three files reference the convention doc).

Run: `grep -rn '## Review Response' plugins/personal/commands/addressit.md && grep -rn '## Code Review' plugins/personal/commands/reviewit.md plugins/personal/commands/addressit.md plugins/personal/commands/mergeit.md`
Expected: `addressit` posts `## Review Response`; `reviewit` posts and `addressit`/`mergeit` look for `## Code Review`.

Run: `git diff --name-only origin/main -- plugins/personal/scripts/`
Expected: empty (no `loop.py` / `test_loop.py` changes).

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/.claude-plugin/plugin.json
git commit -m "chore(personal): bump plugin to 0.5.0"
```

---

## Self-Review (plan author)

**Spec coverage:** §4.1 convention doc → Task 1. §4.2/§4.3 bundle in reviewit → Task 2. §5 `/addressit` → Task 3. §7 `/mergeit` loop-ready → Task 4. §8 `/implementit` origin/main → Task 5. §8 `/shipit` SHIPPED → Task 6. §10 version bump + verification → Task 7. §9 future loop semantics → intentionally no task (out of scope). All covered.

**Placeholder scan:** No TBD/TODO; every file's full content or exact old→new edit is shown. The `{TICKET_ID}` / `PR_NUMBER` / `<DOCS_DIR>` tokens are intentional runtime placeholders inside the prompt text, not plan gaps.

**Consistency:** Status strings and the `## Code Review` / `## Review Response` headings match the Global Constraints across Tasks 2/3/4 and are re-checked in Task 7 Step 2.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
