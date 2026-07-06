# Scaffold a Linear project: brainstorm it, break it into milestones, stories, and work tickets, and create them in Linear. Per-ticket specs/plans are authored later, just-in-time, with /personal:planit.
# Usage: /personal:projectit [--dry-run] ["high-level project idea"]

## Conventions used by this command

- **Dry-run:** if `--dry-run` is passed, make NO `save_*`/`create_*` Linear calls. Instead print each Linear write you would make. Every phase honors this — its write step prints instead of executing when dry-run is active.
- **Never** set issue `status` — the GitHub↔Linear connector owns it.
- **No labels.** This command applies no labels of any kind. Ticket selection is manual, and per-ticket specs/plans are authored later with `/personal:planit`.
- Create nothing in Linear until after the Phase 3 gate.

## Phase 0 — Resolve the Linear target  ■ gate

1. Determine the idea: use the quoted argument, else ask the user for a one-line project idea.
2. **Initiative:** read the repo's `CLAUDE.md` for `linear_initiative`. If present, use it. Else call
   `list_initiatives(query=<app/repo name>, includeProjects=true)` and propose the best name match.
3. **Team:** read `linear_team` from `CLAUDE.md`; else `list_teams`, propose the most likely team, and ask if ambiguous.
4. **Project:** from the initiative's returned projects, if one plausibly matches the idea, propose
   "reuse <project>"; otherwise propose "create new: <name>".
5. **■ Gate:** show the resolved initiative, team, and reuse/create decision; wait for confirmation.
6. On confirm: record the decision — if reusing, store `PROJECT=<existing-project-id>`; if creating,
   store `PROJECT_TO_CREATE=<name>`. **Do not call `save_project` here** — all Linear writes are deferred
   to the Phase-3 batch. Offer to write `linear_initiative`/`linear_team` back into the repo's
   `CLAUDE.md` if they were not already set.
7. **Target repos (multi-repo projects only):** if this project's tickets may span more than one repo,
   resolve the set of repo **names** — most authoritative first: (a) a `linear_repos:` list in
   `CLAUDE.md`; else (b) ask the user to name them. Record the set as `REPOS` (names only — no local
   paths and no docs-dir resolution or pinning). If the project targets a single repo, skip repo
   handling entirely and tickets carry no target-repo line.

## Phase 1 — Project description  ■ gate

Run a `/grilling` session, using `/domain-modeling` alongside it, framed on the idea + initiative
context to produce a thorough project description (purpose, scope, goals) — updating `CONTEXT.md`
and any ADRs inline as decisions crystallize. **■ Gate:** user approves.

Once approved, resolve `DOCS_DIR` for the repo `/personal:projectit` is being run in (per
`spec-and-plan-convention.md`), then write a **project-wide spec** to
`DOCS_DIR/specs/<project-slug>-project-spec.md` (`<project-slug>` = hyphenated project name;
create the folder if missing) capturing the full grilling session's outcome — not just the short
paragraph destined for Linear's project description below. This is what lets
`/personal:planit`'s sufficiency check pass immediately for every ticket in the project, without a
fresh per-ticket interview, when the project-shaping pass was thorough enough to cover it. Record
its path as `PROJECT_SPEC`.

**Hold the approved one-paragraph description** (for Linear's `project.description`) **and
`PROJECT_SPEC`'s path** for the Phase-3 creation batch — do not write to Linear yet.

## Phase 2 — Milestones + shared contracts  ■ gate

Propose milestones as a list of {name, one-paragraph goal, order}. For each milestone, also draft the
**cross-cutting decisions siblings must agree on before either is built** — the API shape a backend
ticket exposes and a frontend ticket consumes, a shared data model, naming conventions. Fold these
into the milestone's description as a short **Shared contracts** section beneath the goal. **■ Gate:**
user edits/approves. **Hold the approved milestone list (goals + contracts)** for the Phase-3 creation
batch — do not write to Linear yet.

## Phase 3 — User stories & work tickets  ■ gate

For each milestone, propose user stories and, under each, work tickets. Granularity rule:
one work ticket = one `/implementit` run = one PR; stories hold user-facing acceptance criteria,
tickets are the implementable slices. Note inter-ticket `blockedBy` dependencies (B builds on A).

**Target repo (multi-repo projects only):** assign each work ticket exactly one repo name from
`REPOS` and record it as a plain `**Target repo:** <name>` line in the ticket description —
informational, so you know where to run `/personal:planit`. **Never silently guess** — ask when a
ticket's repo is ambiguous. Show each ticket's assigned repo in the breakdown so the user can edit
it at the gate. Stories get no repo assignment. Single-repo projects: omit target-repo lines entirely.

**■ Gate:** user reviews/edits the full breakdown. **This is the single gate after which all Linear
writes happen** — nothing was written in Phases 0–2.

On approval, create top-down in one batch (dry-run prints each call instead):
1. **Project:** append a `**Project spec:** <PROJECT_SPEC path>` line to the held Phase-1 description. If creating new, `save_project(name=<PROJECT_TO_CREATE>, addTeams=[<team>], addInitiatives=[<initiative>], description=<description + Project spec line>)`; if reusing, `save_project(id=PROJECT, description=<description + Project spec line>)`. Record `PROJECT`.
2. **Milestones:** for each held milestone, `save_milestone(project=PROJECT, name=<name>, description=<goal + Shared contracts section>)`.
3. **Stories:** `save_issue(title, team=TEAM, project=PROJECT, milestone=<name>, description=<story + acceptance criteria>)`. Record each identifier. **No label.**
4. **Tickets:** `save_issue(title, team=TEAM, project=PROJECT, milestone=<name>, parentId=<story-id>, description=<intent; for multi-repo projects prepend a "**Target repo:** <name>" line>)`.
5. **Dependencies:** for each "B builds on A", `save_issue(id=B, blockedBy=[A])`.

**Idempotency:** before creating, look up the project (by id/name), milestones (by name), and issues
(by title within PROJECT); update matches instead of duplicating. Safe to re-run.

## Done — summary

Print a summary block:

```
Project: <Linear project URL>
Milestones:   <count>
User stories: <count>
Work tickets: <count>

Next: run /personal:planit {TICKET} in the ticket's repo to plan it just-in-time,
then /personal:implementit {TICKET}.
```
