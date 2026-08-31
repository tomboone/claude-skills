---
description: Set up the work branch and implement a Linear ticket from its spec or plan
argument-hint: "{TICKET_ID} [--base <branch>]"
---

**CRITICAL: Follow every step in order. Do not skip or reorder steps. Do not jump ahead to
implementation.**

## Step 1 — Resolve the docs directory

Determine `DOCS_DIR` (must resolve the same on every machine):
1. **Override:** if any loaded `CLAUDE.md` defines `specs_dir`, `DOCS_DIR` = that value (resolve relative paths from the project root); skip to step 2.
2. Otherwise auto-resolve via `git rev-parse --show-toplevel` and the repo root's parent:
   - **Umbrella layout** — parent is *not* a git repo and holds sibling code repos (e.g. a backend and a frontend): `DOCS_DIR = <umbrella>/docs`.
   - **Single-repo layout** — the repo stands alone: `DOCS_DIR = <repo-root>/.claude/docs`.
   - If genuinely ambiguous, ask the user.

## Step 2 — Locate the plan file

Look for a plan file whose name contains `{TICKET_ID}` (case-insensitive) in **both** supported layouts:
- `DOCS_DIR/plans/` — the current spec-storage convention.
- `DOCS_DIR/superpowers/plans/` — the retired layout (older tickets only).

Work the sources below **in order** and stop at the first that resolves. `STATUS: NO_PLAN` is correct only after *all four* have been tried — it means "no design context exists anywhere," not "the filename lookup missed."

**1. A per-ticket file named for the ticket.**
- If exactly one match is found across both plan layouts, proceed with it.
- If multiple match, list them and ask the user which to use.
- If none match, check for a spec file containing `{TICKET_ID}` in `DOCS_DIR/specs/` **and** `DOCS_DIR/superpowers/specs/` — a spec without a separate plan is acceptable input (this is the common case now: `/personal:planit` authors a spec only, and this command implements straight from it).

**2. A pointer in the ticket's own description.** Fetch `{TICKET_ID}` via the Linear MCP and read **its own description** for a line naming a spec or plan — `/personal:projectit` writes one on every ticket it creates, in the form ``Spec: `docs/specs/NEU-638-*.md` §5`` (a `Plan:` line is equally valid). **Resolve globs**: `NEU-638-*.md` is a real pointer, not a literal filename — expand it against `DOCS_DIR` and use the match. A section marker (`§5`) narrows *what to read within the file*; it does not make the pointer unusable. This is the most direct signal available and is checked before any project-level lookup.

**3. The project-wide spec.** Read the description of **the Linear project the ticket belongs to** — the `project` / `projectId` field on the issue. This is *not* the ticket's `parentId`: a ticket commonly has both a parent **issue** (a user story, e.g. `NEU-727`) and a Linear **project**, and only the project carries the pointer. Look for a `**Project spec:**` line (written by `/personal:projectit` Phase 1); a `**Project plan:**` line is an equally valid fallback. If present, resolve and read that file — this is the common case for a ticket that never went through `/personal:planit`, relying instead on `/projectit`'s project-wide spec covering it well enough. Note: this fallback trusts the project spec's coverage of this specific ticket without the sufficiency judgment `/personal:planit` would normally make (see `docs/adr/0004-implementit-falls-back-to-the-project-spec.md`) — if implementation goes sideways because the spec doesn't actually cover this ticket, run `/personal:planit {TICKET_ID}` for a proper per-ticket pass instead.

**4. Nothing found.** Only if all three above come back empty, stop and tell the user to run `/personal:planit {TICKET_ID}` first. Say **which** sources you checked and what you searched for. Then, as the **very last line of your response**, emit `STATUS: NO_PLAN` so the headless loop orchestrator records this ticket as *not implemented* instead of marching on to `/personal:shipit`.

## Step 3 — Load the referenced spec (if the plan references one)

Read the chosen plan file. If it contains a line beginning `**Spec:** ` **or** `**Milestone spec:** `,
resolve that relative path (from the plan file's location) and read the referenced spec. Pass **both**
the plan and the spec to the implementation in Step 5 as design context — the plan is the per-ticket
slice, the spec is the design it realizes. (`**Spec:** ` points to a per-ticket spec from a newer
`/projectit` run; `**Milestone spec:** ` points to a shared milestone spec from an older run — both
are supported.)

If the plan has no such line (e.g. a `/planit`-authored plan), proceed with the plan alone — this
step is a no-op. Backwards-compatible.

## Step 4 — Create the work branch

Derive a branch name from the ticket ID and the plan/spec title: `feat/{TICKET_ID}-short-description` (or `fix/` if the ticket is a bug fix). Use the ticket ID exactly as given — don't assume a project prefix.

**Branch from the resolved base.** Determine `BASE`:
1. If invoked with `--base <branch>` (the loop threads this), use it.
2. Otherwise resolve locally: a `loop_base:` line in the repo `CLAUDE.md`; else the current
   checked-out branch when it is a real integration branch (not detached, not a `feat/*`/`fix/*`
   work branch); else the repo default branch (`git symbolic-ref --short refs/remotes/origin/HEAD`,
   stripped of `origin/`).

Sync the base first so each ticket starts from every prior ticket's merged state, then branch:
```bash
git fetch origin "$BASE"
git checkout -b feat/{TICKET_ID}-short-description "origin/$BASE"
```
(Use the `fix/` prefix for a bug-fix ticket, per the branch-name rule above.) Do **not** prompt for
the base in headless mode — the loop always supplies `--base`.

## Step 5 — Implement the plan

Implement the work **directly in this session**, from whatever design context Steps 2–3 resolved
(the per-ticket plan/spec, the milestone spec loaded in Step 3 if any, or the project-wide spec if
that's what Step 2 fell back to).

**Deliberately not delegated to `/implement` — do not "simplify" this back into one.** That skill
is installed from the `mattpocock/skills` marketplace (`~/.agents/.skill-lock.json`) and carries
`disable-model-invocation: true`. The Skill tool enforces that flag and refuses the call outright
(*"Skill implement cannot be used with Skill tool due to disable-model-invocation"*), so only a
human typing `/implement` can reach it. This is a property of that one skill, not of commands in
general — every `/personal:*` command here **is** Skill-invocable. Delegating to `/implement`
stalls the entire `implementit → shipit → mergeit` chain — headless under `loop.py` and attended
under `/personal:doit` alike — at phase 1, with a branch created and nothing implemented. Its body
was four lines of generic guidance, reproduced as the sequence below, so inlining costs nothing.

Execute in this order:

1. **Implement**, invoking `personal:tdd` at pre-agreed seams where applicable — failing test first
   wherever the repo's conventions call for it.
2. **Typecheck and test as you go**: typechecking regularly, individual test files regularly, and
   the full suite once at the end. Use the commands the repo's `CLAUDE.md` prescribes (many
   projects wrap these — don't invoke the underlying tool directly when a task runner is
   documented).
3. **Review and fix**: invoke `personal:code-review` over the work and act on its findings. That
   wrapper owns the severity scoping and the sub-agent model routing — follow it as written rather
   than restating the rules here.
4. **Commit** to the current branch.

Apply the findings **scoped by severity**, per the rules in `personal:code-review` — hard violations of a documented repo standard and genuine defects get fixed; the Fowler smell heuristics the Standards axis reports as judgement calls get listed in your summary, not refactored (`docs/adr/0006-implementit-applies-review-findings-by-severity.md`).

**This review pass is not optional and must not be skipped.** It is the only code review the loop performs: the loop runs `implementit → shipit → mergeit` and no longer runs a post-ship `/personal:reviewit` pass (see `docs/adr/0005-the-loop-drops-post-ship-review.md`). Run `/personal:reviewit {TICKET_ID}` by hand afterwards if a ticket warrants a second, judgment-preserving opinion on the open PR.

Do not invoke `/personal:shipit`. When the review-and-fix pass finishes, tell the user to clear context and run `/personal:shipit {TICKET_ID}` when ready.

(**Exception — running under `/personal:doit`:** that command composes this one with `/personal:shipit` and `/personal:mergeit` in a single session, and its Overrides replace this hand-off. Continue straight into its next phase instead of stopping.)

**Completion signal.** Only after the review-and-fix pass in step 3 has actually completed, emit — as the **very last line of your response** — `STATUS: IMPLEMENTED`. This is how the headless loop orchestrator (`loop.py`) confirms the plan was executed; if you stopped early for any reason (no plan, ambiguous input, an error), do **not** emit it.
