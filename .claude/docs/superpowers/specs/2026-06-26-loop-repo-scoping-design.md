# Loop Repo Scoping — Per-Repo Ticket Selection (Design Spec)

- **Date:** 2026-06-26
- **Status:** Approved design (brainstorming output)
- **Repo:** `claude-skills` (the `personal` plugin)
- **Linear ticket:** none yet (exploratory personal work)

## Summary

The autonomous loop (`plugins/personal/scripts/loop.py`) is invoked from a repo's root and
processes Linear work tickets through `/implementit → /shipit → (/reviewit ↔ /addressit)* →
/mergeit`. Today it scopes to a single Linear **project** and the `loop-ready` label. But one
Linear project routinely spans **multiple repos** (e.g. a backend and a frontend), and
`/projectit` puts `loop-ready` on *every* leaf ticket regardless of repo. So running the loop
in the backend repo would also pull frontend tickets it cannot implement.

This spec adds **per-repo scoping**: each work ticket carries a `repo:<name>` label whose value
is the repo's **canonical name derived from its git remote**, and the loop filters triage on
both `loop-ready` **and** the `repo:<name>` for the repo it is running in. The loop derives its
own repo identity the same way `/projectit` derives it when applying the label, so the two
sides always agree without hardcoding. A second, smaller refinement hardens triage against ever
selecting a user story / parent issue.

Net effect: run the loop in any repo root of a multi-repo project and it works only that repo's
tickets, for the whole project.

## Context & relationship to existing components

- **`/projectit`** (spec: `2026-06-24-projectit-planning-flow-design.md`) is the producer: it
  scaffolds a Linear project's milestones, stories, and work tickets, generates resilient
  plans, and applies `loop-ready` to leaf tickets. It is currently **single-repo**: it reads one
  repo's `CLAUDE.md` and writes plans to one `DOCS_DIR`.
- **`loop.py`** is the consumer: `resolve_project()` resolves the Linear project (from `--project`
  or `linear_initiative:` in `CLAUDE.md`); `run_triage()` runs a `claude -p` call against the
  Linear MCP using `TRIAGE_PROMPT` to find ready tickets; `main()` runs each ticket through the
  pipeline.

This spec changes both halves so the producer stamps a repo label and the consumer filters on it.

## Key decisions (from brainstorming)

1. **Per-repo label, not per-project/team split.** One Linear project still spans all repos;
   scoping is by a `repo:<name>` label rather than by carving the project into one-per-repo.
2. **Label value is the canonical repo name from the git remote** (e.g. `report-exporters`),
   never a hardcoded `backend`/`frontend` shortcut — so it generalizes to N repos with arbitrary
   names.
3. **One shared canonical-name derivation** used by both the loop (to learn its own identity) and
   `/projectit` (to stamp the label). Neither side hardcodes; both ask git/GitHub what the repo
   is called, so the names are guaranteed to match.
4. **Loop identity is auto-derived, with overrides.** Precedence: `--repo` flag → `linear_repo:`
   in `CLAUDE.md` → `git remote get-url origin` basename. No silent unscoped runs.
5. **Label format `repo:<name>`** (namespaced prefix), name = repo basename (not `owner/repo`).
6. **Harden triage against parent issues** — exclude any issue with sub-issues or the
   `user-story` label. Belt-and-suspenders on top of `/projectit` only labeling leaf tickets.
7. **`/projectit` repo discovery degrades gracefully**, ending in asking the user when ambiguous:
   explicit `linear_repos:` list → local sibling scan → GitHub candidate proposal → ask.
8. **Plan-doc generation/location is unchanged** — for an umbrella project `DOCS_DIR` resolves to
   the same `<umbrella>/docs` from any sibling repo, so a plan written once is found by
   `/implementit` regardless of which repo the loop runs in. No per-repo plan dirs.

## Part 1 — Canonical repo name (one shared derivation)

A single helper in `loop.py`, importable by `/projectit`'s logic, resolves the current repo's
label:

```
resolve_repo_label(args, read_claude_md=...) -> "repo:<name>"
  precedence:
    1. --repo <name>                  (explicit override)
    2. linear_repo: in CLAUDE.md      (override for odd remotes / no remote)
    3. git remote get-url origin → normalize → basename
  if none resolve: SystemExit (do not run unscoped)
```

**Normalization** accepts both remote URL forms and yields the bare repo name:

- `git@github.com:org/report-exporters.git` → `report-exporters`
- `https://github.com/org/report-exporters.git` → `report-exporters`

Rule: take the path component after the host, strip a trailing `.git`, take the last
path segment. The returned label is `repo:<name>`.

**Defaults (locked in brainstorming):**

- Label format is the namespaced `repo:<name>` (greppable, won't collide with feature labels).
- Name is the repo basename (`report-exporters`), unique within a single Linear project. If
  cross-org name clashes ever arise, switch the derivation to `owner/repo` in this one helper —
  both sides update together because they share it.

## Part 2 — Triage filter (loop)

`TRIAGE_PROMPT` is a natural-language prompt to a `claude -p` Linear-MCP call. It gains two
refinements; the returned JSON contract (`project`/`wave`/`held`) is unchanged.

1. **Repo scoping.** A ticket qualifies only if it carries **both** `loop-ready` **and** the
   resolved `repo:<name>` label, in addition to the existing rules (every `blockedBy` blocker is
   Done; the ticket is still un-started — Todo/Backlog, not In Progress/In Review/Done).
2. **Parent/story guard.** Explicitly exclude any issue that has sub-issues/children or carries
   the `user-story` label. `/projectit` already only labels leaf tickets `loop-ready`; this makes
   the loop robust even if a parent is mislabeled by hand.

**Plumbing:**

- `run_triage(project, label, runner)` → `run_triage(project, label, repo_label, runner)`.
- `main()` resolves `repo_label` via Part 1 and threads it through. `--tickets` (explicit ticket
  list) bypasses triage today and continues to do so — explicit IDs are taken as the user's
  intent and are not repo-filtered.
- `--dry-run` prints the resolved repo filter (e.g. `repo:report-exporters`) alongside the
  pipeline so scoping is confirmable before a real run.
- **`held` semantics are preserved**: a ticket filtered out for being the wrong repo simply does
  not appear (it is not reported as held). `held` continues to mean "right repo, blocked by an
  unfinished dependency."

## Part 3 — `/projectit` applies the label at creation

`/projectit` becomes multi-repo aware so every leaf ticket is born with the correct
`repo:<name>` label, derived the same way the loop derives it.

### 3a — Resolve each ticket's repo (layered best-effort, then confirm)

Build the candidate repo set from these sources, most authoritative first:

1. **`linear_repos:` in `CLAUDE.md`** — an explicit allow-list of canonical repo names;
   authoritative when present. (New convention, sibling to `linear_initiative:` / `linear_team:`
   / `linear_repo:`.)
2. **Local sibling git repos** — scan not just the immediate umbrella folder but the broader
   neighborhood (the umbrella *and* the surrounding workspace root), walking up a **bounded**
   number of levels (not the whole filesystem). Run the Part-1 derivation in each discovered git
   repo to get its canonical name.
3. **GitHub** — if (1) and (2) come up thin, query GitHub for likely candidates (org repos,
   prioritizing names that match the initiative/project) and propose them. A GitHub repo's name
   equals its remote basename, so proposed names are guaranteed to match what the loop later
   derives in the cloned repo.

**Resolution rule:** assign each leaf ticket a repo from the candidate set, but **never silently
guess**. Whenever a ticket's repo is ambiguous (multiple plausible candidates, or a thin/empty
set), **ask the user** which repo to label. Unambiguous assignments still surface at the Phase-3
gate for final review/edit. The flow degrades: explicit list → local scan → GitHub proposal →
ask; the user is the backstop, not the first resort.

Stories (parent issues) get no repo assignment — they are not implemented directly.

### 3b — Assign in Phase 3

In the work-ticket breakdown (Phase 3), each leaf ticket carries its resolved `repo:` assignment,
shown in the Phase-3 review gate so assignments can be edited before any Linear write.

### 3c — Ensure labels exist (Phase 5 Step 1)

For each repo in use, ensure a `repo:<name>` label exists (`create_issue_label` with a distinct
color if missing) — same bootstrap pattern as the existing `loop-ready` / `user-story` labels, so
a re-run against an existing project does not fail.

### 3d — Apply the label (Phase 5 Step 2)

Each leaf ticket's `save_issue(...)` adds its `repo:<name>` label alongside `loop-ready`.

### What does NOT change

Plan-doc generation and location. For an umbrella project, `DOCS_DIR` resolves to
`<umbrella>/docs` regardless of which sibling repo you run from, so a plan written once is found
by `/implementit` whether the loop runs in the backend or frontend repo. No per-repo plan dirs
are introduced.

## Data flow (end to end)

```
/projectit (in/around the umbrella)
  └─ resolve candidate repos: linear_repos → sibling scan → GitHub → ask
  └─ assign each leaf ticket a repo (reviewed at Phase-3 gate)
  └─ Phase 5: ensure repo:<name> labels exist; stamp each leaf ticket
                 labels = [loop-ready, repo:<name>]

loop.py (in backend repo root)
  └─ resolve_repo_label(): --repo → linear_repo: → git remote  => "repo:backend"
  └─ run_triage(project, loop-ready, repo:backend):
        Linear MCP → tickets with BOTH labels, blockers Done, un-started,
                     NOT a parent/user-story
  └─ wave = backend tickets only → pipeline per ticket
```

## Testing

`loop.py` has a unit-test suite (`test_loop.py`); `/projectit` is command/prompt tooling.

- **Unit (loop):**
  - `resolve_repo_label` normalization — SSH and HTTPS remotes both → bare basename; trailing
    `.git` stripped; override precedence (`--repo` > `linear_repo:` > git remote); error when
    nothing resolves.
  - `TRIAGE_PROMPT` includes the `repo:<name>` filter and the parent/user-story exclusion clause;
    triage JSON parsing (`parse_triage_result`) is unchanged.
  - `run_triage` threads `repo_label` through; `--dry-run` surfaces the repo filter.
- **`/projectit`:** dry-run produces the proposed breakdown with per-ticket repo assignments
  *without* writing to Linear; verify the layered discovery resolves/asks as specified.
- **End-to-end (contract test):** in a two-repo sandbox project, run the loop in each repo root
  and confirm each wave contains only that repo's tickets and no parent issues.

## Out of scope

- Splitting a Linear project into one-per-repo projects/teams (explicitly rejected).
- Per-repo plan directories (unnecessary; umbrella `DOCS_DIR` already shared).
- Inferring a ticket's repo from linked PRs/branches (no PR exists at triage time for an
  un-started ticket).

## Open items / deferred

- The `linear_repo:` (single) and `linear_repos:` (list) `CLAUDE.md` conventions should be
  documented alongside the existing `linear_initiative:` / `linear_team:` / `specs_dir` hints.
- Bound for the sibling-scan walk-up (how many parent levels) — pick a sane default at
  implementation (e.g. stop at the workspace root / first non-project ancestor).
- Whether `owner/repo` is ever needed instead of the basename — deferred until a real name
  clash appears; isolated to the single derivation helper.
