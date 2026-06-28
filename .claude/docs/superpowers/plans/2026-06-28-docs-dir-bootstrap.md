# Docs-dir bootstrap (pin specs_dir on first use) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make `/planit` and `/projectit` offer to pin `specs_dir` in a repo's `CLAUDE.md` when none is set, so `DOCS_DIR` is explicit from first use instead of silently auto-resolving to the wrong place.

**Architecture:** Prose edits to the canonical `spec-and-plan-convention.md` (define the offer once) and to `planit.md` / `projectit.md` (invoke it). `implementit`/`reviewit`/the loop are untouched and never prompt. No code.

**Tech Stack:** Markdown command/convention files. No test framework — verify via `grep` + read-through.

**Design spec:** `../specs/2026-06-28-docs-dir-bootstrap-design.md`

## Global Constraints

- Prose edits only — verify with the `grep` checks given.
- **Authoring-only:** the offer lives in `/planit` + `/projectit`. **Do not** add any prompt/offer to `implementit.md` or `reviewit.md` — they stay read-only/headless-safe.
- **Greenfield default = `docs`** (`specs_dir: docs`). Detect an existing superpowers tree first and prefer that.
- **Backward compatible:** `specs_dir` already set → no offer; decline → current auto-resolution unchanged.
- Ships in the **same release** as the open PR (#18); version stays `0.11.0` (no extra bump).

---

### Task 1: Define the offer in the canonical convention doc

**Files:**
- Modify: `plugins/personal/spec-and-plan-convention.md` ("Resolving the docs directory (`DOCS_DIR`)" section)

**Interfaces:**
- Produces: the canonical "pin `specs_dir` if unset" procedure that Tasks 2–3 reference.

- [ ] **Step 1: Insert the pin-offer step**

In the numbered list under `## Resolving the docs directory (\`DOCS_DIR\`)`, insert a new **step 2**
between the `specs_dir` override (step 1) and auto-resolve (currently step 2), and renumber the rest:

```markdown
2. **No `specs_dir`? Authoring commands offer to pin one.** When resolving for an **authoring command
   (`/planit`, `/projectit`)** and no loaded `CLAUDE.md` sets `specs_dir`, do **not** silently
   auto-resolve — offer to make the convention explicit:
   - **Detect** an existing superpowers docs tree under the repo, in order: `<repo>/docs/superpowers`,
     `<repo>/.claude/docs/superpowers`, or (umbrella) `<umbrella>/docs/superpowers`. If found, propose
     `specs_dir` = its base (`docs`, `.claude/docs`, or the umbrella path) — "lock to existing docs."
   - **Else** propose the default **`specs_dir: docs`** (a `docs/` folder at the repo root).
   - Show the proposal; the user confirms, edits the value, or declines.
   - **On confirm:** write `specs_dir: <value>` into the repo's `CLAUDE.md` (prefer an existing
     `.claude/CLAUDE.md`, else `CLAUDE.md`; create `.claude/CLAUDE.md` if neither exists) and ensure
     `<DOCS_DIR>/superpowers/{specs,plans}` exist. `DOCS_DIR = <repo>/<value>`.
   - **On decline:** fall through to auto-resolution (next step) for this run.
   **Read-only commands (`/implementit`, `/reviewit`) and the loop never prompt** — they skip this
   step, auto-resolve, and report if nothing is found. (`/projectit` runs this offer **per assigned
   repo** via `docs_dir_for(repo)`.)
```

- [ ] **Step 2: Verify**

```bash
cd plugins/personal
grep -n 'offer to pin' spec-and-plan-convention.md
grep -n 'never prompt' spec-and-plan-convention.md
grep -n 'lock to existing docs' spec-and-plan-convention.md
```
Expected: each prints a line.

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/spec-and-plan-convention.md
git commit -m "feat(convention): authoring commands offer to pin specs_dir when unset"
```

---

### Task 2: Wire the offer into `/planit` Step 1

**Files:**
- Modify: `plugins/personal/commands/planit.md` (Step 1)

**Interfaces:**
- Consumes: the convention's pin-offer (Task 1).

- [ ] **Step 1: Replace planit Step 1's resolution list**

Replace the numbered list in `## Step 1 — Resolve the docs directory` (the `1. Override … 2. Otherwise
auto-resolve …` block) with:

```markdown
1. **Override:** if any loaded `CLAUDE.md` defines `specs_dir`, `DOCS_DIR` = that value (resolve
   relative paths from the project root); skip to Step 2.
2. **No `specs_dir`? Offer to pin one (do not silently auto-resolve):** detect an existing superpowers
   docs tree under the repo (`<repo>/docs/superpowers`, `<repo>/.claude/docs/superpowers`, or umbrella
   `<umbrella>/docs/superpowers`) and propose `specs_dir` = its base; else propose the default
   `specs_dir: docs`. On confirm, write `specs_dir: <value>` into the repo's `CLAUDE.md` (prefer
   `.claude/CLAUDE.md`) and use `DOCS_DIR = <repo>/<value>`. On decline, continue to step 3. (See
   `spec-and-plan-convention.md`.)
3. **Auto-resolve** (only if not pinned) via `git rev-parse --show-toplevel` and the repo root's parent:
   - **Umbrella layout** — parent is *not* a git repo and holds sibling code repos: `DOCS_DIR = <umbrella>/docs`.
   - **Single-repo layout** — the repo stands alone: `DOCS_DIR = <repo-root>/.claude/docs`.
   - If genuinely ambiguous, ask the user.
```

(Leave the trailing "Specs live in … Create the folders if missing." sentence as-is.)

- [ ] **Step 2: Verify**

```bash
cd plugins/personal/commands
grep -n 'Offer to pin one' planit.md
grep -n 'specs_dir: docs' planit.md
```
Expected: both print a line.

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/commands/planit.md
git commit -m "feat(planit): offer to pin specs_dir when unset (Step 1)"
```

---

### Task 3: Wire the offer into `/projectit` (per repo)

**Files:**
- Modify: `plugins/personal/commands/projectit.md` (the `docs_dir_for` Conventions bullet)

**Interfaces:**
- Consumes: the convention's pin-offer (Task 1); the per-repo `docs_dir_for(repo)` (already present).

- [ ] **Step 1: Extend the `docs_dir_for` bullet with the per-repo offer**

In the Conventions bullet that defines `docs_dir_for(repo)`, append after the existing sentence about
resolving from the repo's `CLAUDE.md`:

```markdown
  When a repo has no `specs_dir`, `docs_dir_for(repo)` runs the convention's **pin-`specs_dir` offer
  for that repo** (detect an existing superpowers tree → else default `specs_dir: docs`; on confirm,
  write it into that repo's `CLAUDE.md` and create the folders) before falling back to
  auto-resolution. Phase 0 is interactive, so do this per assigned repo as repos are resolved; a repo
  not checked out locally can't be pinned — skip it (as for doc generation). See
  `spec-and-plan-convention.md`.
```

- [ ] **Step 2: Verify**

```bash
cd plugins/personal/commands
grep -n "pin-\`specs_dir\` offer" projectit.md
grep -n 'per assigned repo' projectit.md
```
Expected: both print a line.

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/commands/projectit.md
git commit -m "feat(projectit): pin specs_dir per repo when unset (docs_dir_for)"
```

---

### Task 4: Confirm read-only commands stay untouched

**Files:**
- Inspect only: `plugins/personal/commands/implementit.md`, `plugins/personal/commands/reviewit.md`

- [ ] **Step 1: Verify no offer leaked into read-only commands**

```bash
cd plugins/personal/commands
! grep -niE 'offer to pin|pin .?specs_dir' implementit.md
! grep -niE 'offer to pin|pin .?specs_dir' reviewit.md
```
Expected: both negated checks succeed (no pin/offer language — they remain read-only).

- [ ] **Step 2: (no commit — inspection only)**

---

## Self-Review

- **Spec coverage:** §3 offer procedure → Task 1 (canonical) + Tasks 2–3 (wiring). §4 applies-to (planit, projectit per-repo; implementit/reviewit untouched) → Tasks 2,3,4. §5 convention-doc change → Task 1. §6 backward compat → preserved (override short-circuits; decline falls through; read-only unchanged, asserted in Task 4). §7 out-of-scope respected (auto-resolution fallback unchanged; no implementit/reviewit prompting). §8 testing → each task's grep checks. No gaps.
- **Placeholder scan:** every edit has concrete replacement text + grep checks. No TBDs.
- **Consistency:** the offer wording (detect-existing → default `docs` → write to repo CLAUDE.md) is identical across the convention doc (Task 1), planit (Task 2), and projectit (Task 3); `docs_dir_for(repo)` matches the term introduced by the projectit per-ticket change.
