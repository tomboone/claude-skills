# Commit any uncommitted work, push the branch, and open a PR against the release branch (or the repo's default branch when there is none).
# Usage: /personal:shipit {TICKET_ID}

## Step 1 — Guard rails

Confirm we're not on main or a release branch. If we are, stop and tell the user.

Confirm the current branch corresponds to `{TICKET_ID}` — its name should contain the ticket ID (e.g. `feat/{TICKET_ID}-…`). If it doesn't, warn the user and ask them to confirm before continuing.

## Step 2 — Determine project type

Get the repo root with `git rev-parse --show-toplevel`.
- If that path is inside `~/ingest/` (i.e. `$HOME/ingest/…`) → **ingest (work) project**.
- Otherwise → **personal project**.

This selects how the commit message and PR description are generated below.

## Step 3 — Commit any uncommitted changes

If uncommitted changes exist:

1. Generate a one-line Conventional Commit message:
   - **Ingest project:** invoke the `localdev:commit-msg` skill to generate it.
   - **Personal project:** generate it inline — read the diff (`git diff HEAD`), use any active plan or conversation context for the *why*, and write a single-line Conventional Commit message: imperative mood, ≤72 chars, no trailing period, focused on what + why (e.g. `fix(api): guard against null session token`).
2. Append `{TICKET_ID}` as a **trailing parenthetical**: `feat(scope): description ({TICKET_ID})`.
3. Stage and commit. **No co-author line. No footer in commit messages.**

## Step 4 — Push

Push the current branch to origin if it isn't already up to date.

## Step 5 — Identify the base branch

Resolve the PR base, `BASE`, **without blocking on a question when a sane default exists** — this command runs headlessly under the loop orchestrator, so a prompt to the user hangs the run and produces no PR:

1. Look for branches matching `release/v*` (`git branch --list 'release/v*'`).
   - **Exactly one** → that's `BASE`.
   - **More than one** → take the highest version: `git branch --list 'release/v*' | sed 's/^[* ]*//' | sort -V | tail -1`. (Only ask the user if one is genuinely present and the ordering is ambiguous.)
2. **No `release/v*` branch** → fall back to the repo's default branch (normally `main`): `git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##'`, or if that's unset, `git remote show origin | sed -n 's/.*HEAD branch: //p'`. Use that as `BASE`.
3. Only ask the user if **none** of the above resolves a branch *and* a user is present to answer; in headless mode, default to `main`.

## Step 6 — Build the PR description

1. **Generate the raw description** (diff against `BASE`):
   - **Ingest project:** invoke the `localdev:pr-desc` skill and use the description it produces.
   - **Personal project:** generate it inline — read `git log BASE..HEAD` and `git diff BASE..HEAD`, fold in any plan/conversation context, and write:

     ```markdown
     ## Summary
     - <what changed and why, scaled to the size of the changeset>

     ## Changes
     - <meaningful changes grouped logically>

     ## Test plan
     - [ ] <testing considerations>
     ```

2. **Fit a PR template if the repo has one.** Check for a template at `.github/pull_request_template.md`, `.github/PULL_REQUEST_TEMPLATE.md`, a root `pull_request_template.md`, `docs/pull_request_template.md`, or any file under `.github/PULL_REQUEST_TEMPLATE/`. If one exists:
   - Rewrite the generated content to fit the template's structure and section headings rather than appending your own.
   - **Preserve every checkbox from the template, including unchecked ones — never omit them.** Check a box only when the change genuinely satisfies it; otherwise leave it unchecked (`- [ ]`).
   - Keep any other required template fields/sections; fill them from the generated content where you can, and leave a clear placeholder where you can't.

3. **Append the footer** to the body (always, after fitting the template). Don't duplicate it if the generator already added it:

   ```
   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   ```

## Step 7 — Create the PR

Use `gh pr create` with:
- Base: `BASE`
- Title: a Conventional Commit subject describing the branch's primary change, with `{TICKET_ID}` as a **trailing parenthetical**: `feat(ingestion): add endpoint ({TICKET_ID})`.
- Body: the description assembled in Step 6.
- No co-author attribution anywhere.

## Step 8 — Hand off

Show the PR URL. Tell the user to clear context and run `/personal:reviewit {TICKET_ID}` when ready. Stop here — do not wait for CI, do not merge.
