---
name: implementit
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

Work the sources below **in order** and stop at the first that resolves. `STATUS: NO_PLAN` is correct only after *all four* have been tried — it means "no design context exists anywhere," not "the filename lookup missed." The one exception is a ticket labelled `planit`, where source 3 is off limits (see below).

**1. A per-ticket file named for the ticket.**
- If exactly one match is found across both plan layouts, proceed with it.
- If multiple match, list them and ask the user which to use.
- If none match, check for a spec file containing `{TICKET_ID}` in `DOCS_DIR/specs/` **and** `DOCS_DIR/superpowers/specs/` — a spec without a separate plan is acceptable input (this is the common case now: `/planit` authors a spec only, and this command implements straight from it).

**2. A pointer in the ticket's own description.** Fetch `{TICKET_ID}` via the Linear MCP and read **its own description** for a line naming a spec or plan — `/projectit` writes one on every ticket it creates, in the form ``Spec: `docs/specs/NEU-638-*.md` §5`` (a `Plan:` line is equally valid). **Resolve globs**: `NEU-638-*.md` is a real pointer, not a literal filename — expand it against `DOCS_DIR` and use the match. A section marker (`§5`) narrows *what to read within the file*; it does not make the pointer unusable. This is the most direct signal available and is checked before any project-level lookup.

**3. The project-wide spec.** **Skip this source entirely if the ticket carries the `planit` label** (visible on the issue fetched in source 2) — `/projectit` applies it when it judged that the project-wide spec doesn't cover this ticket, and `/planit` removes it once the ticket has been checked or given its own spec (`docs/adr/0009-projectit-flags-spec-gaps-for-planit.md`). The same goes for a source-2 pointer that names the project-wide spec file rather than a per-ticket one. Go straight to source 4.

Otherwise, read the description of **the Linear project the ticket belongs to** — the `project` / `projectId` field on the issue. This is *not* the ticket's `parentId`: a ticket commonly has both a parent **issue** (a user story, e.g. `NEU-727`) and a Linear **project**, and only the project carries the pointer. Look for a `**Project spec:**` line (written by `/projectit` Phase 1); a `**Project plan:**` line is an equally valid fallback. If present, resolve and read that file — this is the common case for a ticket that never went through `/planit`, relying instead on `/projectit`'s project-wide spec covering it well enough. Note: this fallback trusts the project spec's coverage of this specific ticket without the sufficiency judgment `/planit` would normally make (see `docs/adr/0004-implementit-falls-back-to-the-project-spec.md`) — if implementation goes sideways because the spec doesn't actually cover this ticket, run `/planit {TICKET_ID}` for a proper per-ticket pass instead.

**4. Nothing found.** Only if all three above come back empty, stop and tell the user to run `/planit {TICKET_ID}` first. Say **which** sources you checked and what you searched for — and if the ticket is labelled `planit`, say that this is why the project-wide spec wasn't used. Then, as the **very last line of your response**, emit `STATUS: NO_PLAN` so `/doit` records this ticket as *not implemented* instead of marching on to `/shipit`.

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

**First, check for a no-code ticket.** If the design context resolved in Steps 2–3 calls for **no
change to this repository at all**, the ticket is entirely manual work: configuring something in an
external console, running an existing runbook or script, a one-off data fix. In that case don't
create a branch and don't implement anything. Say in one line why there is nothing to commit, then
**close the run** as `plugins/personal/manual-steps-convention.md` → "Closing a run" defines: post
the steps to the ticket as a checklist comment, show a one-line-per-step outline, and ask whether to
work through them now. Those steps *are* the ticket's implementation, so the list must be complete
and every step exact. If the user picks **now**, invoke `finishit` via the Skill tool. It runs
inline, with its Step 0 already answered, and its `STATUS:` sentinel (`FINISHED` / `PAUSED`) ends
the response. (**Exception — running under `/doit`:** skip all of this here. `/doit` closes the run
in its Step 4.) Otherwise, as the **very last line of your response**, emit `STATUS: NO_CODE`. If the ticket needs *any* repository
change — including writing a runbook or script that someone then executes — this exception doesn't
apply. Implement the repository part as normal; the execution becomes a manual step after merge.

Derive a branch name from the ticket ID and the plan/spec title: `feat/{TICKET_ID}-short-description` (or `fix/` if the ticket is a bug fix). Use the ticket ID exactly as given — don't assume a project prefix.

**Branch from the resolved base.** Determine `BASE`:
1. If invoked with `--base <branch>` (`/doit` threads this), use it.
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
the base — the resolution order above always ends in one.

## Step 5 — Implement the plan

Implement the work **directly in this session**, from whatever design context Steps 2–3 resolved
(the per-ticket plan/spec, the milestone spec loaded in Step 3 if any, or the project-wide spec if
that's what Step 2 fell back to).

**Deliberately not delegated to `/implement` — do not "simplify" this back into one.** That skill
is installed from the `mattpocock/skills` marketplace (`~/.agents/.skill-lock.json`) and carries
`disable-model-invocation: true`. The Skill tool enforces that flag and refuses the call outright
(*"Skill implement cannot be used with Skill tool due to disable-model-invocation"*), so only a
human typing `/implement` can reach it. This is a property of that one skill, not of commands in
general — every command in this plugin **is** Skill-invocable. Delegating to `/implement`
stalls the entire `implementit → shipit → mergeit` chain under `/doit` at phase 1, with a branch
created and nothing implemented. Its body
was four lines of generic guidance, reproduced as the sequence below, so inlining costs nothing.

Execute in this order:

1. **Implement**, invoking the `tdd` skill at pre-agreed seams where applicable — the seams the
   ticket's spec or plan already identified — writing the failing test first wherever the repo's
   conventions call for it. This is not a blanket instruction to test-drive every line of a ticket,
   and it does not override a repo whose `CLAUDE.md` prescribes something else.
2. **Typecheck and test as you go, narrowly**: typecheck regularly, and run the test files the
   change touches. Do **not** run the full suite by hand when the repo's pre-commit hook runs it:
   step 4's commit runs it once, and a hook failure is fixed and recommitted. Only when the hook
   is narrower than CI, or absent, run the full suite by hand, once, just before step 4, and say
   that the hook is narrower. Never start a test run while another is running. The rules are
   `claude-global.md` → *Running tests*. Use the commands the repo's `CLAUDE.md` prescribes (many
   projects wrap these — don't invoke the underlying tool directly when a task runner is
   documented).
3. **Review and fix**: invoke the `code-review` skill over the work and act on its findings. It
   reports along two axes — **Standards** (does the code follow this repo's documented coding
   standards?) and **Spec** (does the code match what the originating ticket asked for?) — in
   parallel sub-agents. It reports; it does not fix.

   **Review the uncommitted working tree; do not commit first.** Give both sub-agents the change
   as `git diff <BASE>` plus the untracked files `git status --short` lists. Committing before the
   review and again after its fixes runs the hook's full suite twice per ticket. Committing once,
   in step 4, runs it once.

   **Test cost is a Standards finding.** Add to the Standards sub-agent's brief: flag every new or
   changed test that rebuilds expensive state (a pipeline step, a migrated database, a large file)
   per test when it only reads that state, or that re-reads fixture files inside a loop. Since the
   hook runs the suite on every commit, this is a hard finding, not a smell: fix it in this ticket.

   **Sub-agent model routing.** Run the **Standards** sub-agent on **Haiku**: it is checklist
   matching against documented rules and a fixed smell list — rubric work, not open-ended
   judgement. Keep the **Spec** sub-agent on the **session's own model**, because deciding whether
   an implementation honours the intent of a spec is exactly the judgement Standards does not
   require. This matters most here, where the session is typically on Opus and this pass is
   the pipeline's only code review (`docs/adr/0005-the-loop-drops-post-ship-review.md`) — without the
   routing, the Standards axis is Opus-priced for checklist work.
4. **Commit** to the current branch, once, after the review's fixes. The pre-commit hook runs the
   suite here. If it fails, fix the cause and commit again; never `--no-verify`. Then read the
   slowest-tests list the hook prints, where the repo has one (`--durations`), and fix any new
   test near its top before going on.

Apply the findings **scoped by severity**:

- **Apply** hard violations of a documented repo standard, and genuine defects.
- **Do not refactor** for the Fowler smell heuristics the Standards axis also reports (Mysterious
  Name, Duplicated Code, Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, Shotgun
  Surgery, Divergent Change, Speculative Generality, Message Chains, Middle Man, Refused Bequest) —
  the skill explicitly marks these as *"always a judgement call, never a hard violation."* Act on one
  only when it is directly implicated in a real defect; otherwise list it in your summary and leave
  the code alone.

**Why.** The skill is a read-only reporting tool — no `--fix` flag, no severity field, no confidence
threshold — because it was written for a human to read and exercise judgement over. Blind-applying
everything means applying a dozen judgement-call refactorings (rename, extract a type, replace with
polymorphism, split the module) that the skill deliberately declines to rank. That is both a quality
risk and the pipeline's single largest token cost — see
`docs/adr/0006-implementit-applies-review-findings-by-severity.md`.

**This review pass is not optional and must not be skipped.** It is the only code review the pipeline performs: `/doit` runs `implementit → shipit → mergeit` and does not run a post-ship `/reviewit` pass (see `docs/adr/0005-the-loop-drops-post-ship-review.md`). Run `/reviewit {TICKET_ID}` by hand afterwards if a ticket warrants a second, judgment-preserving opinion on the open PR.

Do not invoke `/shipit`. When the review-and-fix pass finishes, tell the user to clear context and run `/shipit {TICKET_ID}` when ready.

(**Exception — running under `/doit`:** that command composes this one with `/shipit` and `/mergeit` in a single session, and its Overrides replace this hand-off. Continue straight into its next phase instead of stopping.)

**Completion signal.** Only after the review-and-fix pass in step 3 has actually completed, emit — as the **very last line of your response** — `STATUS: IMPLEMENTED`. This is how `/doit` confirms the plan was executed before moving on to `/shipit`; if you stopped early for any reason (no plan, ambiguous input, an error), do **not** emit it.
