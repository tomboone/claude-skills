# Scaffold a whole Linear project (milestones, stories, tickets) and pre-generate milestone specs + ticket plans.
# Usage: /personal:projectit [--dry-run] ["high-level project idea"]

## Conventions used by this command

- Resolve `DOCS_DIR` exactly as `/personal:planit` does (specs_dir override; else umbrella `<umbrella>/docs` or single-repo `<repo>/.claude/docs`).
- **Dry-run:** if `--dry-run` is passed, make NO `save_*`/`create_*` Linear calls. Instead print each Linear write you would make, and write any generated docs under `DOCS_DIR/superpowers/.dryrun/` rather than `specs/`/`plans/`. This dry-run rule is honored by every later phase — each phase's write step prints instead of executing when dry-run is active.
- **Never** set issue `status` — the GitHub↔Linear connector owns it.
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

## Phase 1 — Project description  ■ gate

Invoke `superpowers:brainstorming` framed on the idea + initiative context to produce a thorough
project description (purpose, scope, goals). **■ Gate:** user approves. **Hold the approved
description** for the Phase-3 creation batch — do not write to Linear yet.

## Phase 2 — Milestones  ■ gate

Propose milestones as a list of {name, one-paragraph goal, order}. **■ Gate:** user edits/approves.
**Hold the approved milestone list** for the Phase-3 creation batch — do not write to Linear yet.

## Phase 3 — User stories & work tickets  ■ gate

For each milestone, propose user stories and, under each, work tickets. Granularity rule:
one work ticket = one `/implementit` run = one PR; stories hold user-facing acceptance criteria,
tickets are the implementable slices. Note inter-ticket dependencies (B builds on A).

**■ Gate:** user reviews/edits the full breakdown. **This is the single gate after which all Linear
writes happen** — nothing was written in Phases 0–2.

On approval, create top-down in one batch (dry-run prints each call instead):
1. **Project:** if creating new, `save_project(name=<PROJECT_TO_CREATE>, addTeams=[<team>], addInitiatives=[<initiative>], description=<held Phase-1 description>)`; if reusing, `save_project(id=PROJECT, description=<held Phase-1 description>)`. Record `PROJECT`.
2. **Milestones:** for each held milestone, `save_milestone(project=PROJECT, name=<name>, description=<goal>)`.
3. **Stories:** `save_issue(title, team=TEAM, project=PROJECT, milestone=<name>, description=<story + acceptance criteria>, labels=["user-story"])`. Record each identifier.
4. **Tickets:** `save_issue(title, team=TEAM, project=PROJECT, milestone=<name>, parentId=<story-id>, description=<intent>)`.
5. **Dependencies:** for each "B builds on A", `save_issue(id=B, blockedBy=[A])`.

**Idempotency:** before creating, look up the project (by id/name), milestones (by name), and issues
(by title within PROJECT); update matches instead of duplicating. Safe to re-run.
