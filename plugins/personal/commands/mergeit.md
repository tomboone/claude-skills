---
description: Wait for CI to pass, then merge a Linear ticket's PR, clean up branches, and sync the base
argument-hint: "{TICKET_ID}"
---

**CRITICAL: Follow every step in order. Do not skip or reorder steps.**

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
- If there is **no** `## Code Review` comment, proceed. The loop no longer runs `/personal:reviewit` — `/personal:implementit` performs its `/personal:code-review` pass before the PR is opened, so a loop-driven PR legitimately has no review comment and CI is the gate. (Run `/personal:reviewit {TICKET_ID}` by hand first if you want a recorded verdict on this PR.)

## Step 3 — Wait for CI (bounded)

### 3a. Decide whether this repo runs CI on PRs — from the repo, not from `gh pr checks`

**`gh pr checks` cannot tell you.** When it prints `no checks reported on the '<branch>' branch` and exits **1**, that means either "this repo has no CI" *or* "CI hasn't registered a run yet" — identical output, identical exit code, opposite correct responses. Resolve it by looking at the workflow definitions instead:

```bash
grep -rlE '^[[:space:]]*(pull_request|pull_request_target)[[:space:]]*:' .github/workflows/ 2>/dev/null
```

Pass the **directory** to `grep -r`; do not glob the filenames. Under `zsh` — the default shell on macOS, and the one this runs under — an unmatched glob like `.github/workflows/*.y*ml` is a **fatal** `no matches found` error that aborts the command before `grep` ever runs, so a repo with no workflows directory would fail this step instead of cleanly answering "no". (`bash` degrades to a literal string instead, which is why this reads as portable but isn't.) `grep -r` on a missing directory just exits non-zero with no output, which is exactly the signal we want.

- **Any match** → this repo **does** run CI on pull requests. Checks *will* appear; a missing check means "not yet," never "not configured." Call this `EXPECTS_CI=yes`.
- **No output** (no matching trigger, or no `.github/workflows/` at all) → `EXPECTS_CI=no`.

### 3b. Wait for a check run to register (only when `EXPECTS_CI=yes`)

Registration is not instant. `/personal:shipit` opened the PR moments ago, and GitHub can take **several minutes** to create the check run — five minutes has been observed. `gh pr checks --watch` does **not** wait for checks to *appear*; it returns immediately when there are none.

Poll for a check to exist, up to **10 minutes**, then fall through to 3c:

```bash
for i in $(seq 1 20); do
  gh pr checks PR_NUMBER >/dev/null 2>&1 && break
  gh pr checks PR_NUMBER 2>&1 | grep -qv 'no checks reported' && break
  sleep 30
done
```

If 10 minutes pass with still no check registered, **stop and emit `STATUS: MERGE_BLOCKED`** as the very last line, reporting that the repo defines a `pull_request` workflow but no check run appeared. **Do not merge.** A held ticket is recoverable; a release-branch merge that skipped CI is not.

### 3c. Watch the checks to completion

**Do not hand-roll a poll loop here.** `gh` blocks server-side and returns the moment checks settle, far cheaper than a `sleep`-and-re-check cycle (each of which costs a full agent turn):

```bash
gh pr checks PR_NUMBER --watch --fail-fast --interval 10
```

Bound it at 30 minutes. Prefer `timeout 1800 gh pr checks …` when `timeout` (or `gtimeout`) is on `PATH` — it's GNU coreutils and is **not** present on a stock macOS, so check with `command -v timeout` first and run the command bare if it's missing. Under the loop this is belt-and-braces anyway: `loop.py` caps the whole `mergeit` step at 1200s and will kill it first.

Interpret the exit code:

- **0** — every check passed. Proceed to Step 4.
- **1** — a check **failed** (3a and 3b have already ruled out the no-checks case). Stop and emit `STATUS: MERGE_BLOCKED` as the very last line, reporting which check failed and its log URL. If the output is *still* `no checks reported`, treat it as the 3b timeout: block, don't merge.
- **124** (`timeout` fired) — checks were still pending at the 30-minute cap. Stop and emit `STATUS: MERGE_BLOCKED` as the very last line, reporting which checks were still running and their log URLs.

When `EXPECTS_CI=no`, skip 3b and 3c entirely: say the repo defines no PR-triggered workflow and proceed to Step 4. **"No CI configured" is not a merge blocker** — plenty of repos have none.

`--watch` streams its own progress, so don't add status lines of your own.

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
