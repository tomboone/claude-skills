# claude-skills

Personal Claude Code configuration repo. It holds two things:

1. **The `personal` plugin** — a Linear-driven, Superpowers-backed workflow for taking a project
   from idea → planned tickets → implemented, reviewed, **merged** PRs, plus a headless loop that
   drives the whole cycle unattended.
2. **The canonical global `CLAUDE.md`** (`claude-global.md`) — global preferences synced across
   machines via a thin `@`-import in `~/.claude/CLAUDE.md`.

## Repo layout

```
claude-skills/
├── .claude-plugin/marketplace.json         # marketplace manifest ("personal-skills")
├── claude-global.md                        # canonical global CLAUDE.md (see below)
├── plugins/personal/
│   ├── .claude-plugin/plugin.json          # plugin manifest ("personal", v0.7.0)
│   ├── commands/                           # the slash commands (projectit, planit, …, mergeit)
│   ├── scripts/loop.py                     # headless autonomous loop (+ test_loop.py)
│   ├── spec-and-plan-convention.md         # where specs & plans live on disk
│   ├── pr-resolution-convention.md         # how a command resolves a PR from a ticket ID
│   └── review-context-convention.md        # the cached review-context bundle reviewit/addressit share
└── .claude/docs/superpowers/               # design specs & plans for this repo's own work
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

## The three layers

The plugin is organized into three layers, all keyed on a Linear ticket ID:

1. **Planning** — turn ideas into `loop-ready` tickets with specs and plans (`/projectit`, `/planit`).
2. **Per-ticket pipeline commands** — each runnable standalone, each re-resolving all of its state
   from the ticket ID plus on-disk docs and GitHub/Linear, so each runs in a fresh context with no
   handoff state required (`/implementit`, `/shipit`, `/reviewit`, `/addressit`, `/mergeit`).
3. **The loop** — a headless orchestrator (`scripts/loop.py`) that chains the pipeline commands into
   an autonomous, end-to-end implement → ship → review ↔ address → merge cycle.

## Commands

| Command | Usage | What it does |
|---|---|---|
| `/projectit` | `[--dry-run] ["idea"]` | **Planning (bulk).** Scaffolds a whole Linear project from an idea — description, milestones, user stories, work tickets — and pre-generates a design spec per milestone and an implementation plan per ticket. Marks every work ticket `loop-ready`. Front-loads all per-ticket planning so the loop can run `/implementit` directly. |
| `/planit` | `{TICKET_ID}` | **Planning (per-ticket).** Researches a single ticket; if a sufficient spec already exists it says so, otherwise it hands off to Superpowers brainstorming + plan-writing and saves the outputs by convention. The per-ticket alternative to `/projectit`'s bulk planning. |
| `/implementit` | `{TICKET_ID}` | Creates the work branch and executes the ticket's plan via Superpowers `subagent-driven-development` (fresh subagent per task, two-stage review, final whole-branch review). Emits `STATUS: IMPLEMENTED`. |
| `/shipit` | `{TICKET_ID}` | Commits any outstanding work (Conventional Commit + ticket parenthetical), pushes, and opens a PR against the release branch. Fits the repo's PR template if it has one. |
| `/reviewit` | `{TICKET_ID}` | Reviews the PR via the Superpowers code-reviewer, **building on any prior review rounds** (reads the existing review thread so re-reviews don't re-flag resolved items), posts findings as a `## Code Review` comment, and emits `STATUS: APPROVED` / `STATUS: CHANGES_REQUESTED`. |
| `/addressit` | `{TICKET_ID}` | Responds to `/reviewit`'s latest findings via Superpowers `receiving-code-review`: implements valid fixes (testing as it goes), **pushes back with reasoning on findings that are wrong / out of scope / conflict with the spec**, pushes fixes to the PR branch, posts a `## Review Response` comment, and emits `STATUS: ADDRESSED` / `STATUS: PUSHED_BACK` / `STATUS: BLOCKED`. |
| `/mergeit` | `{TICKET_ID}` | Waits for CI, squash-merges the PR, deletes the branch, and syncs `main`. Emits `STATUS: MERGED` / `STATUS: MERGE_BLOCKED`. |

### The two entry points

- **Per-ticket:** `/planit` → `/implementit` → `/shipit` → `/reviewit` ↔ `/addressit` → `/mergeit`.
- **Whole-project:** `/projectit` scaffolds and plans an entire project up front, then each ticket
  goes straight to `/implementit` → `/shipit` → `/reviewit` ↔ `/addressit` → `/mergeit` (no
  `/planit` needed).

The `/reviewit` ↔ `/addressit` step alternates until the reviewer returns `APPROVED` (or the two
reach an impasse). Ticket statuses are never set by these commands — the GitHub↔Linear connector
owns status transitions based on branch/PR activity.

## The autonomous loop

`plugins/personal/scripts/loop.py` is a headless orchestrator (Python 3, standard library only)
that drives the commands non-interactively via `claude -p`. It is the **consumer** of what
`/projectit` produces: per run it processes one wave of `loop-ready` tickets whose blockers are all
`Done`, driving each ticket all the way to a merged PR before starting the next — so each new branch
roots on an up-to-date `main` and downstream conflicts shrink.

### Per-ticket state machine

For each ticket the loop runs:

```
implementit → shipit → ┌─ reviewit ──→ APPROVED ──[--merge]──→ mergeit ─→ MERGED
                       │     │                 │                    │
                       │     │                 └─[no --merge]──→ READY_FOR_REVIEW
                       │     └─ CHANGES_REQUESTED → addressit ─┐   └─ MERGE_BLOCKED → NEEDS_HUMAN
                       │                                       │
                       └──────────── ADDRESSED (re-review) ◀───┘
                                     PUSHED_BACK / BLOCKED ──────→ NEEDS_HUMAN
                                     rounds exhausted ───────────→ NEEDS_HUMAN
```

- The review ↔ address alternation is **bounded** by `--max-rounds` (default 3). One round =
  one `reviewit` + (if not approved) one `addressit`.
- A ticket is merged only after an `APPROVED` verdict **and only when `--merge` is set**; otherwise an APPROVED verdict leaves the PR at `READY_FOR_REVIEW` for a human/team to merge.
- Any **stall** — an impasse (`PUSHED_BACK`), `addressit` `BLOCKED`, rounds exhausted without
  approval, or `MERGE_BLOCKED` — records the ticket's disposition as `NEEDS_HUMAN` with a reason and
  **continues to the next ticket**. The wave is never stopped by a single stalled ticket.
- Hard failures of a step (non-zero exit / timeout / missing sentinel) are recorded as `FAILED` and
  the loop moves on.

Re-run the loop as tickets merge to pick up the next newly-unblocked wave (tickets whose blockers
are now `Done`).

### Usage

Run it from inside the target app's repo (so file reads and git operations resolve there):

```bash
plugins/personal/scripts/loop.py [--project <name>] [--label loop-ready] \
                                 [--tickets ID ...] [--dry-run] [--check] \
                                 [--limit N] [--notify [backend]] [--max-rounds N] [--detach] [--merge]
```

| Flag | Effect |
|---|---|
| `--project <name>` | Override the project; otherwise inferred from the repo's `linear_initiative:` CLAUDE.md hint. |
| `--label <name>` | Ready-marker label to triage on (default `loop-ready`). |
| `--tickets ID …` | Bypass triage with an explicit ticket list. |
| `--dry-run` | Run read-only triage and print the wave + the exact `claude -p` commands (including the bounded review↔address step and the merge/stop step) without executing. |
| `--check` | Run only the feasibility guard (verifies `claude -p` + Linear/GitHub MCP are reachable). |
| `--limit N` | Cap the wave size. |
| `--notify [backend]` | Send a notification as each ticket finishes (with its final disposition) and once at the end of the run. Bare `--notify` posts a native **macOS** banner; `--notify pushover` sends via **Pushover** (requires `PUSHOVER_APP_TOKEN` and `PUSHOVER_USER_KEY` env vars). Off by default. Missing credentials or an unknown backend fail silently — the loop is never affected. |
| `--max-rounds N` | Cap the review ↔ address rounds per ticket (default 3); exhausting them stalls the ticket as `NEEDS_HUMAN`. |
| `--detach` | Background the run: re-launch detached, write stdout/stderr to a timestamped `<repo>/.claude/loop/run-*.log` (self-`.gitignore`d), print a `tail -f` watch command, and return immediately. |
| `--merge` | Run `mergeit` after the review↔address loop reaches APPROVED. **Off by default** — without it the loop stops at the `READY_FOR_REVIEW` disposition (PR opened and loop-approved, left for a human/team to merge). Use it on repos where auto-merge is wanted; omit it where PRs require team approval. |

**Run flow:** feasibility guard → Linear-MCP triage (returns the wave as JSON) → per-ticket state
machine (implement → ship → review ↔ address until approved or stalled → merge/stop) → a printed
summary showing each ticket's **disposition** (`MERGED` / `READY_FOR_REVIEW` / `NEEDS_HUMAN` /
`FAILED`), **round count**, and a **per-step usage/cost breakdown**, plus the held list.
`READY_FOR_REVIEW` means the review↔address loop reached APPROVED and `--merge` was not set — the PR
is open and ready for the human/team to merge.

### Models & effort per step

Cost levers are parameterized in `default_models()` / `default_efforts()` (defaults below, flagged
to retune from real usage data — not final):

| Step | Model | Effort |
|---|---|---|
| `implementit` | Sonnet | high |
| `shipit` | Sonnet | low |
| `reviewit` (round 1) | Opus | high |
| `reviewit` (re-review, rounds ≥2) | Sonnet | medium |
| `addressit` | Sonnet | medium |
| `mergeit` | Haiku | low |
| triage | Sonnet | medium |
| feasibility guard | Haiku | low |

Planning quality is front-loaded into `/projectit`, and the first review gets the heaviest model;
re-reviews and the mechanical merge step run on the cheaper tier.

### Observability

The pipeline emits flushed, timestamped `[HH:MM:SS]` progress lines on entry to each step
(`implementit`, `shipit`, `reviewit (round r)`, `addressit (round r)`, `mergeit`), plus wave start,
per-ticket start, and per-ticket disposition. With `--detach` those lines stream to the log file, so
`tail -f <logpath>` shows live progress.

### Safety

The agentic steps run under `--permission-mode bypassPermissions`. Safety comes from: the
`settings.json` deny-rules (which still apply); every change landing on a feature branch behind a
reviewed PR; the loop **merging only after an `APPROVED` verdict**; bounded review rounds; and
stalls / merge-blocks escalating to `NEEDS_HUMAN` rather than being forced through.

`scripts/test_loop.py` covers the pure-Python parsing/orchestration logic (parsers, state-machine
transitions, model/effort routing, max-rounds boundary, detach helpers, and summary rendering).

## Conventions

Several commands share on-disk conventions so they behave identically on every machine:

- **[`spec-and-plan-convention.md`](plugins/personal/spec-and-plan-convention.md)** — where specs and
  plans live. Used by `/projectit`, `/planit`, `/implementit`, `/reviewit`, `/addressit`.
  - **`specs_dir` in a project's `CLAUDE.md`** overrides everything.
  - Otherwise: **umbrella** layout (a non-git folder holding sibling repos) → `<umbrella>/docs/`;
    **single repo** → `<repo>/.claude/docs/`.
  - Specs → `<docs>/superpowers/specs/`, plans → `<docs>/superpowers/plans/`, filenames include the
    ticket ID (`<TICKET-ID>-<slug>.md`).
- **[`pr-resolution-convention.md`](plugins/personal/pr-resolution-convention.md)** — how
  `/reviewit`, `/addressit`, and `/mergeit` resolve a `PR_NUMBER` from a ticket ID (head branch, then
  title fallback).
- **[`review-context-convention.md`](plugins/personal/review-context-convention.md)** — the cached
  review-context bundle (Linear intent + spec/plan) that `/reviewit` and `/addressit` load-or-generate
  so a review and its response measure the PR against the same ground truth.

A repo can also declare hint keys in its `CLAUDE.md` so `/projectit` and the loop can resolve the
Linear target without searching:

- `linear_initiative: <name>` — the Linear initiative (project group) this repo belongs to.
- `linear_team: <name>` — the Linear team to create tickets under.
- `linear_repo: <name>` — overrides the loop's auto-derived repo label (`repo:<name>`). The loop
  otherwise derives `<name>` from `git remote get-url origin` (basename). Used to filter triage to
  this repo's tickets within a multi-repo project.
- `linear_repos: [<name>, <name>, …]` — for `/projectit`: the canonical repo names a project's
  tickets may target, so each ticket can be tagged with the right `repo:<name>` at creation.

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
