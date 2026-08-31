# claude-skills

This repo holds personal Claude Code plugins — slash commands, scripts, and skills used to run a Linear-ticket-driven development pipeline (plan → implement → ship → review → merge), plus two ways to chain that pipeline: `/personal:doit` (attended — one ticket, one session) and a headless orchestrator (`loop.py`) that drives it unattended across a wave.

## Language

**Project-shaping**:
The one-time, upfront pass over a whole Linear project — brainstorm the idea, break it into milestones/stories/tickets, batch-create them. Breadth over depth; deliberately does not try to resolve per-ticket implementation detail. Owned by `/personal:projectit`.
_Avoid_: planning (too broad — see Just-in-time ticket planning)

**Just-in-time ticket planning**:
The per-ticket depth pass that runs right before implementation, deferred until then so it can use ground truth unavailable at project-shaping time — the parent milestone's shared contracts, and the actual shipped spec/code of any already-merged blocking ticket. Skips straight through when an existing spec is already implementation-ready. Owned by `/personal:planit`.
_Avoid_: project-shaping

**Pre-ship review**:
A private, self-directed code review that runs inside `/implement`, before a PR exists. Acts on findings rather than merely reporting them, **scoped by severity**: hard violations of documented standards and genuine defects get fixed; the Fowler smell heuristics `/code-review` reports as judgement calls are listed, not refactored (see `docs/adr/0006-implementit-applies-review-findings-by-severity.md`).
_Avoid_: code review (ambiguous with post-ship review)

**Post-ship review**:
The public, durable review gate that runs against an open PR (`/personal:code-review`, invoked by `/personal:reviewit`). Produces a `## Code Review` PR comment and a `STATUS` sentinel. Read-only — findings get pushed back on or fixed by `/personal:addressit`, never auto-applied. **Manual only:** `loop.py` no longer runs it (see `docs/adr/0005-the-loop-drops-post-ship-review.md`), and `/personal:mergeit` honors its verdict when one exists but does not require one.
_Avoid_: code review (ambiguous with pre-ship review)

**Review context bundle**:
A cached, per-ticket file capturing the Linear ticket's intent (description, spec, plan) — the stable "why", as opposed to the live PR diff/comment thread which is always fetched fresh. Shared by `/personal:reviewit`, `/personal:addressit`, and `/personal:mergeit`. See `plugins/personal/review-context-convention.md`.

**Project-wide spec**:
A single written spec covering an entire project, produced by `/personal:projectit` Phase 1 and pointed to from the Linear project's description (`**Project spec:**`). Distinct from a per-ticket spec: `/personal:implementit` falls back to it directly when no per-ticket spec exists, trusting its coverage without `/personal:planit`'s sufficiency judgment (see `docs/adr/0004-implementit-falls-back-to-the-project-spec.md`).
_Avoid_: project spec, spec (ambiguous with per-ticket spec)

**Attended pipeline run**:
One ticket driven `implementit → shipit → mergeit` inline in a single interactive session, by `/personal:doit`. Contrasts with the loop, which drives the same state machine unattended across a wave with each step in its own `claude -p` process. The distinction that matters is **warm context vs. cold starts**, not autonomy alone — the phases of an attended run reuse state (branch, base, spec, diff) the earlier phases resolved. See `docs/adr/0007-doit-is-the-attended-single-ticket-pipeline.md`.
_Avoid_: loop (reserve for `loop.py`)

**Loop-ready**:
A Linear label `/personal:projectit` applies to a work ticket at creation (alongside `repo:<name>`), meaning `loop.py` may pick it up directly once its `blockedBy` blockers are `Done` — with no `/personal:planit` pass required first. Deselectable per-ticket at the Phase-3 gate for anything that should be planned or reviewed by hand first. It gates *unattended* pickup only: `/personal:doit` deliberately ignores it, since a human named the ticket.
