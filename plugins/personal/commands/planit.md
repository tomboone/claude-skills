---
description: Research a Linear ticket, then confirm its spec is implementation-ready or grill it into shape
argument-hint: "{TICKET_ID}"
---

**CRITICAL: Follow every step in order. Do not skip or reorder steps.**

## Step 1 — Resolve the docs directory

Determine `DOCS_DIR` for this project (must resolve the same on every machine):
1. **Override:** if any loaded `CLAUDE.md` defines `specs_dir`, `DOCS_DIR` = that value (resolve relative paths from the project root); skip to "Specs live in…".
2. **No `specs_dir`? Offer to pin one** (do not silently auto-resolve): detect an existing superpowers docs tree under the repo (`<repo>/docs/superpowers`, `<repo>/.claude/docs/superpowers`, or umbrella `<umbrella>/docs/superpowers`) and propose `specs_dir` = its base; else propose the default `specs_dir: docs`. On confirm, write `specs_dir: <value>` into the repo's `CLAUDE.md` (prefer `.claude/CLAUDE.md`) and use `DOCS_DIR = <repo>/<value>`. On decline, continue to step 3. (See `spec-and-plan-convention.md`.)
3. **Auto-resolve** (only if not pinned) via `git rev-parse --show-toplevel` and the repo root's parent:
   - **Umbrella layout** — parent is *not* a git repo and holds sibling code repos (e.g. a backend and a frontend): `DOCS_DIR = <umbrella>/docs`.
   - **Single-repo layout** — the repo stands alone: `DOCS_DIR = <repo-root>/.claude/docs`.
   - If genuinely ambiguous, ask the user.

Specs live in `DOCS_DIR/specs/`, plans in `DOCS_DIR/plans/`. Filenames are `<TICKET_ID>-<short-slug>.md`. Create the folders if missing. (Older projects may still have specs/plans under the retired `DOCS_DIR/superpowers/{specs,plans}/` layout — Step 3 checks both.)

## Step 2 — Fetch the ticket

Use the Linear MCP to fetch ticket `{TICKET_ID}`. Extract:
- Title and description
- Priority and type
- Any attached documents or file links (fetch their contents)
- Parent ticket, sub-issues, and directly related tickets — fetch each and note how they relate
- Any comments containing decisions, constraints, or clarifications (ignore status-update noise)
- **Parent milestone (shared contracts):** fetch the ticket's parent milestone and read its description; surface any **Shared contracts** / cross-cutting decisions it records — the plan must honor these.
- **Project-wide spec:** fetch the ticket's parent Linear project's description; if it contains a `**Project spec:**` line (written by `/personal:projectit` Phase 1), resolve and read that file too — it may already cover this ticket in full.
- **Merged dependencies as ground truth:** for each `blockedBy` (or directly related) ticket that is already Done/merged, read its **actual shipped spec** (`DOCS_DIR/specs/<DEP-ID>-*.md`, or `DOCS_DIR/superpowers/specs/<DEP-ID>-*.md` for older tickets) and the merged code it produced — not just the Linear text — so this plan matches what was really built.

Summarise what you've gathered. Flag any ambiguities that would need resolving before implementation.

## Step 3 — Check for an existing spec

Either of these sources can satisfy this ticket:

- A **per-ticket spec or plan**: any file whose name contains `{TICKET_ID}` (case-insensitive), in **both** supported layouts — `DOCS_DIR/{specs,plans}/` (current convention) and `DOCS_DIR/superpowers/{specs,plans}/` (retired layout, older tickets only). Also scan for files whose names match the ticket title closely enough to be the same thing.
- The **project-wide spec** fetched in Step 2 (if any), if its coverage of this ticket is detailed enough on its own.

Read whichever exists (both, if both exist) fully. Evaluate whether the two together are sufficient for a developer or AI agent to begin implementation without further clarification. Sufficient means covering:
- What to build and why
- Acceptance criteria or observable outcomes
- Key technical decisions and constraints
- Any known unknowns explicitly called out as out of scope or deferred

**If sufficient:** Tell the user it looks implementation-ready — name which source(s) covered it (per-ticket file, project-wide spec, or both) and give a one-paragraph summary. Tell the user to clear context and run `/personal:implementit {TICKET_ID}` when ready. Stop here — do not begin implementation.

**If insufficient (or nothing found at all):** Tell the user what's missing. Then continue to Step 4.

## Step 4 — Grill it into a spec

Present the ticket context you gathered in Step 2 — including the parent milestone's **Shared contracts**, the project-wide spec (if any), and any merged dependencies' shipped specs/code — as the starting point for design, then run a `/personal:grilling` session, using `/personal:domain-modeling` alongside it. Frame the problem using the ticket title, description, and any relevant attached docs or related ticket context you fetched, so the design honors the established contracts and matches what was actually built. Update `CONTEXT.md` and any ADRs inline as decisions crystallize. Do not implement anything yourself.

`/personal:grilling`/`/personal:domain-modeling` sharpen the design and the repo's shared vocabulary — they do not, on their own, produce a per-ticket spec file. Once the session reaches shared understanding, write the spec yourself to `DOCS_DIR/specs/{TICKET_ID}-<slug>.md` (create the folder if missing): what to build and why, acceptance criteria, key technical decisions and constraints, anything explicitly out of scope or deferred. This is the file `/personal:implementit` will look for by ticket ID — no separate step-by-step implementation plan is authored; `/personal:implementit` implements straight from this spec.

When done, tell the user to clear context and run `/personal:implementit {TICKET_ID}` when ready. Stop here.
