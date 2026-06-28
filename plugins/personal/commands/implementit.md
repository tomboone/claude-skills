# Set up the work branch and execute the implementation plan for a Linear ticket.
# Usage: /personal:implementit {TICKET_ID} [--base <branch>]

## Step 1 — Resolve the docs directory

Determine `DOCS_DIR` (must resolve the same on every machine):
1. **Override:** if any loaded `CLAUDE.md` defines `specs_dir`, `DOCS_DIR` = that value (resolve relative paths from the project root); skip to step 2.
2. Otherwise auto-resolve via `git rev-parse --show-toplevel` and the repo root's parent:
   - **Umbrella layout** — parent is *not* a git repo and holds sibling code repos (e.g. a backend and a frontend): `DOCS_DIR = <umbrella>/docs`.
   - **Single-repo layout** — the repo stands alone: `DOCS_DIR = <repo-root>/.claude/docs`.
   - If genuinely ambiguous, ask the user.

## Step 2 — Locate the plan file

Look for a plan file whose name contains `{TICKET_ID}` (case-insensitive) in **both** supported layouts:
- `DOCS_DIR/superpowers/plans/` — the spec-storage convention.
- `DOCS_DIR/plans/` — the flat layout (some projects store plans directly under `docs/`).

- If exactly one match is found across both, proceed with it.
- If multiple match, list them and ask the user which to use.
- If none match, check for a spec file containing `{TICKET_ID}` in `DOCS_DIR/superpowers/specs/` **and** `DOCS_DIR/specs/` — a spec without a separate plan is acceptable input.
- If nothing is found in either location, stop and tell the user to run `/personal:planit {TICKET_ID}` first. Then, as the **very last line of your response**, emit `STATUS: NO_PLAN` so the headless loop orchestrator records this ticket as *not implemented* instead of marching on to `/personal:shipit`.

## Step 3 — Load the milestone spec (if the plan references one)

Read the chosen plan file. If it contains a line beginning `**Milestone spec:** `, resolve that
relative path (from the plan file's location) and read the referenced milestone spec. Pass **both**
the plan and the milestone spec to the implementation in Step 5 — the plan is the per-ticket slice,
the milestone spec is the shared design context.

If the plan has no such line (e.g. a `/planit`-authored plan), proceed with the plan alone — this
step is a no-op. Backwards-compatible.

## Step 4 — Create the work branch

Derive a branch name from the ticket ID and the plan/spec title: `feat/{TICKET_ID}-short-description` (or `fix/` if the ticket is a bug fix). Use the ticket ID exactly as given — don't assume a project prefix.

**Branch from the resolved base.** Determine `BASE`:
1. If invoked with `--base <branch>` (the loop threads this), use it.
2. Otherwise resolve locally: a `loop_base:` line in the repo `CLAUDE.md`; else the current
   checked-out branch when it is a real integration branch (not detached, not a `feat/*`/`fix/*`
   work branch); else the repo default branch (`git symbolic-ref --short refs/remotes/origin/HEAD`,
   stripped of `origin/`).

Sync the base first so each ticket starts from every prior ticket's merged state, then branch:
```bash
git fetch origin "$BASE"
git checkout -b feat/{TICKET_ID}-short-description "origin/$BASE"
```
(Use the `fix/` prefix for a bug-fix ticket, per the branch-name rule above.) Do **not** prompt for
the base in headless mode — the loop always supplies `--base`.

## Step 5 — Hand off to Superpowers

Invoke `superpowers:subagent-driven-development`, passing the resolved plan file path (and the milestone spec loaded in Step 3, if any, as design context) as the plan to execute.

Let Superpowers run its full subagent-driven execution from here — fresh subagent per task, two-stage review (spec compliance then code quality) after each task, final whole-branch review at the end.

**Stop after that final whole-branch review. Do NOT transition into `superpowers:finishing-a-development-branch`** (the built-in last node of `subagent-driven-development`) and do not present its numbered finishing options. Branch finishing in this workflow is owned by `/personal:shipit` → `/personal:reviewit` → `/personal:mergeit`, not by Superpowers.

Do not implement anything yourself. Do not invoke `/personal:shipit`. When the final review is done, tell the user to clear context and run `/personal:shipit {TICKET_ID}` when ready.

**Completion signal.** Only after the final whole-branch review has actually run, emit — as the **very last line of your response** — `STATUS: IMPLEMENTED`. This is how the headless loop orchestrator (`loop.py`) confirms the plan was executed; if you stopped early for any reason (no plan, ambiguous input, an error), do **not** emit it.
