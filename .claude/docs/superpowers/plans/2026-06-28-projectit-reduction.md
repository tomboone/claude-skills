# projectit Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** ../specs/2026-06-28-projectit-reduction-design.md

**Goal:** Reduce `/personal:projectit` to project-shaping only (Phases 0–3) and move per-ticket spec/plan authoring to `/personal:planit`, just-in-time.

**Architecture:** Two Claude Code slash-command markdown files are edited in place. `projectit.md` loses Phase 4 (bulk doc-gen) and Phase 5 (labels + plan-wiring) and the machinery that supported them; `planit.md` gains two context-gathering touch-ups so cross-ticket coherence survives. No code, no build step, no test runner — these are instruction documents for an agent. Verification is grep assertions on the edited files plus a read-through against the spec's acceptance criteria.

**Tech Stack:** Markdown command files under `plugins/personal/commands/`; Linear MCP (invoked at runtime by the command, not by this plan); `git` for commits.

## Global Constraints

- All Linear writes stay deferred to one batch after the Phase 3 gate; the batch stays idempotent (look up by id/name/title, update matches, never duplicate).
- `--dry-run` still prints every Linear write instead of executing it.
- `/projectit` applies **no labels of any kind** (no `loop-ready`, `repo:<name>`, or `user-story`).
- `/projectit` never sets issue `status` (the GitHub↔Linear connector owns it).
- `/planit` plan/spec storage naming is unchanged: `DOCS_DIR/superpowers/{specs,plans}/<TICKET_ID>-<slug>.md`.
- Commit messages: Conventional Commits, no Linear parenthetical (none maps), no footer, no `Co-Authored-By`.

---

### Task 1: Reduce `projectit.md` to Phases 0–3 + Done

**Files:**
- Modify: `plugins/personal/commands/projectit.md` (currently 178 lines, 5 phases)

**Interfaces:**
- Consumes: the Linear MCP (`save_project`, `save_milestone`, `save_issue`) and repo `CLAUDE.md` hints (`linear_initiative`, `linear_team`, `linear_repos`) — all already referenced by the command.
- Produces: a Linear project (project + milestones-with-contracts + stories + tickets + `blockedBy` deps) and a Done summary pointing at `/personal:planit`. No docs, no labels, no plan-wiring.

- [ ] **Step 1: Replace the title/usage line.** Find the first line and replace it.

  Old:
  ```
  # Scaffold a whole Linear project (milestones, stories, tickets) and pre-generate milestone specs + ticket plans.
  ```
  New:
  ```
  # Scaffold a Linear project: brainstorm it, break it into milestones, stories, and work tickets, and create them in Linear. Per-ticket specs/plans are authored later, just-in-time, with /personal:planit.
  ```

- [ ] **Step 2: Replace the "## Conventions used by this command" section.** Replace everything from `## Conventions used by this command` up to (not including) `## Phase 0 — Resolve the Linear target  ■ gate` with:

  ```
  ## Conventions used by this command

  - **Dry-run:** if `--dry-run` is passed, make NO `save_*`/`create_*` Linear calls. Instead print each Linear write you would make. Every phase honors this — its write step prints instead of executing when dry-run is active.
  - **Never** set issue `status` — the GitHub↔Linear connector owns it.
  - **No labels.** This command applies no labels of any kind. Ticket selection is manual, and per-ticket specs/plans are authored later with `/personal:planit`.
  - Create nothing in Linear until after the Phase 3 gate.

  ```
  (This deletes the `docs_dir_for(repo)` / per-repo-docs bullet entirely.)

- [ ] **Step 3: Simplify Phase 0 step 7 (repos).** In `## Phase 0`, keep steps 1–6 verbatim. Replace step 7 (the `Candidate repos (\`REPOS\`)` paragraph, which currently spans the 3-tier resolution + local filesystem paths + not-checked-out handling) with:

  ```
  7. **Target repos (multi-repo projects only):** if this project's tickets may span more than one repo, resolve the set of repo **names** — most authoritative first: (a) a `linear_repos:` list in `CLAUDE.md`; else (b) ask the user to name them. Record the set as `REPOS` (names only — no local paths and no docs-dir resolution or pinning). If the project targets a single repo, skip repo handling entirely and tickets carry no target-repo line.
  ```

- [ ] **Step 4: Add shared contracts to Phase 2.** Replace the `## Phase 2 — Milestones  ■ gate` section with:

  ```
  ## Phase 2 — Milestones + shared contracts  ■ gate

  Propose milestones as a list of {name, one-paragraph goal, order}. For each milestone, also draft the **cross-cutting decisions siblings must agree on before either is built** — the API shape a backend ticket exposes and a frontend ticket consumes, a shared data model, naming conventions. Fold these into the milestone's description as a short **Shared contracts** section beneath the goal. **■ Gate:** user edits/approves. **Hold the approved milestone list (goals + contracts)** for the Phase-3 creation batch — do not write to Linear yet.
  ```

- [ ] **Step 5: Rewrite Phase 3 (target-repo line, no labels, contracts in milestone write).** Replace the entire `## Phase 3 — User stories & work tickets  ■ gate` section with:

  ````
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
  1. **Project:** if creating new, `save_project(name=<PROJECT_TO_CREATE>, addTeams=[<team>], addInitiatives=[<initiative>], description=<held Phase-1 description>)`; if reusing, `save_project(id=PROJECT, description=<held Phase-1 description>)`. Record `PROJECT`.
  2. **Milestones:** for each held milestone, `save_milestone(project=PROJECT, name=<name>, description=<goal + Shared contracts section>)`.
  3. **Stories:** `save_issue(title, team=TEAM, project=PROJECT, milestone=<name>, description=<story + acceptance criteria>)`. Record each identifier. **No label.**
  4. **Tickets:** `save_issue(title, team=TEAM, project=PROJECT, milestone=<name>, parentId=<story-id>, description=<intent; for multi-repo projects prepend a "**Target repo:** <name>" line>)`.
  5. **Dependencies:** for each "B builds on A", `save_issue(id=B, blockedBy=[A])`.

  **Idempotency:** before creating, look up the project (by id/name), milestones (by name), and issues
  (by title within PROJECT); update matches instead of duplicating. Safe to re-run.
  ````

- [ ] **Step 6: Delete Phases 4 and 5; add the Done summary.** Replace everything from `## Phase 4 — Bulk doc generation (subagents)` through the end of the file with the Done section below. (Inner fences shown as `~~~` — write them as triple backticks in the file.)

  ```
  ## Done — summary

  Print a summary block:

  ~~~
  Project: <Linear project URL>
  Milestones:   <count>
  User stories: <count>
  Work tickets: <count>

  Next: run /personal:planit {TICKET} in the ticket's repo to plan it just-in-time,
  then /personal:implementit {TICKET}.
  ~~~
  ```

- [ ] **Step 7: Verify removals and additions with grep.**

  Run:
  ```bash
  cd ~/claude-skills && grep -nE 'Phase 4|Phase 5|docs_dir_for|loop-ready|user-story|specs_dir|create_issue_label|pre-generate|Bulk doc' plugins/personal/commands/projectit.md
  ```
  Expected: no output (exit 1 — all removed tokens gone).

  Run:
  ```bash
  grep -nE 'Milestones \+ shared contracts|Shared contracts section|Target repo:|## Done — summary|planit \{TICKET\}' plugins/personal/commands/projectit.md
  ```
  Expected: matches for the milestone-contracts heading, the contracts write, the target-repo line, the Done heading, and the planit next-step.

- [ ] **Step 8: Read the file against the spec's acceptance criteria.**

  Read `plugins/personal/commands/projectit.md` start to finish. Confirm: only Phases 0–3 + Done; Phase 3 still defers all writes to one post-gate batch and is idempotent; `--dry-run` still prints; no labels; milestone write carries contracts; multi-repo tickets get a `**Target repo:**` line and single-repo runs omit it. Fix anything that drifted.

- [ ] **Step 9: Commit.**

  ```bash
  cd ~/claude-skills && git add plugins/personal/commands/projectit.md
  git commit -m "refactor(projectit): reduce to project-shaping; drop bulk doc-gen, labels, and plan-wiring"
  ```

---

### Task 2: Add the two coherence touch-ups to `planit.md`

**Files:**
- Modify: `plugins/personal/commands/planit.md` (Step 2 — Fetch the ticket; Step 4 — Hand off to Superpowers)

**Interfaces:**
- Consumes: the Linear MCP (already used in Step 2 to fetch the ticket) and the docs convention paths resolved in Step 1.
- Produces: richer design context for the Superpowers handoff — the parent milestone's shared contracts and merged dependencies' shipped specs/code — so just-in-time plans honor `/projectit`'s up-front contracts (mechanism B) and match what dependencies actually shipped (mechanism A). Storage naming is unchanged.

- [ ] **Step 1: Extend Step 2's extract list with two bullets.** In `## Step 2 — Fetch the ticket`, the bulleted "Extract:" list currently ends with the line beginning `- Any comments containing decisions`. Immediately after that bullet (before the `Summarise what you've gathered.` paragraph), add:

  ```
  - **Parent milestone (shared contracts):** fetch the ticket's parent milestone and read its description; surface any **Shared contracts** / cross-cutting decisions it records — the plan must honor these.
  - **Merged dependencies as ground truth:** for each `blockedBy` (or directly related) ticket that is already Done/merged, read its **actual shipped spec** (`DOCS_DIR/superpowers/specs/<DEP-ID>-*.md`) and the merged code it produced — not just the Linear text — so this plan matches what was really built.
  ```

- [ ] **Step 2: Reference the new context in the Step 4 handoff.** In `## Step 4 — Hand off to Superpowers`, the first paragraph begins `Present the ticket context you gathered in Step 2 as the starting point for design`. Replace that sentence with:

  ```
  Present the ticket context you gathered in Step 2 as the starting point for design — including the parent milestone's **Shared contracts** and any merged dependencies' shipped specs/code — so the design honors the established contracts and matches what was actually built.
  ```

- [ ] **Step 3: Verify the additions and confirm naming is untouched.**

  Run:
  ```bash
  cd ~/claude-skills && grep -nE 'Parent milestone \(shared contracts\)|Merged dependencies as ground truth|honors the established contracts' plugins/personal/commands/planit.md
  ```
  Expected: three matches (the two new bullets + the updated handoff sentence).

  Run:
  ```bash
  grep -nE 'superpowers/specs/\{TICKET_ID\}-<slug>|superpowers/plans/\{TICKET_ID\}-<slug>' plugins/personal/commands/planit.md
  ```
  Expected: the unchanged Step 4 save-path lines still present (storage naming untouched).

- [ ] **Step 4: Commit.**

  ```bash
  cd ~/claude-skills && git add plugins/personal/commands/planit.md
  git commit -m "feat(planit): read parent-milestone contracts and merged deps as ground truth"
  ```

---

## Notes on verification scope

There is no automated test suite for these command docs. The grep assertions above are the mechanical checks; the real proof is a `--dry-run` of `/projectit` on a small idea (confirms it produces project + milestones-with-contracts + stories + tickets, no labels, no docs, and a planit-pointing Done summary) followed by a `/planit` on one resulting ticket (confirms it pulls the milestone contracts). Those are interactive smoke tests for the user to run after merge, not steps an agent executes headlessly here.
