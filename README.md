# claude-skills

Personal Claude Code configuration repo. It holds two things:

1. **The `personal` plugin** — a Linear-driven workflow, built on Matt Pocock's engineering skills,
   for taking a project from idea → planned tickets → implemented, reviewed, **merged** PRs, plus a
   headless loop that drives the whole cycle unattended.
2. **The canonical global `CLAUDE.md`** (`claude-global.md`) — global preferences synced across
   machines via a thin `@`-import in `~/.claude/CLAUDE.md`.

## Repo layout

```
claude-skills/
├── .claude-plugin/marketplace.json         # marketplace manifest ("personal-skills")
├── claude-global.md                        # canonical global CLAUDE.md (see below)
├── plugins/personal/
│   ├── .claude-plugin/plugin.json          # plugin manifest ("personal", v0.19.0)
│   ├── commands/                           # pipeline commands (projectit, planit, …, mergeit, doit)
│   │                                       # + wrappers for the Pocock skills the pipeline calls
│   ├── scripts/loop.py                     # headless autonomous loop (+ test_loop.py)
│   ├── spec-and-plan-convention.md         # where specs & plans live on disk
│   ├── pr-resolution-convention.md         # how a command resolves a PR from a ticket ID
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

Commands are then available as `/personal:<command>` (e.g. `/personal:planit`).

## The three layers

The plugin is organized into three layers, all keyed on a Linear ticket ID:

1. **Planning** — shape an idea into Linear tickets (`/projectit`), then plan each ticket just-in-time (`/planit`).
2. **Per-ticket pipeline commands** — each runnable standalone, each re-resolving all of its state
   from the ticket ID plus on-disk docs and GitHub/Linear, so each runs in a fresh context with no
   handoff state required (`/implementit`, `/shipit`, `/mergeit`, plus the manual-only `/reviewit`
   and `/addressit`).
3. **Orchestration** — two ways to chain those pipeline commands into a full implement → ship →
   merge cycle:
   - **`/doit {TICKET_ID}`** — *attended*. One ticket, run inline in one Claude Code session. You
     pick the ticket and `/clear` between tickets; the three phases share one warm context.
   - **`scripts/loop.py`** — *headless*. Whole waves of `loop-ready` tickets, unattended, each step
     its own `claude -p` process.

   `/reviewit` and `/addressit` are **not** part of either (see
   `docs/adr/0005-the-loop-drops-post-ship-review.md`); they remain available as manual commands.

## Commands

| Command | Usage | What it does |
|---|---|---|
| `/projectit` | `[--dry-run] ["idea"]` | **Planning (project shaping).** Runs a `/grilling` + `/domain-modeling` session on the idea, writes a project-wide spec to disk, then turns it into a Linear project — description (with a pointer to the spec), milestones (each with a **Shared contracts** section), user stories, and work tickets — and creates them in Linear. Work tickets default to the `loop-ready` and `repo:<name>` labels (deselectable per ticket at the gate), so they're immediately eligible for the loop with no `/planit` pass required. Multi-repo projects tag each ticket with a `**Target repo:**` line. |
| `/planit` | `{TICKET_ID}` | **Planning (per-ticket, just-in-time — optional).** Researches a single ticket — including its parent milestone's shared contracts, the project-wide spec (if any), and any already-merged dependencies' shipped specs/code — then, if that's not already sufficient, runs a `/grilling` + `/domain-modeling` session and saves the resulting spec by convention so `/implementit` finds it by ticket ID. Not required before `/implementit`; useful when a ticket needs deeper per-ticket planning than the project-wide spec gives it. |
| `/implementit` | `{TICKET_ID}` | Creates the work branch and implements the ticket's spec/plan inline (single-pass implementation, with an internal `/personal:code-review` pass before shipping that fixes hard violations and genuine defects, leaving judgement-call smells to a summary). Resolves design context in order: a per-ticket file named for the ticket, then a `Spec:`/`Plan:` pointer in the ticket's own Linear description (globs resolved), then the Linear **project's** `**Project spec:**` pointer — only emitting `STATUS: NO_PLAN` when all three come back empty. Emits `STATUS: IMPLEMENTED`. |
| `/shipit` | `{TICKET_ID}` | Commits any outstanding work (Conventional Commit + ticket parenthetical), pushes, and opens a PR against the release branch. Fits the repo's PR template if it has one. |
| `/reviewit` | `{TICKET_ID}` | **Manual only — not run by the loop.** Reviews the PR via `/personal:code-review`, **building on any prior review rounds** (reads the existing review thread so re-reviews don't re-flag resolved items), posts findings as a `## Code Review` comment (Standards + Spec axes), and emits `STATUS: APPROVED` / `STATUS: CHANGES_REQUESTED`. |
| `/addressit` | `{TICKET_ID}` | **Manual only — not run by the loop.** Responds to `/reviewit`'s latest findings: implements valid fixes (testing as it goes), **pushes back with reasoning on findings that are wrong / out of scope / conflict with the spec**, pushes fixes to the PR branch, posts a `## Review Response` comment, and emits `STATUS: ADDRESSED` / `STATUS: PUSHED_BACK` / `STATUS: BLOCKED`. |
| `/doit` | `{TICKET_ID} [--base <branch>] [--no-merge]` | **The attended pipeline.** Runs `/implementit` → `/shipit` → `/mergeit` inline in one session, taking a single unblocked ticket from planned to merged on one command. Same state machine as the loop, but attended: the user picks the ticket and `/clear`s between tickets, and the three phases share one warm context instead of three cold `claude -p` starts. Verifies the ticket's `blockedBy` blockers are `Done` first — the `loop-ready` label is deliberately **not** required, since a human chose the ticket. Stops on the first phase that fails (`NO_PLAN` / `FAILED` / `MERGE_BLOCKED`) and reports why. See `docs/adr/0007-doit-is-the-attended-single-ticket-pipeline.md`. |
| `/mergeit` | `{TICKET_ID}` | Waits for CI, then merges the PR **with the strategy that matches its base** — squash into a `release/*` branch (one commit per ticket), merge commit into the default branch (preserves history when a release branch integrates). Deletes the branch and syncs the PR's base branch. Detects whether the repo runs PR CI by reading `.github/workflows/` (not by trusting `gh pr checks`, which can't distinguish "no CI" from "not registered yet"), waits up to 10 min for a check to register and 30 min for it to finish, and **blocks rather than merging** if a `pull_request` workflow exists but no check appears. Blocks on an explicit "Needs changes" review verdict; a *missing* review comment does not block. Emits `STATUS: MERGED` / `STATUS: MERGE_BLOCKED`. |

### Wrappers for the Pocock skills

Four commands wrap skills installed from the `mattpocock/skills` marketplace, so the pipeline calls
a name this repo controls rather than a vendored skill directly:

| Wrapper | Wraps | What the wrapper adds |
|---|---|---|
| `/personal:code-review` | `code-review` | Routes the **Standards** sub-agent to Haiku (rubric matching) and keeps **Spec** on the session model (judgement). Owns the severity scoping `/personal:implementit` applies to the findings — fix hard violations and real defects, list the Fowler judgement-call smells rather than refactoring them (ADR 0006). |
| `/personal:tdd` | `tdd` | The "at pre-agreed seams, where the repo's conventions call for it" framing `/personal:implementit` uses — not a blanket instruction to test-drive everything. |
| `/personal:grilling` | `grilling` | Notes that `/personal:planit` and `/personal:projectit` run it alongside domain-modeling, and that neither writes the spec file. |
| `/personal:domain-modeling` | `domain-modeling` | Same pairing, plus the expectation that `CONTEXT.md` and ADRs are updated inline. |

They also make the plugin's dependency on `mattpocock/skills` visible instead of implicit. The
skills stay usable directly (`/code-review`, `/tdd`, …) for one-off work.

### The two entry points

- **Per-ticket:** `/implementit` → `/shipit` → `/mergeit`, with an optional `/planit` first for
  deeper per-ticket planning, and an optional `/reviewit` ↔ `/addressit` pass between ship and merge
  when a PR warrants a second opinion. **`/doit {TICKET_ID}` runs those three in one go** — use it
  when you don't need to stop between phases, and `/clear` before the next ticket.
- **Whole-project:** `/projectit` shapes the project into tickets up front, labeling each
  `loop-ready`; then **each ticket follows the per-ticket flow** above — by hand, via `/doit`
  one ticket at a time, or unattended via `plugins/personal/scripts/loop.py`.

When run by hand, the `/reviewit` ↔ `/addressit` step alternates until the reviewer returns
`APPROVED` (or the two reach an impasse). Ticket statuses are never set by these commands — the GitHub↔Linear connector
owns status transitions based on branch/PR activity.

## `/doit` — one ticket, one session

```
/personal:doit NEU-742          # implement → ship → merge, then stop
/personal:doit NEU-742 --no-merge   # stop once the PR is open
/personal:doit NEU-742 --base release/1.4
```

The working rhythm is: `/personal:doit <ticket>` → let it finish → `/clear` (or `/compact`) →
`/personal:doit <next ticket>`. It checks that the ticket's `blockedBy` blockers are `Done`, then
invokes the three pipeline commands via the Skill tool, which loads each one **inline, in this
session** — no sub-agents, no `claude -p` — so
`shipit` and `mergeit` reuse the branch, base, spec, and diff `implementit` already resolved.

It keeps every gate the loop keeps: the mandatory pre-ship `/code-review` pass, CI as the merge gate,
`MERGE_BLOCKED` instead of a forced merge, and `/reviewit` staying manual. It gives up unattended
operation and wave discovery — you choose each ticket. `docs/adr/0007-doit-is-the-attended-single-ticket-pipeline.md`
records why both this and the loop exist.

| Compared on | `/doit` | `loop.py` |
|---|---|---|
| Attention | You watch and can interject | Walk away |
| Scope per invocation | One ticket | A wave (or a whole project with `--waves`) |
| Ticket selection | You name it | `loop-ready` label triage + blocker check |
| Where phases run | Inline, one warm context | One cold `claude -p` per step |
| Model/effort | Whatever the session is on | Per-step routing (Opus/Sonnet/Haiku) |
| Merging | On by default (`--no-merge` to stop at the PR) | Off by default (`--merge` to enable) |

## The autonomous loop

`plugins/personal/scripts/loop.py` is a headless orchestrator (Python 3, standard library only)
that drives the commands non-interactively via `claude -p`. By default it processes one wave of
`loop-ready`-labelled tickets whose blockers are all `Done`, driving each ticket all the way to a
merged PR before starting the next — so each new branch roots on an up-to-date base and downstream
conflicts shrink. Pass `--waves` to keep going across an entire project instead: after each wave's
merges, it re-discovers whatever just became unblocked and runs that as the next wave, repeating
until nothing is left, a wave makes no progress, or the safety cap is hit (see `--waves` below).
`/projectit` marks each work ticket `loop-ready` (and `repo:<name>`) at creation, so a project it
scaffolds is immediately loop-runnable with no `/planit` pass required — `/implementit` falls back
to the project-wide spec directly. Tickets created outside `/projectit` need the `loop-ready` label
(and matching `repo:<name>`) applied by hand, or can be passed explicitly via `--tickets`.

### Per-ticket state machine

For each ticket the loop runs:

```
implementit → shipit ──[--merge]──→ mergeit ─→ MERGED
     │           │                     │
     │           │                     └─ MERGE_BLOCKED → NEEDS_HUMAN
     │           └─[no --merge]────→ READY_FOR_REVIEW
     └─ no STATUS: IMPLEMENTED ────→ FAILED
```

- Code review happens **inside** `implementit`: it runs `/personal:code-review` before the PR is
  opened and applies its findings **by severity** (ADR 0006 — hard violations and real defects only). The loop does not run `/personal:reviewit` (ADR 0005), so there is no review ↔ address
  alternation and no round budget.
- A ticket is merged **only when `--merge` is set**; otherwise the loop stops once the PR is open,
  at `READY_FOR_REVIEW`, for a human/team to review and merge.
- A `MERGE_BLOCKED` result records the ticket's disposition as `NEEDS_HUMAN` with a reason and
  **continues to the next ticket**. The wave is never stopped by a single stalled ticket.
- Hard failures of a step (non-zero exit / timeout / missing sentinel) are recorded as `FAILED` and
  the loop moves on.

Re-run the loop as tickets merge to pick up the next newly-unblocked wave (tickets whose blockers
are now `Done`) — or pass `--waves` (with `--merge`) to have one run do that automatically until
the project (or `--tickets` list) is complete.

### Usage

Run it from inside the target app's repo (so file reads and git operations resolve there):

```bash
plugins/personal/scripts/loop.py [--project <name>] [--label loop-ready] \
                                 [--tickets ID ...] [--dry-run] [--check] \
                                 [--limit N] [--notify [backend]] [--detach] \
                                 [--merge] [--waves]
```

| Flag | Effect |
|---|---|
| `--project <name>` | Override the project; otherwise inferred from the repo's `linear_initiative:` CLAUDE.md hint. |
| `--label <name>` | Ready-marker label to triage on (default `loop-ready`). |
| `--tickets ID …` | Bypass triage with an explicit ticket list. Without `--waves`, blocker status is never checked — the given IDs are trusted and run as-is. |
| `--dry-run` | Run read-only triage and print the wave + the exact `claude -p` commands (including the merge/stop step) without executing. With `--waves`, only wave 1 is previewed (later waves depend on runtime state). |
| `--check` | Run only the feasibility guard (verifies `claude -p` + Linear/GitHub MCP are reachable). |
| `--limit N` | Cap the wave size (applies per wave when `--waves` is set). |
| `--notify [backend]` | Send a notification as each ticket finishes (with its final disposition) and once at the end of the run. Bare `--notify` posts a native **macOS** banner; `--notify pushover` sends via **Pushover** (requires `PUSHOVER_APP_TOKEN` and `PUSHOVER_USER_KEY` env vars). Off by default. Missing credentials or an unknown backend fail silently — the loop is never affected. |
| `--detach` | Background the run: re-launch detached, write stdout/stderr to a timestamped `<repo>/.claude/loop/run-*.log` (self-`.gitignore`d), print a `tail -f` watch command, and return immediately. |
| `--merge` | Run `mergeit` once the PR is open. **Off by default** — without it the loop stops at the `READY_FOR_REVIEW` disposition (PR opened, left for a human/team to review and merge). Use it on repos where auto-merge is wanted; omit it where PRs require team approval. |
| `--waves` | Iterate wave-by-wave — after each wave's merges, re-discover whatever just became unblocked (via label re-triage, or via a Linear blocker-check scoped to the `--tickets` list) and run it as the next wave. Repeats until a wave comes back empty (project/list **complete**, or **stalled** if anything remains **held**), a wave merges nothing at all (**stopped — no progress**, so a stuck ticket is never retried forever within the run), or a 50-wave safety cap is hit. **Requires `--merge`** — a later wave can only unblock once the prior wave's tickets are actually `Done`, which only happens on merge. |

**Credentials (`--notify pushover`):** `PUSHOVER_APP_TOKEN` and `PUSHOVER_USER_KEY` can come from the
environment or a `.env` file. At startup the loop loads the first file it finds — `$PUSHOVER_ENV_FILE`,
then `<repo-root>/.env`, then `~/.claude/.env` — but **real environment variables always win** (the
file only fills gaps). Copy `.env.example` to `.env` (git-ignored) and fill in your values, or just
`export` the vars in your shell.

**Run flow:** feasibility guard → Linear-MCP triage (returns the wave as JSON) → per-ticket state
machine (implement → ship → merge/stop) → a printed summary showing each ticket's **disposition**
(`MERGED` / `READY_FOR_REVIEW` / `NEEDS_HUMAN` / `FAILED`) and a **per-step usage/cost breakdown**,
plus the held list. `READY_FOR_REVIEW` means the PR was opened and `--merge` was not set — it is
ready for the human/team to review and merge.

### Models & effort per step

Cost levers are parameterized in `default_models()` / `default_efforts()` (defaults below, flagged
to retune from real usage data — not final):

| Step | Model | Effort |
|---|---|---|
| `implementit` | **Opus** | high |
| `shipit` | Sonnet | low |
| `mergeit` | Haiku | low |
| triage | Sonnet | medium |
| feasibility guard | Haiku | low |

`implementit` runs on **Opus at high effort**: it works from a spec rather than a pre-written plan,
and since ADR 0005 its internal `/code-review` pass is the loop's only code review — the whole
quality burden for a ticket sits there. Everything downstream is mechanical, so `shipit` runs on
Sonnet at low effort and `mergeit` on Haiku. The per-step `usage/cost` summary also reports a **cache
write** column alongside cache reads, so each cold-started step's cache cost is visible.

### Observability

The pipeline emits flushed, timestamped `[HH:MM:SS]` progress lines on entry to each step
(`implementit`, `shipit`, `mergeit`), plus wave start,
per-ticket start, and per-ticket disposition. With `--detach` those lines stream to the log file, so
`tail -f <logpath>` shows live progress.

### Safety

The agentic steps run under `--permission-mode bypassPermissions`. Safety comes from: the
`settings.json` deny-rules (which still apply); every change landing on a feature branch behind a
PR; the `/personal:code-review` pass `implementit` runs before that PR is opened; **CI passing** as the
merge gate; `--merge` being opt-in; and merge-blocks escalating to `NEEDS_HUMAN` rather than being
forced through.

`scripts/test_loop.py` covers the pure-Python parsing/orchestration logic (parsers, state-machine
transitions, model/effort routing, base threading, detach helpers, and summary rendering).

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

A repo can also declare hint keys in its `CLAUDE.md` so `/projectit` and the loop can resolve the
Linear target without searching:

- `linear_initiative: <name>` — the Linear initiative (project group) this repo belongs to.
- `linear_team: <name>` — the Linear team to create tickets under.
- `linear_repo: <name>` — overrides the auto-derived repo label (`repo:<name>`) that both the loop
  (for triage filtering) and `/projectit` (for labeling tickets it creates in this repo) resolve.
  Both otherwise derive `<name>` from `git remote get-url origin` (basename).
- `linear_repos: [<name>, <name>, …]` — for `/projectit`: the canonical repo names a project's
  tickets may target, so each ticket can carry the right `**Target repo:**` line at creation.

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
