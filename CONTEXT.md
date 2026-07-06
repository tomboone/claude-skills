# claude-skills

This repo holds personal Claude Code plugins — slash commands, scripts, and skills used to run a Linear-ticket-driven development pipeline (plan → implement → ship → review → merge), plus a headless orchestrator (`loop.py`) that drives that pipeline unattended.

## Language

**Project-shaping**:
The one-time, upfront pass over a whole Linear project — brainstorm the idea, break it into milestones/stories/tickets, batch-create them. Breadth over depth; deliberately does not try to resolve per-ticket implementation detail. Owned by `/personal:projectit`.
_Avoid_: planning (too broad — see Just-in-time ticket planning)

**Just-in-time ticket planning**:
The per-ticket depth pass that runs right before implementation, deferred until then so it can use ground truth unavailable at project-shaping time — the parent milestone's shared contracts, and the actual shipped spec/code of any already-merged blocking ticket. Skips straight through when an existing spec is already implementation-ready. Owned by `/personal:planit`.
_Avoid_: project-shaping

**Pre-ship review**:
A private, self-directed code review that runs inside `/implement`, before a PR exists. Auto-fixes what it finds (`/code-review --fix`) rather than reporting — there's no adversarial party yet to push back against, so blind auto-apply is safe.
_Avoid_: code review (ambiguous with post-ship review)

**Post-ship review**:
The public, durable review gate that runs against an open PR (`/review`, invoked by `/personal:reviewit`). Produces a `## Code Review` PR comment and a `STATUS` sentinel that `loop.py`'s state machine and `/personal:mergeit` depend on. Read-only — findings get pushed back on or fixed by `/personal:addressit`, never auto-applied.
_Avoid_: code review (ambiguous with pre-ship review)

**Review context bundle**:
A cached, per-ticket file capturing the Linear ticket's intent (description, spec, plan) — the stable "why", as opposed to the live PR diff/comment thread which is always fetched fresh. Shared by `/personal:reviewit`, `/personal:addressit`, and `/personal:mergeit`. See `plugins/personal/review-context-convention.md`.
