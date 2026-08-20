# Global Preferences

- **Git**: Repo-modifying ops (add, commit, push, branch, checkout -b, merge, rebase, reset) are permitted per `~/.claude/settings.json`. Use conventional-commits format with the Linear ticket ID as a parenthetical at the end of the subject line: `<type>(<scope>): <description> (<LINEAR-ID>)` — e.g. `feat: add agent_http_client helper (PRD-520)`. Apply the same format to PR titles. If no Linear ticket maps to the change, drop the parenthetical (don't invent one). **Never include a `Co-Authored-By:` trailer** — `includeCoAuthoredBy: false` is set in settings.json so Claude doesn't show up as a GitHub contributor. The `🤖 Generated with Claude Code` footer is wanted on PR bodies and Linear content, but **not** on commit messages — see [Claude Code attribution footer](#claude-code-attribution-footer). Destructive ops (`reset --hard`, `push --force`, branch deletes) still require explicit confirmation. All `gh` operations are now permitted (PR merge/close, issue close, repo create/delete, and `gh api` writes); the only command hard-blocked in `~/.claude/settings.json` is `sudo`. Still confirm before genuinely irreversible or outward-facing actions (deleting repos/releases, closing PRs/issues you didn't open).
- **Linear ticket statuses**: The GitHub↔Linear connector automatically moves tickets through their statuses (e.g., to In Progress / In Review / Done) based on branch and PR activity. Never manually flip a ticket's status or offer to — it's handled for you.
- **Project Context**: Always run the `localdev:load-project-context` skill at the start of a conversation.

## Python Coding Style

- **Type hints**: Use modern `X | None` and `X | Y` syntax (not `Optional[X]` / `Union[X, Y]`).
- **No `from __future__ import annotations`** — prefer consistency without it.
- **Linting**: ruff for PEP 8 compliance. Use `x as x` re-export pattern in `__init__.py` to avoid F401 errors.
- **IDE**: PyCharm — be mindful of unresolved attribute warnings when suggesting code.

## Claude Code attribution footer

Always append this footer to GitHub PR descriptions, GitHub PR comments (including code-review comments), Linear ticket descriptions, and Linear ticket comments:

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Do **not** add this footer to git commit messages, and never add a `Co-Authored-By` trailer.

## Project type

A project is a **work (ingest) project** if its repo root is inside `~/ingest/`; any project elsewhere is a **personal project**.

- Work/ingest projects: use the `localdev` plugin's generators (`localdev:commit-msg`, `localdev:pr-desc`) for commit messages and PR descriptions.
- Personal projects: commit-message and PR-description generation is handled inline by `/shipit` (no separate skill).

## Specs & implementation plans

Specs and plans follow the spec-storage convention:

- If a project's CLAUDE.md sets `specs_dir`, use it as the docs base.
- Otherwise: umbrella projects (a non-git folder holding sibling code repos) → `<umbrella>/docs/`; standalone single repos → `<repo>/.claude/docs/` (gitignore it if you don't want it committed).
- Specs → `<docs>/superpowers/specs/`, plans → `<docs>/superpowers/plans/`.
- Filenames include the Linear ticket ID: `<TICKET-ID>-<slug>.md`.
