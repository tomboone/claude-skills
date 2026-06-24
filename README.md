# claude-skills

Personal Claude Code configuration repo. It holds two things:

1. **The `personal` plugin** — a Linear-driven, Superpowers-backed workflow for taking a project
   from idea → planned tickets → implemented, reviewed PRs, plus a headless loop that drives it
   unattended.
2. **The canonical global `CLAUDE.md`** (`claude-global.md`) — global preferences synced across
   machines via a thin `@`-import in `~/.claude/CLAUDE.md`.

## Repo layout

```
claude-skills/
├── .claude-plugin/marketplace.json     # marketplace manifest ("personal-skills")
├── claude-global.md                    # canonical global CLAUDE.md (see below)
├── plugins/personal/
│   ├── .claude-plugin/plugin.json      # plugin manifest ("personal", v0.3.0)
│   ├── commands/                       # the slash commands (projectit, planit, …)
│   ├── scripts/loop.py                 # headless implementation loop
│   └── spec-and-plan-convention.md     # where specs & plans live on disk
└── .claude/docs/superpowers/           # design specs & plans for this repo's own work
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

Commands are then available as `/personal:<command>` (e.g. `/personal:planit`).

## Commands

The plugin implements a Linear-ticket-driven development pipeline. Every command takes a Linear
ticket ID and re-resolves all its state from that ID plus on-disk docs and GitHub/Linear — so each
runs in a fresh context with no handoff state required.

| Command | Usage | What it does |
|---|---|---|
| `/projectit` | `[--dry-run] ["idea"]` | Scaffolds a whole Linear project from an idea — description, milestones, user stories, work tickets — and pre-generates a design spec per milestone and an implementation plan per ticket. Marks every work ticket `loop-ready`. Front-loads all per-ticket planning so the loop can run `/implementit` directly. |
| `/planit` | `{TICKET_ID}` | Researches a single ticket; if a sufficient spec already exists it says so, otherwise it hands off to Superpowers brainstorming + plan-writing and saves the outputs by convention. The per-ticket alternative to `/projectit`'s bulk planning. |
| `/implementit` | `{TICKET_ID}` | Creates the work branch and executes the ticket's plan via Superpowers `subagent-driven-development` (fresh subagent per task, two-stage review, final whole-branch review). |
| `/shipit` | `{TICKET_ID}` | Commits any outstanding work (Conventional Commit + ticket parenthetical), pushes, and opens a PR against the release branch. Fits the repo's PR template if it has one. |
| `/reviewit` | `{TICKET_ID}` | Reviews the PR via the Superpowers code-reviewer, posts findings as a PR comment, and emits a machine-readable `STATUS: APPROVED` / `STATUS: CHANGES_REQUESTED` final line. |
| `/mergeit` | `{TICKET_ID}` | Waits for CI, squash-merges the PR, deletes the branch, and syncs `main`. The only step that merges — always manual. |

### The two entry points

- **Per-ticket:** `/planit` → `/implementit` → `/shipit` → `/reviewit` → `/mergeit`.
- **Whole-project:** `/projectit` scaffolds and plans an entire project up front, then each ticket
  goes straight to `/implementit` → `/shipit` → `/reviewit` → `/mergeit` (no `/planit` needed).

Ticket statuses are never set by these commands — the GitHub↔Linear connector owns status
transitions based on branch/PR activity.

## The implementation loop

`plugins/personal/scripts/loop.py` is a headless orchestrator (Python 3, standard library only)
that drives the commands non-interactively via `claude -p`. It is the **consumer** of what
`/projectit` produces: per run it processes one wave of `loop-ready` tickets whose blockers are all
`Done`, running `/implementit → /shipit → /reviewit` for each and leaving a reviewed PR open per
ticket.

**It stops before merge** — merging stays a manual, human-gated `/mergeit` step. Re-run it as PRs
merge to pick up the next unblocked wave; the un-started filter makes re-runs idempotent.

Run it from inside the target app's repo (so file reads and git operations resolve there):

```bash
plugins/personal/scripts/loop.py [--project <name>] [--label loop-ready] \
                                 [--tickets ID ...] [--dry-run] [--check] \
                                 [--limit N] [--notify]
```

| Flag | Effect |
|---|---|
| `--project <name>` | Override the project; otherwise inferred from the repo's `linear_initiative:` CLAUDE.md hint. |
| `--label <name>` | Ready-marker label to triage on (default `loop-ready`). |
| `--tickets ID …` | Bypass triage with an explicit ticket list. |
| `--dry-run` | Run read-only triage and print the wave + exact `claude -p` commands without executing. |
| `--check` | Run only the feasibility guard (verifies `claude -p` + Linear/GitHub MCP are reachable). |
| `--limit N` | Cap the wave size. |
| `--notify` | Send a single end-of-run notification. |

**Run flow:** feasibility guard → Linear-MCP triage (returns the wave as JSON) → per-ticket
`implement/ship/review` pipeline (hard failures are recorded and skipped, the run continues) → a
printed summary of per-ticket outcomes plus the held list.

**Models per step:** `implementit`, `shipit`, and triage run on Sonnet; `reviewit` on Opus; the
feasibility guard on Haiku. Planning quality is front-loaded into `/projectit`, so execution runs on
the cheaper tier. The agentic steps run under `--permission-mode bypassPermissions`; safety comes
from `settings.json` deny-rules (which still apply), the loop never invoking `/mergeit`, and every
change landing on a feature branch behind a reviewed PR.

`scripts/test_loop.py` covers the pure-Python parsing/orchestration logic.

## Specs & plan storage

`/projectit`, `/planit`, `/implementit`, and `/reviewit` all resolve where specs and plans live the
same way on every machine, documented in
[`plugins/personal/spec-and-plan-convention.md`](plugins/personal/spec-and-plan-convention.md):

- **`specs_dir` in a project's `CLAUDE.md`** overrides everything.
- Otherwise: **umbrella** layout (a non-git folder holding sibling repos) → `<umbrella>/docs/`;
  **single repo** → `<repo>/.claude/docs/`.
- Specs → `<docs>/superpowers/specs/`, plans → `<docs>/superpowers/plans/`, filenames include the
  ticket ID (`<TICKET-ID>-<slug>.md`).

A repo can also declare `linear_initiative:` / `linear_team:` in its `CLAUDE.md` so `/projectit` and
the loop can resolve the Linear target without searching.

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
