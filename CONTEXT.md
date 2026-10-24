# claude-skills

This repo holds personal Claude Code plugins — slash commands, scripts, and skills used to run a Linear-ticket-driven development pipeline (plan → implement → ship → review → merge), plus `/doit`, which chains that pipeline for one ticket in one attended session.

## Language

**Project-shaping**:
The one-time, upfront pass over a whole Linear project — brainstorm the idea, break it into milestones/stories/tickets, batch-create them. Breadth over depth; deliberately does not try to resolve per-ticket implementation detail. Owned by `/projectit`.
_Avoid_: planning (too broad — see Just-in-time ticket planning)

**Just-in-time ticket planning**:
The per-ticket depth pass that runs right before implementation, deferred until then so it can use ground truth unavailable at project-shaping time — the parent milestone's shared contracts, and the actual shipped spec/code of any already-merged blocking ticket. Skips straight through when an existing spec is already implementation-ready. Owned by `/planit`.
_Avoid_: project-shaping

**Pre-ship review**:
A private, self-directed code review that runs inside `/implement`, before a PR exists. Acts on findings rather than merely reporting them, **scoped by severity**: hard violations of documented standards and genuine defects get fixed; the Fowler smell heuristics `/code-review` reports as judgement calls are listed, not refactored (see `docs/adr/0006-implementit-applies-review-findings-by-severity.md`).
_Avoid_: code review (ambiguous with post-ship review)

**Post-ship review**:
The public, durable review gate that runs against an open PR (`/code-review`, invoked by `/reviewit`). Produces a `## Code Review` PR comment and a `STATUS` sentinel. Read-only — findings get pushed back on or fixed by `/addressit`, never auto-applied. **Manual only:** no pipeline command runs it (see `docs/adr/0005-the-loop-drops-post-ship-review.md`), and `/mergeit` honors its verdict when one exists but does not require one.
_Avoid_: code review (ambiguous with pre-ship review)

**Review context bundle**:
A cached, per-ticket file capturing the Linear ticket's intent (description, spec, plan) — the stable "why", as opposed to the live PR diff/comment thread which is always fetched fresh. Shared by `/reviewit`, `/addressit`, and `/mergeit`. See `plugins/personal/review-context-convention.md`.

**Project-wide spec**:
A single written spec covering an entire project, produced by `/projectit` Phase 1 and pointed to from the Linear project's description (`**Project spec:**`). Distinct from a per-ticket spec: `/implementit` falls back to it directly when no per-ticket spec exists, trusting its coverage without `/planit`'s sufficiency judgment (see `docs/adr/0004-implementit-falls-back-to-the-project-spec.md`).
_Avoid_: project spec, spec (ambiguous with per-ticket spec)

**Attended pipeline run**:
One ticket driven `implementit → shipit → mergeit` inline in a single interactive session, by `/doit`. Contrasts with the retired `loop.py`, which drove the same state machine unattended with each step in its own `claude -p` process. The phases of an attended run reuse state (branch, base, spec, diff) the earlier phases resolved. See `docs/adr/0007-doit-is-the-attended-single-ticket-pipeline.md` and `docs/adr/0008-retire-the-headless-loop.md`.
_Avoid_: loop (the retired headless orchestrator)

**Manual-steps walkthrough**:
The closing section of a `/mergeit`, `/doit`, or no-code `/implementit` report. It lists everything that must still happen outside the merged code for the ticket to be finished — deploys, migrations, secrets, external-service setup, executing a delivered runbook — each with exact commands (local or deployed) or click-by-click UI steps, plus a check that it worked. It always appears, and always ends with the user moving the ticket to **Done** by hand — merging only takes it to **Merged** (see `docs/adr/0010-done-means-the-manual-steps-are-finished.md`). For a **no-code ticket** (one needing no repository change, signalled by `STATUS: NO_CODE`), it *is* the implementation. See `plugins/personal/manual-steps-convention.md`.
_Avoid_: follow-ups, next steps (too vague — the point is that they're exact)

**Planit label**:
A Linear label `/projectit` applies to a work ticket at creation when its Phase-3 coverage check finds the project-wide spec doesn't cover that ticket to `/planit`'s sufficiency standard. While it's on, `/implementit` (and so `/doit`) won't fall back to the project-wide spec and stops with `NO_PLAN`; `/planit` removes it once it has judged the ticket implementation-ready or written its per-ticket spec. It flags coverage gaps visible at project-shaping time only — not later drift from how a blocker actually shipped. See `docs/adr/0009-projectit-flags-spec-gaps-for-planit.md`.
_Avoid_: needs-planning, loop-ready (retired)
