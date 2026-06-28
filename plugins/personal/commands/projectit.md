# Scaffold a whole Linear project (milestones, stories, tickets) and pre-generate milestone specs + ticket plans.
# Usage: /personal:projectit [--dry-run] ["high-level project idea"]

## Conventions used by this command

- **Per-repo docs.** Each ticket's docs live in **its assigned repo**. Define `docs_dir_for(repo)`:
  resolve `DOCS_DIR` from *that repo's* root + its `CLAUDE.md` exactly as `/personal:planit` does
  (`specs_dir` override → umbrella `<umbrella>/docs` → single-repo `<repo>/.claude/docs`). Cache per
  repo. A single-repo project resolves once (unchanged behavior). There is **no** project- or
  milestone-level shared docs location.
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
7. **Candidate repos (`REPOS`):** resolve the set of repos this project's tickets may target,
   most authoritative first: (a) a `linear_repos:` list in `CLAUDE.md`; else (b) local sibling
   git repos discovered by scanning the umbrella folder **and** the surrounding workspace root
   (a bounded walk-up — stop at the workspace root, do not scan the whole filesystem), taking
   each repo's canonical name from `git remote get-url origin` (basename, strip `.git`); else
   (c) query GitHub for likely repos (org repos, prioritizing names matching the
   initiative/project) and propose them. Record the resolved set as `REPOS`. If it resolves to a
   single repo, default all tickets to that repo's canonical name. If all
   three tiers leave `REPOS` empty or unresolved, ask the user directly to
   name the target repo(s) before proceeding to Phase 3.
   For each repo in `REPOS`, also record its **local filesystem path** (the sibling-scan in tier (b)
   yields these directly; for repos resolved via tier (a)/(c) without a known path, locate the repo
   under the workspace or ask the user). This path is required to read the repo's `CLAUDE.md` and to
   write its docs. If an assigned repo is **not checked out locally**, note it and **skip generating
   that repo's docs** in Phase 4 (the ticket is still created and labeled in Linear; its spec/plan can
   be authored later with `/personal:planit` run inside that repo).

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

**Repo assignment:** assign each work ticket exactly one repo from `REPOS` (its `repo:<name>`).
**Never silently guess** — whenever a ticket's repo is ambiguous (multiple plausible candidates,
or `REPOS` is thin/empty), ask the user which repo to label. Show each ticket's assigned repo in
the breakdown so the user can edit it at the gate. Stories (parent issues) get no repo assignment.

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

## Phase 4 — Bulk doc generation (subagents)

Run on Opus. Batch subagents (≤5 at a time) per `superpowers:dispatching-parallel-agents`. Each
ticket gets a **self-contained `spec + plan` written into its own repo** (`docs_dir_for(ticket.repo)`)
— planit's output shape. There is **no milestone-spec file**.

### Cross-ticket design pass (in context, not a file)
Before dispatching, draft each milestone's cross-cutting decisions and shared contracts (from the
Phase-1 description + the Phase-3 breakdown) and hold them as notes. These notes are **not written to
disk** — they are passed to the relevant ticket subagents so their self-contained specs make the
**same** decisions (especially a cross-stack contract: the BE ticket and the FE ticket that consumes
it must agree). Each ticket spec **inlines** the decisions it needs; nothing is cross-linked.

### Per-ticket subagents (dependency order)
Dispatch one subagent per work ticket, in dependency order so a ticket's `blockedBy` prerequisites'
specs already exist and can be passed as context. Each subagent receives: the project description; the
milestone shared-decision notes; the ticket's story + intent; its `blockedBy` prerequisites' specs;
and **its assigned repo's path** (it explores that repo's real code/conventions). It writes BOTH, under
`DOCS_DIR = docs_dir_for(ticket.repo)`:

- **Spec** → `DOCS_DIR/superpowers/specs/<TICKET-ID>-<slug>.md` — self-contained: purpose/scope;
  architecture & approach (components, data models, interfaces it introduces); the cross-cutting
  decisions it depends on (inlined); acceptance; explicit out-of-scope.
- **Plan** → `DOCS_DIR/superpowers/plans/<TICKET-ID>-<slug>.md` — a RESILIENT plan: what to build,
  acceptance criteria, which part of the design it realizes, testing intent; deliberately light on
  exact file/function signatures (filled in by `/implementit` against real code). It MUST start with:

      **Spec:** ../specs/<TICKET-ID>-<slug>.md
      **Depends on:** <TICKET-ID, …>   (omit if no blockers)

  The `../specs/<TICKET-ID>-<slug>.md` link is **same-repo** (both files under the ticket's `DOCS_DIR`),
  so it always resolves — there is no cross-repo reference.

Skip any ticket whose repo isn't checked out locally (per Phase 0 step 7); list it as skipped.
Each subagent returns both paths + a one-line summary. (Dry-run: write under
`docs_dir_for(ticket.repo)/superpowers/.dryrun/{specs,plans}/` instead of `specs/`/`plans/`.)

### ■ Bulk review gate
Present a table: ticket → repo, spec path, plan path (grouped by story/milestone), each with its
one-line summary. The user reviews on disk. For any doc that is off, re-dispatch just that one
subagent with the user's feedback appended. Proceed to Phase 5 only on approval.

## Phase 5 — Link & mark ready

### Step 1 — Ensure labels exist

Call `list_issue_labels` for the team. Check for the labels `user-story` and `loop-ready`. For each
that is missing, call `create_issue_label` with a distinct color per label: `user-story` → `color="#6E56CF"`, `loop-ready` → `color="#30A46C"`. (Phase 3 applies `user-story` to stories; it is bootstrapped here too so a re-run against an existing project does not fail.)
Also, for each repo in `REPOS`, ensure a `repo:<name>` label exists; create any missing one with
`create_issue_label` using a distinct color (e.g. `color="#0091FF"`).
(Dry-run: print each `create_issue_label` call instead of executing.)

### Step 2 — Update work-ticket descriptions and apply `loop-ready`

For each work ticket (leaf-level issue, not stories), with `DOCS_DIR = docs_dir_for(ticket.repo)`:

- **Relative plan path:** `DOCS_DIR/superpowers/plans/<TICKET-ID>-<slug>.md` relative to `DOCS_DIR`
  (e.g. `superpowers/plans/PRD-42-add-widget.md`).
- **Relative spec path:** `superpowers/specs/<TICKET-ID>-<slug>.md`.
- **GitHub plan URL (best-effort):** if the ticket's repo `DOCS_DIR` is committed + pushed, construct
  `<that-repo-remote-url>/blob/<default-branch>/<DOCS_DIR-relative-plan-path>`; else skip the attachment.

Call `save_issue(id=<ticket-id>, description=<updated>, labels=["loop-ready", "repo:<assigned-repo>"])` where the updated
description prepends the following header block to the existing ticket description:

```
**Plan:** <relative plan path>
**Spec:** <relative spec path>
```

If the plan URL is available (committed and pushed), include `links=[{url: <github-plan-url>, title: "Implementation plan"}]` in the same `save_issue` call (best-effort — omit the `links` param if the file is not yet in the remote).

**Do not** set `status` on any issue — the GitHub↔Linear connector owns status transitions.

(Dry-run: print each `save_issue` call instead of executing.)

### Step 3 — Final summary

Print a summary block:

```
Project: <Linear project URL>
Milestones:   <count>
User stories: <count>
Work tickets: <count>  (<loop-ready count> marked loop-ready)

Next step: run /implementit on any loop-ready ticket to begin implementation.
```

The loop selects work tickets by the `loop-ready` label **scoped to the repo it runs in** (the
`repo:<name>` label) and reads each ticket's plan from **that repo's** docs by ticket ID. The Linear
`links` attachment from Step 2 is a human-convenience reference, not load-bearing for the loop.
