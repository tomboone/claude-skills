# Scaffold a whole Linear project (milestones, stories, tickets) and pre-generate milestone specs + ticket plans.
# Usage: /personal:projectit [--dry-run] ["high-level project idea"]

## Conventions used by this command

- Resolve `DOCS_DIR` exactly as `/personal:planit` does (specs_dir override; else umbrella `<umbrella>/docs` or single-repo `<repo>/.claude/docs`).
- **Dry-run:** if `--dry-run` is passed, make NO `save_*`/`create_*` Linear calls. Instead print each Linear write you would make, and write any generated docs under `DOCS_DIR/superpowers/.dryrun/` rather than `specs/`/`plans/`.
- **Never** set issue `status` — the GitHub↔Linear connector owns it.
- Create nothing in Linear until after the Phase 3 gate.

## Phase 0 — Resolve the Linear target  ■ gate

1. Determine the idea: use the quoted argument, else ask the user for a one-line project idea.
2. **Initiative:** read the repo's `CLAUDE.md` for `linear_initiative`. If present, use it. Else call
   `list_initiatives(query=<app/repo name>, includeProjects=true)` and propose the best name match.
3. **Team:** read `linear_team` from `CLAUDE.md`; else `list_teams` and propose/ask.
4. **Project:** from the initiative's returned projects, if one plausibly matches the idea, propose
   "reuse <project>"; otherwise propose "create new: <name>".
5. **■ Gate:** show the resolved initiative, team, and reuse/create decision; wait for confirmation.
6. On confirm: if creating, `save_project(name=<name>, addTeams=[<team>], addInitiatives=[<initiative>])`
   (skipped in dry-run — print instead). Record `PROJECT`. Offer to write `linear_initiative`/`linear_team`
   back into the repo's `CLAUDE.md` if they were not already set.
