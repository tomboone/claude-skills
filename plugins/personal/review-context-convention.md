# Review context convention

`/reviewit`, `/addressit`, and `/mergeit` share one bundle of "ticket intent" so they review and respond from the same understanding. This doc is the single source of truth for what that bundle contains, where it lives, and how it is managed.

## The context bundle

**Path:** `<DOCS_DIR>/superpowers/context/<TICKET_ID>-review-context.md`

`DOCS_DIR` resolves exactly as in `/personal:implementit`:
1. `specs_dir` override in any loaded `CLAUDE.md`, else
2. umbrella layout → `<umbrella>/docs`, else
3. single-repo layout → `<repo-root>/.claude/docs`.

The `<TICKET_ID>` in the filename keeps bundles for different tickets from colliding when runs overlap.

## Contents (stable intent only)

Gather once, via the Linear MCP and the local spec/plan files, and write under clear headings:

- **Linear ticket:** id, title, description, current state.
- **Linear hierarchy & relations:** the ticket's project, its milestone, its parent and sub-issues, and its `blockedBy` / `blocks` / related issues (id + title + state for each).
- **Spec & plan:** the spec file and the plan file whose names contain `<TICKET_ID>`, searched in BOTH layouts (`<DOCS_DIR>/superpowers/{specs,plans}/` and the flat `<DOCS_DIR>/{specs,plans}/`). If the plan references a milestone spec (a line beginning `**Milestone spec:** `), include that too.

This is reference context — not the live diff.

## Live, never cached

Do NOT put the PR diff or the comment thread in the bundle — they change between rounds. `/reviewit` and `/addressit` always fetch those live (`gh pr diff`, `gh pr view --comments`, the inline-comments / reviews APIs).

## Lifecycle

- **Generate-or-load:** before reviewing/responding, check for the bundle file. If present, read it. If absent, gather the contents above, write it, then read it. Regenerate only when missing.
- **Gitignore (single-repo layouts only):** when `DOCS_DIR` is inside the code repo, the bundle must never be committed into the PR. Before writing it, ensure the repo's `.gitignore` contains an entry covering `.claude/docs/superpowers/context/` (add it if missing). Umbrella layouts keep `DOCS_DIR` outside the code repo, so this does not apply.
- **Delete on merge:** `/mergeit` deletes the bundle file after a successful merge.
