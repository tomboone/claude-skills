# `/projectit` Planning Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/projectit` slash command to the `personal` plugin that scaffolds an entire Linear project (description → milestones → user stories → work tickets) and pre-generates a milestone spec per milestone and a resilient implementation plan per work ticket, so the future implementation loop can run `/implementit` on Sonnet without per-ticket `/planit`.

**Architecture:** `/projectit` is a single self-contained prose command file matching the existing command style in `plugins/personal/commands/`. It runs six gated phases; the structural top is an interactive dialogue, and the bulk doc generation dispatches batched in-session subagents. Two supporting edits — the spec/plan convention doc and `/implementit` — complete the contract. There is no application code: deliverables are markdown command/convention files, validated by dry-run and a sandbox end-to-end run.

**Tech Stack:** Claude Code plugin (markdown slash commands), Linear MCP (`claude_ai_Linear`), superpowers skills (`brainstorming`, `dispatching-parallel-agents`), git. No programming language, test framework, or build step.

## Global Constraints

These apply to every task; values are copied verbatim from the spec.

- Command file: `plugins/personal/commands/projectit.md`; invoked as `/personal:projectit`.
- Existing command style (match exactly): file begins with two comment lines — `# <one-line description>` then `# Usage: /personal:<cmd> {ARGS}` — followed by `## Step N — …` / `## Phase N — …` prose sections. See `planit.md` and `implementit.md`.
- **Never set Linear issue `status`** — the GitHub↔Linear connector owns status transitions.
- **No Linear writes before the Phase-3 gate** — Phases 0–2 only propose/hold; the single Linear-creation batch runs after the Phase-3 gate, in order: project (+description) → milestones → stories → tickets → blockedBy.
- Labels (exact strings): `user-story`, `loop-ready`. Ensure they exist via `create_issue_label` before applying.
- Ticket plan filename: `plans/<TICKET-ID>-<slug>.md`. Milestone spec filename: `specs/<project-slug>-m<NN>-<milestone-slug>.md` (`NN` zero-padded, preserves order).
- **Contract tokens inside each ticket plan file** (used by `/implementit`, must match exactly):
  - `**Milestone spec:** <relative-path-from-plan-file-to-its-milestone-spec>`
  - `**Depends on:** <TICKET-ID>[, <TICKET-ID>…]` (mirrors Linear `blockedBy`; omit the line if none)
- Planning subagents run on **Opus**.
- `DOCS_DIR` resolves via the existing convention (umbrella → `<umbrella>/docs`; single-repo → `<repo>/.claude/docs`; `specs_dir` override).
- Dry-run: the command accepts a `--dry-run` argument; in dry-run it performs **no** `save_*`/`create_*` Linear calls and writes generated docs under `DOCS_DIR/superpowers/.dryrun/` instead of the real `specs/` `plans/` dirs, printing every Linear write it *would* have made.
- Commits: Conventional Commit subject, no Linear parenthetical (no ticket maps to this work), **no footer in commit messages**, no co-author.

---

## File Structure

**Create:**
- `plugins/personal/commands/projectit.md` — the `/projectit` command (built incrementally across Tasks 3–6).

**Modify:**
- `plugins/personal/spec-and-plan-convention.md` — add the `linear_initiative`/`linear_team` CLAUDE.md hint convention and the milestone-spec filename pattern (Task 1).
- `plugins/personal/commands/implementit.md` — load the milestone spec a plan references (Task 2).

No application code, so no test files. Validation is dry-run + a sandbox end-to-end run (Task 7).

---

## Task 1: Spec/plan convention — Linear hints + milestone naming

**Files:**
- Modify: `plugins/personal/spec-and-plan-convention.md`

**Interfaces:**
- Produces: the `linear_initiative` / `linear_team` CLAUDE.md hint convention (consumed by Task 3, Phase 0) and the milestone-spec filename pattern `specs/<project-slug>-m<NN>-<milestone-slug>.md` (consumed by Task 5).

- [ ] **Step 1: Add the Linear hint convention**

After the "Resolving the docs directory (`DOCS_DIR`)" section, add a new section:

```markdown
## Linear target hints (for `/projectit`)

A repo may declare its Linear home so `/projectit` can resolve it without searching:

- `linear_initiative: <name-or-id>` — the initiative this repo's app belongs to (initiative ≈ one app).
- `linear_team: <name-or-key>` — the team new issues/projects are created in.

Set these in the repo's `CLAUDE.md` (sibling to `specs_dir`). If absent, `/projectit` searches
initiatives by name and asks for confirmation, then offers to write the confirmed values back.
```

- [ ] **Step 2: Add the milestone-spec filename pattern**

In the "Filenames" section, after the ticket-ID filename rule, add:

```markdown
- **Milestone specs** are not ticket-scoped. Name them `specs/<project-slug>-m<NN>-<milestone-slug>.md`
  (`<project-slug>` = hyphenated Linear project name; `<NN>` = zero-padded milestone order).
  Ticket plans reference their milestone spec by relative path (see `/projectit`).
```

- [ ] **Step 3: Validate**

Re-read the file. Confirm: (a) the new sections don't contradict the existing `specs_dir` / ticket-ID rules; (b) the milestone pattern and the `**Milestone spec:**` contract token (Global Constraints) are consistent; (c) no placeholder text remains.

- [ ] **Step 4: Commit**

```bash
git add plugins/personal/spec-and-plan-convention.md
git commit -m "docs: add Linear target hints and milestone-spec naming to convention"
```

---

## Task 2: `/implementit` loads the referenced milestone spec

**Files:**
- Modify: `plugins/personal/commands/implementit.md` (Step 2 area, lines 13–20)

**Interfaces:**
- Consumes: the `**Milestone spec:** <relative-path>` token written into ticket plans (Global Constraints / Task 5).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Add a milestone-spec load step**

Immediately after the existing Step 2 ("Locate the plan file"), insert a new step and renumber the following steps (current Step 3 "Create the work branch" becomes Step 4, etc.):

```markdown
## Step 3 — Load the milestone spec (if the plan references one)

Read the chosen plan file. If it contains a line beginning `**Milestone spec:** `, resolve that
relative path (from the plan file's location) and read the referenced milestone spec. Pass **both**
the plan and the milestone spec to the implementation in Step 5 — the plan is the per-ticket slice,
the milestone spec is the shared design context.

If the plan has no such line (e.g. a `/planit`-authored plan), proceed with the plan alone — this
step is a no-op. Backwards-compatible.
```

- [ ] **Step 2: Renumber subsequent steps**

Update the headings for the remaining steps (branch creation, Superpowers hand-off, final hand-off) so numbering is contiguous, and update any in-text references to step numbers.

- [ ] **Step 3: Validate**

Re-read the file. Confirm: (a) a plan with no `**Milestone spec:**` line still flows (no-op path stated); (b) the token string matches Global Constraints exactly; (c) step numbers are contiguous and no cross-references are stale.

- [ ] **Step 4: Commit**

```bash
git add plugins/personal/commands/implementit.md
git commit -m "feat: load referenced milestone spec in implementit"
```

---

## Task 3: `/projectit` scaffold + Phase 0 (resolve Linear target) + dry-run

**Files:**
- Create: `plugins/personal/commands/projectit.md`

**Interfaces:**
- Consumes: the `linear_initiative`/`linear_team` hint convention (Task 1); Linear MCP `list_initiatives`, `list_teams`, `save_project`.
- Produces: a confirmed `INITIATIVE`, `TEAM`, and `PROJECT` (id or to-create), plus the resolved `DOCS_DIR` and a `DRY_RUN` flag — consumed by Tasks 4–6.

- [ ] **Step 1: Write the command header and dry-run preamble**

```markdown
# Scaffold a whole Linear project (milestones, stories, tickets) and pre-generate milestone specs + ticket plans.
# Usage: /personal:projectit [--dry-run] ["high-level project idea"]

## Conventions used by this command

- Resolve `DOCS_DIR` exactly as `/personal:planit` does (specs_dir override; else umbrella `<umbrella>/docs` or single-repo `<repo>/.claude/docs`).
- **Dry-run:** if `--dry-run` is passed, make NO `save_*`/`create_*` Linear calls. Instead print each Linear write you would make, and write any generated docs under `DOCS_DIR/superpowers/.dryrun/` rather than `specs/`/`plans/`.
- **Never** set issue `status` — the GitHub↔Linear connector owns it.
- Create nothing in Linear until after the Phase 3 gate.
```

- [ ] **Step 2: Write Phase 0 (resolve the Linear target)**

```markdown
## Phase 0 — Resolve the Linear target  ■ gate

1. Determine the idea: use the quoted argument, else ask the user for a one-line project idea.
2. **Initiative:** read the repo's `CLAUDE.md` for `linear_initiative`. If present, use it. Else call
   `list_initiatives(query=<app/repo name>, includeProjects=true)` and propose the best name match.
3. **Team:** read `linear_team` from `CLAUDE.md`; else `list_teams` and propose/ask.
4. **Project:** from the initiative's returned projects, if one plausibly matches the idea, propose
   "reuse <project>"; otherwise propose "create new: <name>".
5. **■ Gate:** show the resolved initiative, team, and reuse/create decision; wait for confirmation.
6. On confirm: **record the decision only — do not create the project yet.** For reuse, keep the existing project's id as `PROJECT`; for create, hold the new project NAME as `PROJECT_TO_CREATE`. All Linear creation is deferred to the single post-gate batch in Phase 3. Offer to write `linear_initiative`/`linear_team` back into the repo's `CLAUDE.md` if they were not already set (a local file write, allowed here).
```

- [ ] **Step 3: Validate via dry-run**

In a throwaway/sandbox repo (or with a `linear_initiative` hint set), run `/personal:projectit --dry-run "test idea"`. Confirm it: resolves an initiative + team, proposes reuse/create, stops at the gate, and on confirm records the decision **without any Linear write** (creation is deferred to Phase 3).

- [ ] **Step 4: Commit**

```bash
git add plugins/personal/commands/projectit.md
git commit -m "feat: add projectit command scaffold and Linear target resolution"
```

---

## Task 4: `/projectit` Phases 1–3 (description, milestones, stories + tickets)

**Files:**
- Modify: `plugins/personal/commands/projectit.md`

**Interfaces:**
- Consumes: the Phase-0 decision (`PROJECT` id for reuse, or `PROJECT_TO_CREATE` name), `TEAM`, `INITIATIVE`, `DRY_RUN` (Task 3); Linear MCP `save_project`, `save_milestone`, `save_issue`; `superpowers:brainstorming`.
- Produces: the full Linear hierarchy, created in ONE batch after the Phase-3 gate — project(+description), milestones, user-story issues (e.g. `PROJ-101`), work-ticket sub-issues with `blockedBy` edges — consumed by Tasks 5–6.

> **Note (write-timing model):** Phases 0–2 only propose/hold; nothing is written to Linear until the single post-Phase-3-gate batch. This task must also **revise the Phase 0 section authored in Task 3** so its step 6 records the reuse/create decision instead of calling `save_project`.

- [ ] **Step 1: Write Phase 1 (project description)**

```markdown
## Phase 1 — Project description  ■ gate

Invoke `superpowers:brainstorming` framed on the idea + initiative context to produce a thorough
project description (purpose, scope, goals). **■ Gate:** user approves. **Hold the approved
description** for the Phase-3 creation batch — do not write to Linear yet.
```

- [ ] **Step 2: Write Phase 2 (milestones)**

```markdown
## Phase 2 — Milestones  ■ gate

Propose milestones as a list of {name, one-paragraph goal, order}. **■ Gate:** user edits/approves.
**Hold the approved milestone list** for the Phase-3 creation batch — do not write to Linear yet.
```

- [ ] **Step 3: Write Phase 3 (stories + tickets + dependencies)**

```markdown
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
```

- [ ] **Step 4: Validate via dry-run**

Run `/personal:projectit --dry-run "test idea"` through to end of Phase 3. Confirm: nothing is printed as written during Phases 0–2; after the Phase-3 gate it prints a coherent create-order (project → milestones → stories → tickets → blockedBy), sets `parentId` on tickets, emits `blockedBy` edges, applies `user-story` labels, and never prints a `status` write.

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/commands/projectit.md
git commit -m "feat: add projectit structural phases (description, milestones, stories, tickets)"
```

---

## Task 5: `/projectit` Phase 4 (bulk doc generation via subagents)

**Files:**
- Modify: `plugins/personal/commands/projectit.md`

**Interfaces:**
- Consumes: the Linear hierarchy (Task 4); `DOCS_DIR`; `superpowers:dispatching-parallel-agents`.
- Produces: a milestone spec per milestone at `specs/<project-slug>-m<NN>-<slug>.md` and a resilient plan per ticket at `plans/<TICKET-ID>-<slug>.md`, each plan carrying the `**Milestone spec:**` and optional `**Depends on:**` tokens — consumed by Task 6 (links) and, downstream, by `/implementit` (Task 2).

- [ ] **Step 1: Write Phase 4 round 1 (milestone specs)**

```markdown
## Phase 4 — Bulk doc generation (subagents)

Run on Opus. Resolve `DOCS_DIR`. Two ordered rounds; batch subagents (≤5 at a time) per
`superpowers:dispatching-parallel-agents`.

### Round 1 — milestone specs (one subagent per milestone)
Each subagent receives: the project description, the milestone goal, its stories+tickets, and the
repo path (it explores actual code/conventions). It writes `specs/<project-slug>-m<NN>-<slug>.md`
containing: purpose/scope of the phase; architecture & approach (components, data models, interfaces
it introduces); cross-cutting decisions & constraints; milestone-level acceptance; explicit
out-of-scope. It returns the path + a one-line summary. (Dry-run: write under `.dryrun/specs/`.)
```

- [ ] **Step 2: Write Phase 4 round 2 (ticket plans)**

```markdown
### Round 2 — ticket plans (one subagent per work ticket, after Round 1)
Each subagent receives: the ticket's milestone spec (now on disk), its story context, the ticket
intent, the docs of its `blockedBy` prerequisites, and the repo path. It writes
`plans/<TICKET-ID>-<slug>.md` — a RESILIENT plan: what to build, acceptance criteria, which part of
the milestone design it realizes, testing intent. Deliberately light on exact file/function
signatures (those are filled in by `/implementit` against real code). It MUST start the file with:

    **Milestone spec:** <relative path from this plan to its milestone spec>
    **Depends on:** <TICKET-ID, …>   (omit if no blockers)

(Dry-run: write under `.dryrun/plans/`.)
```

- [ ] **Step 3: Write the bulk-review gate**

```markdown
### ■ Bulk review gate
Present a table: milestone → spec path; ticket → plan path (grouped by story), each with its
one-line summary. The user reviews on disk. For any doc that is off, re-dispatch just that one
subagent with the user's feedback appended. Proceed to Phase 5 only on approval.
```

- [ ] **Step 4: Validate via dry-run**

Run dry-run through Phase 4. Open one generated milestone spec and one ticket plan from `.dryrun/`. Confirm: the spec has the required sections; the plan begins with the `**Milestone spec:**` token (path resolves) and a `**Depends on:**` line where the ticket had blockers; the plan is intent-level (not full code).

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/commands/projectit.md
git commit -m "feat: add projectit bulk doc generation via subagents"
```

---

## Task 6: `/projectit` Phase 5 (link Linear + mark ready) + label bootstrap

**Files:**
- Modify: `plugins/personal/commands/projectit.md`

**Interfaces:**
- Consumes: the hierarchy (Task 4), the generated docs (Task 5); Linear MCP `save_issue`, `save_milestone`, `create_issue_label`, `list_issue_labels`.
- Produces: each work ticket labeled `loop-ready` with plan/spec links — the producer→loop contract output.

- [ ] **Step 1: Write Phase 5**

```markdown
## Phase 5 — Link & mark ready

1. Ensure labels exist: `list_issue_labels`; if `user-story` or `loop-ready` is missing,
   `create_issue_label` it. (Dry-run prints instead.)
2. For each work ticket: update its description to include the relative plan path and a reference to
   its milestone spec; if `DOCS_DIR` is committed and pushed, also add a `links` attachment to the
   plan's GitHub URL. Add `labels=["loop-ready"]`.
3. For each milestone: add its spec path/link to the milestone description.
4. **Do not** set `status` on anything.
Report a final summary: project URL, counts of milestones/stories/tickets, and the `loop-ready` count.
```

- [ ] **Step 2: Validate via dry-run**

Run dry-run end-to-end. Confirm Phase 5 prints: label-existence checks, per-ticket description updates + `loop-ready` label application, milestone description updates, and zero `status` writes.

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/commands/projectit.md
git commit -m "feat: add projectit linking and loop-ready marking"
```

---

## Task 7: End-to-end sandbox run + contract test

**Files:** none (validation only)

**Interfaces:**
- Consumes: the finished `/projectit` command and the modified `/implementit`.

- [ ] **Step 1: Real run on a sandbox**

In a throwaway initiative/project (or a low-stakes real one), run `/personal:projectit "a small 2-milestone idea"` for real (no `--dry-run`). Step through the gates. Confirm the Linear hierarchy is created correctly (milestones, stories, parented tickets, `blockedBy` edges, labels) and that specs/plans exist on disk with the contract tokens.

- [ ] **Step 2: Contract test through `/implementit`**

Pick one `loop-ready` ticket whose blockers (if any) are satisfied. Run `/personal:implementit <TICKET-ID>`. Confirm it locates the plan by ID, follows the `**Milestone spec:**` token to load the milestone spec, and that the combined plan + spec are sufficient for implementation to proceed without `/planit`. Note any gaps in the resilient-plan level of detail and adjust the Phase-4 subagent instructions if needed.

- [ ] **Step 3: Idempotency check**

Re-run `/personal:projectit` on the same project. Confirm it updates in place (matches milestones by name, issues by title) and does not duplicate.

- [ ] **Step 4: Clean up the sandbox**

Archive/delete the sandbox Linear project and remove any `.dryrun/` artifacts.

---

## Self-Review

**Spec coverage** (each spec section → task):
- `/projectit` Phases 0–5 → Tasks 3, 4, 5, 6.
- Linear hierarchy mechanics + `blockedBy` + idempotency → Task 4.
- Spec/plan document model + on-disk naming + subagent dispatch → Tasks 1 (naming) + 5 (content/dispatch).
- The contract (loop-ready label, plan-by-ID, milestone-spec reference, execution order) → Tasks 5 (tokens) + 6 (label/links) + 2 (`/implementit` consumes).
- Required `/implementit` change → Task 2.
- `linear_initiative`/`linear_team` hint convention → Task 1 (defined), Task 3 (used).
- Testing (dry-run + e2e contract test) → dry-run in Tasks 3–6, e2e in Task 7.
- Commit-the-docs recommendation → covered operationally (docs land in tracked `DOCS_DIR`); plain-commit-vs-PR left to the user per spec.

**Placeholder scan:** No "TBD"/"add error handling"/"similar to" placeholders; each step gives the literal content to write or the literal command to run.

**Type/token consistency:** The contract tokens `**Milestone spec:** ` and `**Depends on:** `, the labels `user-story`/`loop-ready`, the filename patterns, and the `--dry-run` flag are defined once in Global Constraints and referenced identically in Tasks 1, 2, 5, 6. The MCP call signatures (`save_issue`, `save_project`, `save_milestone`, `create_issue_label`, `list_initiatives`) match the live schemas.
