# claude-skills

Personal Claude Code configuration repo — see `README.md` at the repo root for the full picture
(what the `personal` plugin does, the command pipeline, `loop.py`, on-disk conventions).

## How this repo tracks its own work

Unlike the repos the `personal` plugin operates *on*, this repo does not use Linear tickets or
GitHub Issues for its own development — there are none open, and none in its history. Work is
tracked via directly-authored spec/plan docs and PRs. Don't run `/projectit`/`/planit` against this
repo itself, and don't run `/setup-matt-pocock-skills` here — the issue-tracker/triage-label
scaffolding it writes has nothing to attach to.

## Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root (no `CONTEXT-MAP.md`). Used directly
by `/grilling` + `/domain-modeling` when planning changes to this repo.

## Specs & plans for this repo's own work

No `specs_dir` override is set — the single-repo auto-resolve default already matches actual
layout: `.claude/docs/{specs,plans}/` (current convention; new docs go here) and
`.claude/docs/superpowers/{specs,plans}/` (retired layout, older docs only). Filenames here are
dated slugs (e.g. `2026-06-28-projectit-reduction.md`), not ticket IDs, since there's no ticket ID
to key on.
