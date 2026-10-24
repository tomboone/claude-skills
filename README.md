# claude-skills

Personal Claude Code configuration repo. It holds two things:

1. **The `personal` plugin** — a Linear-driven workflow, built on Matt Pocock's engineering skills,
   for taking a project from idea → planned tickets → implemented, reviewed, **merged** PRs.
2. **The canonical global `CLAUDE.md`** (`claude-global.md`) — global preferences synced across
   machines via a thin `@`-import in `~/.claude/CLAUDE.md`.

## Repo layout

```
claude-skills/
├── .claude-plugin/marketplace.json         # marketplace manifest ("personal-skills")
├── claude-global.md                        # canonical global CLAUDE.md (see below)
├── plugins/personal/
│   ├── .claude-plugin/plugin.json          # plugin manifest ("personal", v0.21.0)
│   ├── commands/                           # pipeline commands (projectit, planit, …, mergeit, doit)
│   │                                       # + wrappers for the Pocock skills the pipeline calls
│   ├── spec-and-plan-convention.md         # where specs & plans live on disk
│   ├── pr-resolution-convention.md         # how a command resolves a PR from a ticket ID
│   ├── github-cli-convention.md            # GitHub goes through `gh`, never a GitHub MCP
│   ├── manual-steps-convention.md          # the closing walkthrough of what's left to finish a ticket
│   └── review-context-convention.md        # the cached review-context bundle reviewit/addressit share
└── .claude/docs/                           # design specs & plans for this repo's own work
    └── superpowers/                         # retired layout (older tickets); new docs go to
                                              # .claude/docs/{specs,plans}/, created lazily
```

## Installation

Add the marketplace to Claude Code:

```bash
claude plugin marketplace add --source github --repo tomboone/claude-skills
```

Then enable the plugin:

```bash
claude plugin install personal@personal-skills
```

Commands are then available under their bare names (`/planit`, `/doit`). Each command's
frontmatter declares a bare `name:`, which Claude Code registers as an alias alongside the
namespaced `/personal:<command>` form — both resolve.

## The three layers

The plugin is organized into three layers, all keyed on a Linear ticket ID:

1. **Planning** — shape an idea into Linear tickets (`/projectit`), then plan each ticket just-in-time (`/planit`).
2. **Per-ticket pipeline commands** — each runnable standalone, each re-resolving all of its state
   from the ticket ID plus on-disk docs and GitHub/Linear, so each runs in a fresh context with no
   handoff state required (`/implementit`, `/shipit`, `/mergeit`, plus the manual-only `/reviewit`
   and `/addressit`).
3. **Orchestration** — **`/doit {TICKET_ID}`** chains those pipeline commands into a full
   implement → ship → merge cycle: one ticket, run inline in one Claude Code session. You pick the
   ticket and `/clear` between tickets; the three phases share one warm context.

   `/reviewit` and `/addressit` are **not** part of it (see
   `docs/adr/0005-the-loop-drops-post-ship-review.md`); they remain available as manual commands.
   A headless orchestrator (`loop.py`) used to sit alongside `/doit`; it was retired in
   `docs/adr/0008-retire-the-headless-loop.md`.

## Commands

| Command | Usage | What it does |
|---|---|---|
| `/projectit` | `[--dry-run] ["idea"]` | **Planning (project shaping).** Runs a `/grilling` + `/domain-modeling` session on the idea, writes a project-wide spec to disk, then turns it into a Linear project — description (with a pointer to the spec), milestones (each with a **Shared contracts** section), user stories, and work tickets — and creates them in Linear. Every work ticket gets a `repo:<name>` label. Before creating them, it checks each ticket against the project-wide spec using `/planit`'s sufficiency standard and labels any it doesn't cover `planit` (with the reason shown at the gate, overridable); unlabelled tickets are implementable straight away via `/doit` with no `/planit` pass. Multi-repo projects tag each ticket with a `**Target repo:**` line. |
| `/planit` | `{TICKET_ID}` | **Planning (per-ticket, just-in-time — optional unless the ticket is labelled `planit`).** Researches a single ticket — including its parent milestone's shared contracts, the project-wide spec (if any), and any already-merged dependencies' shipped specs/code — then, if that's not already sufficient, runs a `/grilling` + `/domain-modeling` session and saves the resulting spec by convention so `/implementit` finds it by ticket ID. Removes the ticket's `planit` label when done. Required before `/implementit` only on tickets labelled `planit`; otherwise useful when a ticket needs deeper per-ticket planning than the project-wide spec gives it. |
| `/implementit` | `{TICKET_ID}` | Creates the work branch and implements the ticket's spec/plan inline (single-pass implementation, with an internal `/code-review` pass before shipping that fixes hard violations and genuine defects, leaving judgement-call smells to a summary). Resolves design context in order: a per-ticket file named for the ticket, then a `Spec:`/`Plan:` pointer in the ticket's own Linear description (globs resolved), then the Linear **project's** `**Project spec:**` pointer (skipped while the ticket is labelled `planit`) — only emitting `STATUS: NO_PLAN` when all three come back empty. If the ticket needs no repository change at all, creates no branch and instead gives the manual-steps walkthrough as the implementation (`STATUS: NO_CODE`). Emits `STATUS: IMPLEMENTED`. |
| `/shipit` | `{TICKET_ID}` | Commits any outstanding work (Conventional Commit + ticket parenthetical), pushes, and opens a PR against the release branch. Fits the repo's PR template if it has one. |
| `/reviewit` | `{TICKET_ID}` | **Manual only — not run by `/doit`.** Reviews the PR via `/code-review`, **building on any prior review rounds** (reads the existing review thread so re-reviews don't re-flag resolved items), posts findings as a `## Code Review` comment (Standards + Spec axes), and emits `STATUS: APPROVED` / `STATUS: CHANGES_REQUESTED`. |
| `/addressit` | `{TICKET_ID}` | **Manual only — not run by `/doit`.** Responds to `/reviewit`'s latest findings: implements valid fixes (testing as it goes), **pushes back with reasoning on findings that are wrong / out of scope / conflict with the spec**, pushes fixes to the PR branch, posts a `## Review Response` comment, and emits `STATUS: ADDRESSED` / `STATUS: PUSHED_BACK` / `STATUS: BLOCKED`. |
| `/doit` | `{TICKET_ID} [--base <branch>] [--no-merge]` | **The attended pipeline.** Runs `/implementit` → `/shipit` → `/mergeit` inline in one session, taking a single unblocked ticket from planned to merged on one command. The user picks the ticket and `/clear`s between tickets, and the three phases share one warm context instead of three cold `claude -p` starts. Verifies the ticket's `blockedBy` blockers are `Done` first. Stops on the first phase that fails (`NO_PLAN` / `FAILED` / `MERGE_BLOCKED`) and reports why. A ticket that needs no repository change (`NO_CODE`) skips ship and merge. Every run that merged, stopped at an open PR, or found a no-code ticket ends with a **manual-steps walkthrough**: exact commands or click-by-click steps for whatever is still needed to close the ticket (see `manual-steps-convention.md`). See `docs/adr/0007-doit-is-the-attended-single-ticket-pipeline.md`. |
| `/mergeit` | `{TICKET_ID}` | Waits for CI, then merges the PR **with the strategy that matches its base** — squash into a `release/*` branch (one commit per ticket), merge commit into the default branch (preserves history when a release branch integrates). Deletes the branch and syncs the PR's base branch. Detects whether the repo runs PR CI by reading `.github/workflows/` (not by trusting `gh pr checks`, which can't distinguish "no CI" from "not registered yet"), waits up to 10 min for a check to register and 30 min for it to finish, and **blocks rather than merging** if a `pull_request` workflow exists but no check appears. Blocks on an explicit "Needs changes" review verdict; a *missing* review comment does not block. After merging, ends with a **manual-steps walkthrough** of anything still needed to close the ticket — deploys, migrations, secrets, executing a delivered runbook — with exact commands. Emits `STATUS: MERGED` / `STATUS: MERGE_BLOCKED`. |

### Skills the pipeline calls

Four skills installed from the `mattpocock/skills` marketplace are invoked directly by name. They
used to sit behind `/personal:*` wrapper commands; those were removed when the pipeline's commands
took bare names, because a wrapper and the skill it wraps would then compete for the same slash
command — and a plugin command's bare alias is dropped when it collides with an installed skill.
The policy each wrapper carried moved into its callers:

| Skill | Called by | Where the wrapper's policy lives now |
|---|---|---|
| `code-review` | `/implementit` (pre-ship), `/reviewit` (on the PR) | Both callers state the sub-agent model routing themselves — **Standards** on Haiku (rubric matching), **Spec** on the session model (judgement). `/implementit` also owns the severity scoping it applies to the findings: fix hard violations and real defects, list the Fowler judgement-call smells rather than refactoring them (ADR 0006). `/reviewit` reports rather than applies, so the scoping does not bind it. |
| `tdd` | `/implementit` | Step 1 of `/implementit` carries the "at pre-agreed seams, where the repo's conventions call for it" framing — not a blanket instruction to test-drive everything, and not an override of a repo whose `CLAUDE.md` says otherwise. |
| `grilling` | `/planit` (Step 4), `/projectit` (Phase 1) | Both callers state the interview protocol inline: one `AskUserQuestion` per question, 2–4 keystroke-answerable options, recommendation first. The skill itself only says "one at a time" — the option protocol is this repo's addition, so it has to travel with the callers. |
| `domain-modeling` | `/planit` (Step 4), `/projectit` (Phase 1) | Same pairing, plus the expectation that `CONTEXT.md` and ADRs are updated inline. Neither skill writes the spec file — the calling command does that once the session lands. |

Calling them by name also keeps the plugin's dependency on `mattpocock/skills` visible rather than
implicit: if a skill is missing, the caller names it.

### The two entry points

- **Per-ticket:** `/implementit` → `/shipit` → `/mergeit`, with an optional `/planit` first for
  deeper per-ticket planning, and an optional `/reviewit` ↔ `/addressit` pass between ship and merge
  when a PR warrants a second opinion. **`/doit {TICKET_ID}` runs those three in one go** — use it
  when you don't need to stop between phases, and `/clear` before the next ticket.
- **Whole-project:** `/projectit` shapes the project into tickets up front, labelling `planit` any
  the project-wide spec doesn't cover; then **each ticket follows the per-ticket flow** above — by
  hand, or via `/doit` one ticket at a time, with `/planit` first on the labelled ones.

When run by hand, the `/reviewit` ↔ `/addressit` step alternates until the reviewer returns
`APPROVED` (or the two reach an impasse). Ticket statuses are never set by these commands — the GitHub↔Linear connector
owns status transitions based on branch/PR activity, up to **Merged** on merge. **Done** is yours to
set, once the manual-steps walkthrough is finished (`docs/adr/0010-done-means-the-manual-steps-are-finished.md`).

## `/doit` — one ticket, one session

```
/doit NEU-742          # implement → ship → merge, then stop
/doit NEU-742 --no-merge   # stop once the PR is open
/doit NEU-742 --base release/1.4
```

The working rhythm is: `/doit <ticket>` → let it finish → `/clear` (or `/compact`) →
`/doit <next ticket>`. It checks that the ticket's `blockedBy` blockers are `Done`, then
invokes the three pipeline commands via the Skill tool, which loads each one **inline, in this
session** — no sub-agents, no `claude -p` — so
`shipit` and `mergeit` reuse the branch, base, spec, and diff `implementit` already resolved.

Its gates: the mandatory pre-ship `/code-review` pass, CI as the merge gate, `MERGE_BLOCKED`
instead of a forced merge, and `/reviewit` staying manual. Merging is on by default; pass
`--no-merge` on repos where PRs need team approval. `docs/adr/0007-doit-is-the-attended-single-ticket-pipeline.md`
records why it exists, and `docs/adr/0008-retire-the-headless-loop.md` why it replaced the loop.

## Conventions

Several commands share on-disk conventions so they behave identically on every machine:

- **[`spec-and-plan-convention.md`](plugins/personal/spec-and-plan-convention.md)** — where specs and
  plans live. Used by `/planit`, `/implementit`, `/reviewit`, `/addressit`.
  - **`specs_dir` in a project's `CLAUDE.md`** overrides everything.
  - Otherwise: **umbrella** layout (a non-git folder holding sibling repos) → `<umbrella>/docs/`;
    **single repo** → `<repo>/.claude/docs/`.
  - Specs → `<docs>/specs/`, plans → `<docs>/plans/`, filenames include the
    ticket ID (`<TICKET-ID>-<slug>.md`). Older tickets may still use the retired
    `<docs>/superpowers/{specs,plans}/` layout — commands check both.
- **[`pr-resolution-convention.md`](plugins/personal/pr-resolution-convention.md)** — how
  `/reviewit`, `/addressit`, and `/mergeit` resolve a `PR_NUMBER` from a ticket ID (head branch, then
  title fallback).
- **[`review-context-convention.md`](plugins/personal/review-context-convention.md)** — the cached
  review-context bundle (Linear intent + spec/plan) that `/reviewit` and `/addressit` load-or-generate
  so a review and its response measure the PR against the same ground truth.
- **[`manual-steps-convention.md`](plugins/personal/manual-steps-convention.md)** — the closing
  walkthrough of what's left to finish a ticket after (or instead of) its merge: where to look for
  manual work, and how to write each step — exact, repo-grounded commands, click-by-click UI steps, a
  check per step, an explicit "no other steps" when nothing remains, and always a closing step for
  you to move the ticket to Done. Used by `/mergeit`, `/doit`, and
  `/implementit`'s no-code path.
- **[`github-cli-convention.md`](plugins/personal/github-cli-convention.md)** — every GitHub
  operation goes through the **`gh` CLI**, never a GitHub MCP server. `gh` is present and
  authenticated everywhere these commands run; a GitHub MCP is configured per-project and absent
  from most, so a command that reaches for one works in one repo and stalls headlessly in the rest.
  Used by `/shipit`, `/mergeit`, `/reviewit`, `/addressit`, and `pr-resolution-convention.md`.

A repo can also declare hint keys in its `CLAUDE.md` so the commands can resolve their targets
without searching:

- `linear_initiative: <name>` — the Linear initiative (project group) this repo belongs to.
- `linear_team: <name>` — the Linear team to create tickets under.
- `linear_repo: <name>` — overrides the auto-derived repo label (`repo:<name>`) `/projectit` puts on
  tickets it creates in this repo. Otherwise `<name>` is the basename of `git remote get-url origin`.
- `linear_repos: [<name>, <name>, …]` — for `/projectit`: the canonical repo names a project's
  tickets may target, so each ticket can carry the right `**Target repo:**` line at creation.
- `loop_base: <branch>` — the base branch `/implementit` branches from and `/shipit` targets, when
  `--base` isn't passed. (The name predates the loop's retirement and is kept for compatibility.)

## The canonical global `CLAUDE.md`

`claude-global.md` is the **single source of truth** for global Claude Code preferences (git/commit
conventions, the attribution footer, Python style, project-type rules, the spec convention).

`~/.claude/CLAUDE.md` is a thin wrapper that imports it:

```markdown
@~/claude-skills/claude-global.md
```

This keeps preferences version-controlled and identical across machines: clone the repo to
`~/claude-skills`, point `~/.claude/CLAUDE.md` at it with that one `@`-import line, and every machine
picks up the same rules. **Edit `claude-global.md` here — never the wrapper.**
