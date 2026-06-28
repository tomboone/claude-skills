# Spec & plan storage convention

The single rule for where design specs and implementation plans live. `/planit`, `/implementit`, and `/reviewit` resolve this identically on every machine, and Superpowers is directed to write into it. Keep a copy of this file in the plugin (`plugins/personal/spec-and-plan-convention.md`) so it travels with the commands.

## Resolving the docs directory (`DOCS_DIR`)

1. **Per-project override.** If any loaded `CLAUDE.md` defines a `specs_dir` value, `DOCS_DIR` = that value (relative paths resolve from the project root). Use it as-is and skip to *Layout*.

2. **No `specs_dir`? Authoring commands offer to pin one.** When resolving for an **authoring command (`/planit`, `/projectit`)** and no loaded `CLAUDE.md` sets `specs_dir`, do **not** silently auto-resolve — offer to make the convention explicit:
   - **Detect** an existing superpowers docs tree under the repo, in order: `<repo>/docs/superpowers`, `<repo>/.claude/docs/superpowers`, or (umbrella) `<umbrella>/docs/superpowers`. If found, propose `specs_dir` = its base (`docs`, `.claude/docs`, or the umbrella path) — "lock to existing docs."
   - **Else** propose the default **`specs_dir: docs`** (a `docs/` folder at the repo root).
   - Show the proposal; the user confirms, edits the value, or declines.
   - **On confirm:** write `specs_dir: <value>` into the repo's `CLAUDE.md` (prefer an existing `.claude/CLAUDE.md`, else `CLAUDE.md`; create `.claude/CLAUDE.md` if neither exists) and ensure `<DOCS_DIR>/superpowers/{specs,plans}` exist. `DOCS_DIR = <repo>/<value>`.
   - **On decline:** fall through to auto-resolution (next step) for this run.
   **Read-only commands (`/implementit`, `/reviewit`) and the loop never prompt** — they skip this step, auto-resolve, and report if nothing is found. `/projectit` runs this offer **per assigned repo** via `docs_dir_for(repo)`.

3. **Auto-resolve by project shape.** Find the repo root with `git rev-parse --show-toplevel`, then inspect its parent directory:
   - **Umbrella layout** — the repo root's parent is **not** a git repo and contains sibling code repos (typically a backend and a frontend). The umbrella (the non-git parent) is the project root. → `DOCS_DIR = <umbrella>/docs`, a sibling of the code repos.
   - **Single-repo layout** — the repo stands alone (its parent is not an umbrella of sibling repos). → `DOCS_DIR = <repo-root>/.claude/docs`.
   - If it's genuinely ambiguous, ask which applies before writing anything.

4. Create `DOCS_DIR` and the subfolders below if they don't exist.

## Linear target hints (for `/projectit`)

A repo may declare its Linear home so `/projectit` can resolve it without searching:

- `linear_initiative: <name-or-id>` — the initiative this repo's app belongs to (initiative ≈ one app).
- `linear_team: <name-or-key>` — the team new issues/projects are created in.

Set these in the repo's `CLAUDE.md` (sibling to `specs_dir`). If absent, `/projectit` searches
initiatives by name and asks for confirmation, then offers to write the confirmed values back.

## Layout

Under `DOCS_DIR`, always:

- Specs / designs → `DOCS_DIR/superpowers/specs/`
- Implementation plans → `DOCS_DIR/superpowers/plans/`

Only the base (`DOCS_DIR`) varies between projects — the `superpowers/specs` and `superpowers/plans` structure is constant everywhere.

## Filenames

- When a Linear ticket is associated, the filename **must** include the ticket ID so `/planit` and `/implementit` can find it.
- Standard form: `<TICKET_ID>-<short-slug>.md` — e.g. `NEU-257-rss-ingestion.md`. Lowercase, hyphenated slug.
- Locating a file = case-insensitive match on the filename containing the ticket ID.
- **Milestone specs** are not ticket-scoped. Name them `DOCS_DIR/superpowers/specs/<project-slug>-m<NN>-<milestone-slug>.md`
  (`<project-slug>` = hyphenated Linear project name; `<NN>` = zero-padded milestone order).
  Ticket plans reference their milestone spec via a `` **Milestone spec:** `` line with the relative path (see `/projectit`).

## Examples

| Project shape | `DOCS_DIR` | A plan for `NEU-257` |
|---|---|---|
| Umbrella `boone-gifts/` with `boone-gifts-backend/` + `boone-gifts-frontend/` | `boone-gifts/docs` | `boone-gifts/docs/superpowers/plans/NEU-257-checkout-flow.md` |
| Single repo `report-exporters/` | `report-exporters/.claude/docs` | `report-exporters/.claude/docs/superpowers/plans/PRD-520-pdf-goldens.md` |
| Any project with `specs_dir: docs` in CLAUDE.md | `<root>/docs` | `<root>/docs/superpowers/plans/NEU-257-….md` |

## Housekeeping

- Single-repo layout writes under `.claude/docs/`. Add `/.claude/docs/` to that repo's `.gitignore` if you don't want specs/plans committed.
- Umbrella layout writes to `<umbrella>/docs/`, which is usually not a git repo — nothing to ignore.

## Global CLAUDE.md snippet

Paste this into `~/.claude/CLAUDE.md` and **delete the old** "Store design specs and implementation plans in `~/claude/docs/<project-name>/`" line — that rule now conflicts with this one.

```markdown
## Specs & implementation plans

Specs and plans follow the spec-storage convention:
- If a project's CLAUDE.md sets `specs_dir`, use it as the docs base.
- Otherwise: umbrella projects (a non-git folder holding sibling code repos) → `<umbrella>/docs/`; standalone single repos → `<repo>/.claude/docs/` (gitignore it if you don't want it committed).
- Specs → `<docs>/superpowers/specs/`, plans → `<docs>/superpowers/plans/`.
- Filenames include the Linear ticket ID: `<TICKET-ID>-<slug>.md`.
```
