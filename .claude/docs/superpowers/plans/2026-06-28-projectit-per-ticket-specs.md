# projectit per-ticket specs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make projectit emit a self-contained `spec + plan` per ticket in that ticket's own repo (planit parity), dropping the milestone-spec model, so it works for multi-repo projects.

**Architecture:** Prose edits to two Claude Code slash-command markdown files (`projectit.md`, `implementit.md`) plus a plugin version bump. projectit resolves `DOCS_DIR` per the ticket's assigned repo and writes both a spec and a plan there; the plan links its same-repo spec. implementit learns to load a `**Spec:**`-referenced spec. No Python/code changes.

**Tech Stack:** Markdown command definitions; `plugins/personal/.claude-plugin/plugin.json`. No tests framework (prose commands) — verification is `grep` + read-through + a `--dry-run` reasoning check.

**Design spec:** `../specs/2026-06-28-projectit-per-ticket-specs-design.md`

## Global Constraints

- These are **prose command** edits — no unit tests. Verify each with the `grep` checks given and a read-through.
- **Backward compatible:** single-repo projects must behave as today; existing plans using `**Milestone spec:**` must keep working (implementit keeps recognizing that header).
- **Per-repo placement:** every generated spec/plan goes under the **assigned repo's** `DOCS_DIR` (`docs_dir_for(repo)`), never one global `DOCS_DIR`.
- **No shared spec file:** do not reintroduce a milestone- or project-level spec **file**; cross-cutting decisions are inlined into each ticket's self-contained spec.
- Rollout requires a plugin **version bump** — headless loop/command runs use the installed plugin.
- Do not set issue `status` (connector owns it) — unchanged from current projectit.

---

### Task 1: Per-repo DOCS_DIR resolution + repo path mapping (projectit Phase 0 / Conventions)

**Files:**
- Modify: `plugins/personal/commands/projectit.md` (Conventions bullet at line 6; Phase 0 step 7)

**Interfaces:**
- Produces: the notion `docs_dir_for(repo)` and a repo→local-path mapping used by Tasks 2–3.

- [ ] **Step 1: Replace the Conventions DOCS_DIR bullet**

Replace line 6 (`- Resolve \`DOCS_DIR\` exactly as \`/personal:planit\` does ...`) with:

```markdown
- **Per-repo docs.** Each ticket's docs live in **its assigned repo**. Define `docs_dir_for(repo)`:
  resolve `DOCS_DIR` from *that repo's* root + its `CLAUDE.md` exactly as `/personal:planit` does
  (`specs_dir` override → umbrella `<umbrella>/docs` → single-repo `<repo>/.claude/docs`). Cache per
  repo. A single-repo project resolves once (unchanged behavior). There is **no** project- or
  milestone-level shared docs location.
```

- [ ] **Step 2: Extend Phase 0 step 7 to record local paths + handle missing repos**

Append to the end of Phase 0 step 7 (after the existing REPOS resolution text):

```markdown
   For each repo in `REPOS`, also record its **local filesystem path** (the sibling-scan in tier (b)
   yields these directly; for repos resolved via tier (a)/(c) without a known path, locate the repo
   under the workspace or ask the user). This path is required to read the repo's `CLAUDE.md` and to
   write its docs. If an assigned repo is **not checked out locally**, note it and **skip generating
   that repo's docs** in Phase 4 (the ticket is still created and labeled in Linear; its spec/plan can
   be authored later with `/personal:planit` run inside that repo).
```

- [ ] **Step 3: Verify**

```bash
cd plugins/personal/commands
grep -n 'docs_dir_for' projectit.md          # new concept present
grep -n 'local filesystem path' projectit.md # repo path mapping present
! grep -n 'Resolve `DOCS_DIR` exactly as `/personal:planit` does (specs_dir override; else umbrella' projectit.md  # old single-DOCS_DIR bullet gone
```
Expected: first two print a line; the negated third succeeds (old bullet replaced).

- [ ] **Step 4: Commit**

```bash
git add plugins/personal/commands/projectit.md
git commit -m "feat(projectit): resolve DOCS_DIR per assigned repo (per-repo docs)"
```

---

### Task 2: Phase 4 — per-ticket spec+plan, drop the milestone-spec round

**Files:**
- Modify: `plugins/personal/commands/projectit.md` (Phase 4 section, current lines ~70–101)

**Interfaces:**
- Consumes: `docs_dir_for(repo)` + repo paths (Task 1).
- Produces: per ticket, `docs_dir_for(ticket.repo)/superpowers/specs/<TICKET-ID>-<slug>.md` and
  `…/plans/<TICKET-ID>-<slug>.md`; each plan begins with `**Spec:** ../specs/<TICKET-ID>-<slug>.md`
  and `**Depends on:** …`. Consumed by Task 3 (Phase 5) and by implementit (Task 4).

- [ ] **Step 1: Replace the entire Phase 4 section**

Replace from `## Phase 4 — Bulk doc generation (subagents)` through the end of the `### ■ Bulk review gate` block with:

````markdown
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
````

- [ ] **Step 2: Verify**

```bash
cd plugins/personal/commands
grep -n 'docs_dir_for(ticket.repo)' projectit.md      # per-repo placement
grep -n '\*\*Spec:\*\* ../specs/<TICKET-ID>' projectit.md   # plan links same-repo spec
grep -n 'self-contained' projectit.md                 # per-ticket self-contained spec
! grep -n 'milestone spec' projectit.md               # milestone-spec model gone (case-insensitive check below)
! grep -niE 'Round 1 — milestone specs|<project-slug>-m<NN>-<slug>' projectit.md
```
Expected: first three print lines; the negated checks succeed (no milestone-spec round remains).

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/commands/projectit.md
git commit -m "feat(projectit): emit per-ticket spec+plan in each ticket's repo; drop milestone specs"
```

---

### Task 3: Phase 5 — per-repo paths, Plan/Spec header, drop milestone-spec step

**Files:**
- Modify: `plugins/personal/commands/projectit.md` (Phase 5 Step 2; remove Step 3; the closing loop note)

**Interfaces:**
- Consumes: per-ticket spec/plan paths in each repo (Task 2).

- [ ] **Step 1: Rewrite Phase 5 Step 2's path computation + header**

In `### Step 2 — Update work-ticket descriptions and apply \`loop-ready\``, replace the bullet list that
computes paths and the prepended header block with:

```markdown
For each work ticket (leaf-level issue, not stories), with `DOCS_DIR = docs_dir_for(ticket.repo)`:

- **Relative plan path:** `DOCS_DIR/superpowers/plans/<TICKET-ID>-<slug>.md` relative to `DOCS_DIR`
  (e.g. `superpowers/plans/PRD-42-add-widget.md`).
- **Relative spec path:** `superpowers/specs/<TICKET-ID>-<slug>.md`.
- **GitHub plan URL (best-effort):** if the ticket's repo `DOCS_DIR` is committed + pushed, construct
  `<that-repo-remote-url>/blob/<default-branch>/<DOCS_DIR-relative-plan-path>`; else skip the attachment.

Call `save_issue(id=<ticket-id>, description=<updated>, labels=["loop-ready", "repo:<assigned-repo>"])`
where the updated description prepends:

```
**Plan:** <relative plan path>
**Spec:** <relative spec path>
```
```

- [ ] **Step 2: Remove Phase 5 Step 3 (milestone descriptions)**

Delete the entire `### Step 3 — Update milestone descriptions` block (there is no milestone-spec file
to reference). Renumber the former `### Step 4 — Final summary` to `### Step 3 — Final summary`.

- [ ] **Step 3: Update the closing loop note**

In the final paragraph, ensure it reads that the loop reads each ticket's plan from **its own repo's**
docs by ticket ID. Replace any wording implying a single docs location with:

```markdown
The loop selects work tickets by the `loop-ready` label **scoped to the repo it runs in** (the
`repo:<name>` label) and reads each ticket's plan from **that repo's** docs by ticket ID. The Linear
`links` attachment from Step 2 is a human-convenience reference, not load-bearing for the loop.
```

- [ ] **Step 4: Verify**

```bash
cd plugins/personal/commands
grep -n '\*\*Spec:\*\* <relative spec path>' projectit.md     # new header
grep -n 'docs_dir_for(ticket.repo)' projectit.md              # per-repo path base in Phase 5
! grep -n 'Update milestone descriptions' projectit.md        # Step 3 removed
! grep -n 'Milestone spec (repo)' projectit.md                # old header gone
grep -n '### Step 3 — Final summary' projectit.md             # Step 4 renumbered to 3
```
Expected: the two `grep`s print lines; the two negated checks succeed; the renumber check prints a line.

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/commands/projectit.md
git commit -m "feat(projectit): per-repo Phase 5 paths + Plan/Spec header; drop milestone-desc step"
```

---

### Task 4: implementit recognizes a `**Spec:**` header

**Files:**
- Modify: `plugins/personal/commands/implementit.md` (Step 3)

**Interfaces:**
- Consumes: plans written by Task 2 that start with `**Spec:** ../specs/<TICKET-ID>-<slug>.md`.

- [ ] **Step 1: Broaden Step 3's recognized header**

In `## Step 3 — Load the milestone spec (if the plan references one)`, change the detection so it
recognizes **both** headers. Replace the sentence that looks for a line beginning `**Milestone spec:** `
with:

```markdown
Read the chosen plan file. If it contains a line beginning `**Spec:** ` **or** `**Milestone spec:** `,
resolve that relative path (from the plan file's location) and read the referenced spec. Pass **both**
the plan and the spec to the implementation in Step 5 as design context.
```

Optionally retitle the step to `## Step 3 — Load the referenced spec (if the plan references one)`.

- [ ] **Step 2: Verify**

```bash
cd plugins/personal/commands
grep -n '`\*\*Spec:\*\* `' implementit.md            # recognizes new header
grep -n 'Milestone spec:' implementit.md             # still recognizes old header (backward compat)
```
Expected: both print a line.

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/commands/implementit.md
git commit -m "feat(implementit): load a **Spec:**-referenced per-ticket spec (keep **Milestone spec:**)"
```

---

### Task 5: Version bump (rollout)

**Files:**
- Modify: `plugins/personal/.claude-plugin/plugin.json`

**Interfaces:**
- Consumes: nothing.

- [ ] **Step 1: Bump the version**

Edit `plugins/personal/.claude-plugin/plugin.json`: bump `version` to the next minor above the
current released value. (At authoring time main is `0.10.0` and the loop-final-review fix is `0.11.0`;
if that has merged, set `0.12.0` — otherwise set the next unused minor. Pick the value that is one
above whatever `version` currently reads on the branch you're building from.)

- [ ] **Step 2: Verify**

```bash
cd /Users/trb74/claude-skills
grep -n '"version"' plugins/personal/.claude-plugin/plugin.json   # shows the bumped value
```
Expected: prints the new version, strictly greater than the prior value.

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/.claude-plugin/plugin.json
git commit -m "chore(personal): release (projectit per-ticket specs)"
```

After merge, update + reload the plugin so command runs pick up the new projectit/implementit text.

---

## Self-Review

- **Spec coverage:** §2 decision (per-ticket spec+plan, drop milestone) → Tasks 2,3,4. §3 Conventions/Phase 0 (per-repo `docs_dir_for`, repo paths, skip-if-not-checked-out) → Task 1. §3 Phase 4 (cross-ticket design pass, per-ticket per-repo docs, `**Spec:**`/`**Depends on:**` header, dry-run) → Task 2. §3 Phase 5 (per-repo paths, `**Plan:**`/`**Spec:**`, drop Step 3) → Task 3. §3 implementit Step 3 broadening → Task 4. §4 backward compat → preserved in Tasks 1 (single-repo collapses) & 4 (keeps `**Milestone spec:**`). §6 testing → the `--dry-run` checks are called out in the spec; each task carries its grep verification. Rollout (§ "headless uses installed plugin") → Task 5. No gaps.
- **Placeholder scan:** every edit gives concrete replacement text + grep checks. The one variable is Task 5's version value, which is specified as a rule (next minor above current) with the concrete expected value (0.12.0 if 0.11.0 merged) — deliberate, not a placeholder.
- **Consistency:** `docs_dir_for(repo)` (Task 1) is used verbatim in Tasks 2–3; the `**Spec:** ../specs/<TICKET-ID>-<slug>.md` header produced in Task 2 is exactly what Task 4 teaches implementit to read and what Task 3's Phase-5 path computation mirrors. No drift.
