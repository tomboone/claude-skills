# Research a Linear ticket, then confirm the spec is implementation-ready or hand off to Superpowers to design and plan.
# Usage: /personal:planit {TICKET_ID}

## Step 1 — Resolve the docs directory

Determine `DOCS_DIR` for this project (must resolve the same on every machine):
1. **Override:** if any loaded `CLAUDE.md` defines `specs_dir`, `DOCS_DIR` = that value (resolve relative paths from the project root); skip to "Specs live in…".
2. **No `specs_dir`? Offer to pin one** (do not silently auto-resolve): detect an existing superpowers docs tree under the repo (`<repo>/docs/superpowers`, `<repo>/.claude/docs/superpowers`, or umbrella `<umbrella>/docs/superpowers`) and propose `specs_dir` = its base; else propose the default `specs_dir: docs`. On confirm, write `specs_dir: <value>` into the repo's `CLAUDE.md` (prefer `.claude/CLAUDE.md`) and use `DOCS_DIR = <repo>/<value>`. On decline, continue to step 3. (See `spec-and-plan-convention.md`.)
3. **Auto-resolve** (only if not pinned) via `git rev-parse --show-toplevel` and the repo root's parent:
   - **Umbrella layout** — parent is *not* a git repo and holds sibling code repos (e.g. a backend and a frontend): `DOCS_DIR = <umbrella>/docs`.
   - **Single-repo layout** — the repo stands alone: `DOCS_DIR = <repo-root>/.claude/docs`.
   - If genuinely ambiguous, ask the user.

Specs live in `DOCS_DIR/superpowers/specs/`, plans in `DOCS_DIR/superpowers/plans/`. Filenames are `<TICKET_ID>-<short-slug>.md`. Create the folders if missing.

## Step 2 — Fetch the ticket

Use the Linear MCP to fetch ticket `{TICKET_ID}`. Extract:
- Title and description
- Priority and type
- Any attached documents or file links (fetch their contents)
- Parent ticket, sub-issues, and directly related tickets — fetch each and note how they relate
- Any comments containing decisions, constraints, or clarifications (ignore status-update noise)

Summarise what you've gathered. Flag any ambiguities that would need resolving before implementation.

## Step 3 — Check for an existing spec or plan

Look in `DOCS_DIR/superpowers/specs/` and `DOCS_DIR/superpowers/plans/` for any file whose name contains `{TICKET_ID}` (case-insensitive). Also scan for files whose names match the ticket title closely enough to be the same thing.

### If a spec or plan file exists:

Read it fully. Evaluate whether it is sufficient for a developer or AI agent to begin implementation without further clarification. A spec is sufficient if it covers:
- What to build and why
- Acceptance criteria or observable outcomes
- Key technical decisions and constraints
- Any known unknowns explicitly called out as out of scope or deferred

**If sufficient:** Tell the user the spec looks implementation-ready. Show the file path and give a one-paragraph summary of what it covers. Tell the user to clear context and run `/personal:implementit {TICKET_ID}` when ready. Stop here — do not begin implementation.

**If insufficient:** Tell the user what's missing. Then continue to Step 4.

### If no spec file exists:

Continue to Step 4.

## Step 4 — Hand off to Superpowers

Present the ticket context you gathered in Step 2 as the starting point for design, then invoke the `superpowers:brainstorming` skill. Frame the problem for it using the ticket title, description, and any relevant attached docs or related ticket context you fetched.

Let Superpowers run its full brainstorming and `superpowers:writing-plans` workflow from here. Do not implement anything yourself.

**Direct Superpowers to save into this project's convention:**
- design / spec → `DOCS_DIR/superpowers/specs/{TICKET_ID}-<slug>.md`
- implementation plan → `DOCS_DIR/superpowers/plans/{TICKET_ID}-<slug>.md`

If Superpowers writes to a different location or filename, move and rename the outputs into the paths above after it finishes, so `/personal:implementit` can find them by ticket ID.

When done, tell the user to clear context and run `/personal:implementit {TICKET_ID}` when ready. Stop here.
