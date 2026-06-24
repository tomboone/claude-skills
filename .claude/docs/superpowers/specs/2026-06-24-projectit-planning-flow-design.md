# `/projectit` — Project Planning Flow (Design Spec)

- **Date:** 2026-06-24
- **Status:** Approved design (brainstorming output)
- **Repo:** `claude-skills` (the `personal` plugin)
- **Linear ticket:** none (exploratory personal work)

## Summary

`/projectit` is a new interactive command in the `personal` plugin that turns a high-level
project idea into a fully-populated Linear project — project description, milestones, user
stories, and work tickets — **plus** an on-disk design spec per milestone and an
implementation plan per work ticket. The plans are pitched so that the (separate)
implementation loop can execute each ticket on Sonnet via `/implementit` **without running
`/planit` per ticket**. In effect, `/projectit` front-loads all per-ticket planning for an
entire project in one gated, mostly-automated pass.

## Context & relationship to existing commands

The `personal` plugin already has a per-ticket workflow: `/planit` → `/implementit` →
`/shipit` → `/reviewit` → `/mergeit`. `/projectit` sits **upstream** of all of these: it is
the producer that scaffolds an entire project's worth of work and planning artifacts, which a
future **implementation loop** (separate spec) consumes ticket-by-ticket.

This spec is the **producer** half of a larger pipeline:

1. **Planning flow (this spec)** — `/projectit` produces a populated Linear project + on-disk
   specs/plans, with every work ticket marked ready for the loop.
2. **Implementation loop (separate, future spec)** — pulls ready work tickets and runs
   `/implementit → /shipit → /reviewit → (gated) /mergeit` per ticket.
3. **The contract between them** — defined here (see *The contract*), since `/projectit` must
   produce exactly what the loop consumes.

### Linear hierarchy model

> **Initiative** (≈ one app) ⊃ **Project** ⊃ **Milestone** *(gets a spec)* ; and
> **Project** ⊃ **User story** *(an issue, tied to a milestone)* ⊃ **Work ticket**
> *(a sub-issue, gets a plan)*.

## Scope

**In scope:** Phases 0–5 of `/projectit`; the producer→loop contract; one small change to
`/implementit` (load the milestone spec a plan references).

**Out of scope (separate specs):** the implementation loop / orchestrator itself; the
`/reviewit` machine-readable status signal; `claude -p` headless tooling. This spec only
*defines* the contract those will consume.

## Key decisions (from brainstorming)

1. **Brainstorm the planning flow first**; the implementation loop and `/reviewit` changes are
   separate specs.
2. **Gated by layer** — the human collaborates/approves at the structural layers (project
   description → milestones → stories + tickets); specs and plans are then generated in bulk
   for review.
3. **Plans are high-level & resilient** — pre-generated as intent + acceptance + approach,
   deliberately light on exact file/function specifics so they survive code that doesn't exist
   yet. `/implementit` does the concrete, code-aware detailing at execution time. This
   preserves "no `/planit` in the loop."
4. **Linear target is inferred from the repo, then confirmed** — the repo maps to its app →
   initiative; an existing matching project is reused, else a new one is created.
5. **Architecture: interactive structure command + in-session subagents** — the structural top
   is an interactive gated dialogue; the bulk spec/plan generation dispatches subagents
   (parallel, fresh context, batched) within the same session. No headless `claude -p`
   plumbing, since this phase is attended.
6. **Commit the generated docs** (recommended) — keep `.claude/docs` tracked, for durability,
   cross-machine use, and GitHub URLs for Linear link attachments.
7. **Opus throughout** the planning flow — quality matters most here because execution runs on
   Sonnet.

## The command: `/projectit`

### Invocation

```
/projectit                      # asks for the idea
/projectit "add a digest-email system"
```

Run from inside the **target app's repo** — the repo anchors the Linear initiative.

### Phase sequence (■ = human gate)

| Phase | What happens | Gate |
|---|---|---|
| **0. Resolve Linear target** | Infer initiative from repo; search it for a matching project; **decide** *reuse X* or *create new* (no write). | ■ confirm initiative + project |
| **1. Project description** | Brainstorm purpose/scope/goals into a thorough description; **hold it**. | ■ approve description |
| **2. Milestones** | Propose milestones (name + goal + order); **hold them**. | ■ approve milestone list |
| **3. Stories + tickets** | Per milestone, propose user stories (issues) with acceptance criteria and work tickets (sub-issues); on approval, **create the whole hierarchy in one batch** (project+description → milestones → stories → tickets → blockedBy). | ■ approve breakdown |
| **4. Bulk doc-gen** | Subagents write one spec per milestone, one resilient plan per ticket; docs land on disk. | ■ bulk-review the docs |
| **5. Link + mark ready** | Write plan/spec links into Linear; apply the `loop-ready` label. | — |

Nothing is created in Linear until **after** the Phase-3 gate — phases 0–3 propose, you
approve, then it writes. This contains the blast radius.

## Phase detail

### Phase 0 — Resolve the Linear target

- **Initiative (≈ the app):**
  1. Read the repo's `CLAUDE.md` for an explicit `linear_initiative:` / `linear_team:` hint (a
     new convention, sibling to the existing `specs_dir`).
  2. If absent, `list_initiatives(query=<app name>, includeProjects=true)` and propose the best
     name match.
  3. Confirm with the user. On confirm, offer to **write the hint back into the repo's
     `CLAUDE.md`** so it is automatic next time.
- **Team:** required by `save_issue` and `save_project`. Resolve from the `linear_team` hint,
  else `list_teams` + ask.
- **Project (reuse vs create):** the initiative's projects come back with the `list_initiatives`
  call. If one plausibly matches the idea → propose *reuse*; else *create new*. On confirm,
  **record the decision only — do not write yet** (reuse → keep the existing id; create → hold the
  new project name). The project is created in the Phase-3 batch.

### Phase 1 — Project description

Invoke `superpowers:brainstorming` to develop purpose / scope / goals into a thorough project
description. Gate: user approves. **Hold the description** for the Phase-3 batch — do not write yet.

### Phase 2 — Milestones

Propose milestones; gate: user approves the list. **Hold the milestones** for the Phase-3 batch —
do not write yet.

### Phase 3 — User stories & work tickets

This phase proposes the stories/tickets and, **after its gate, runs the single creation batch for the
whole hierarchy** — first the held project (with its Phase-1 description) and the held milestones, then:

- **User story** → `save_issue(title, team, project, milestone, description:<story + acceptance
  criteria>, labels:["user-story"])` → returns e.g. `PROJ-101`.
- **Work ticket** → `save_issue(title, team, project, milestone, parentId:<story-id>,
  description:<intent>)` — a sub-issue of the story.
- **Dependencies** → where ticket B builds on ticket A, set `B blockedBy A`. This gives the
  loop a topological execution order and lets each ticket's resilient plan name its
  prerequisites by ID rather than guessing at not-yet-existing code.
- **Granularity rule:** one work ticket = one `/implementit` run = one PR. Stories group related
  tickets and hold user-facing acceptance criteria; tickets are the implementable slices. The
  flow suggests the breakdown; the user adjusts at the gate.

### Phase 4 — Bulk doc generation (subagents)

Two ordered rounds (specs must exist before plans reference them):

1. **Round 1 — milestone specs:** one subagent per milestone, in parallel. Each is handed the
   project description + that milestone's goal + its stories/tickets + the repo location (it
   explores actual code/conventions to ground the design) + the output convention. Writes its
   spec, returns path + summary.
2. **Round 2 — ticket plans:** after specs land, one subagent per work ticket, in parallel. Each
   gets its milestone spec + story context + ticket intent + its `blockedBy` prerequisites'
   docs + repo location. Writes the resilient plan.

- **Batched** (N at a time, not all at once) per the `dispatching-parallel-agents` patterns, to
  respect limits and keep output reviewable.
- **Model: Opus** for both rounds.
- **Bulk review gate:** present a summary table (milestone → spec path; ticket → plan path,
  grouped by story). The user reviews on disk; any doc that is off → regen just that one
  subagent with feedback appended. On approval → Phase 5.

### Phase 5 — Link & mark ready

- Write into each work ticket's Linear description: the relative plan path + a link to its
  milestone spec. Milestone descriptions link their spec. If docs are committed/pushed, also add
  a `links` attachment to the GitHub URL.
- Apply the `loop-ready` label to each reviewed work ticket.
- Ensure the `user-story` and `loop-ready` labels exist (`create_issue_label` if missing).
- Never set issue **status** — the GitHub↔Linear connector owns status transitions.

## Document model (spec vs plan)

| | **Milestone spec** → `specs/` | **Work-ticket plan** → `plans/` |
|---|---|---|
| Scope | One per milestone; shared by all its tickets | One per work ticket |
| Holds | Purpose/scope of the phase; architecture & approach (components, data models, interfaces it introduces); cross-cutting decisions & constraints; milestone-level acceptance; out-of-scope | What this ticket builds; its acceptance criteria; which part of the milestone design it realizes; prerequisite tickets by ID (from `blockedBy`) and what they provide; testing intent |
| Detail | Stable, design-level | Intent-level, light on exact signatures (resilient) |

The milestone spec carries the milestone-wide design once, so the per-ticket plans don't each
re-derive architecture — they describe only their slice + dependencies. `/implementit` reads
**both** the ticket's plan and the milestone spec it references.

## On-disk layout & naming

Extends the existing spec-and-plan storage convention (no break):

- **Ticket plans:** `plans/<TICKET-ID>-<slug>.md` — unchanged, so `/implementit` finds them by
  ticket ID exactly as today.
- **Milestone specs:** `specs/<project-slug>-m<NN>-<milestone-slug>.md` — the `NN` preserves
  order; the plan references this path.
- `DOCS_DIR` resolves via the same umbrella-vs-single-repo logic the existing commands use.

## The contract (planning output → implementation loop input)

Hard requirements the loop depends on:

- **Ready marker:** work tickets carry the `loop-ready` label (applied Phase 5). The loop
  selects sub-issues with it.
- **Plan discovery:** by ticket ID on disk — `plans/<TICKET-ID>-<slug>.md`. The loop reads from
  disk, not from Linear; no Linear link is required for it to function.
- **Spec discovery:** the plan references its milestone spec by path; `/implementit` follows it.
- **Execution order:** the loop honors `blockedBy` — a ticket runs only once its blockers are
  merged/Done. This is what makes resilient plans safe: prerequisites are built before the
  ticket that assumes them.
- **Labels:** `user-story` and `loop-ready` must exist.

Human-convenience layer (not load-bearing): ticket descriptions carry the relative plan path +
milestone-spec link.

## Idempotency & error handling

- **Gates contain blast radius** — no Linear writes before the Phase-3 gate.
- **Idempotent re-run is the recovery mechanism** — Linear holds the created hierarchy, disk
  holds the docs; re-running `/projectit` reads current state, fills gaps, updates by match
  (milestones by name, issues by title within the project), and never duplicates. A crash or
  partial failure is fixed by re-running. No separate checkpoint store.
- Subagent failure or a rejected doc → regen that one item, keyed by ticket/milestone.

## Models

Opus for the entire planning flow (structure brainstorm + both doc-gen rounds). Execution
(`/implementit`) runs on Sonnet later, which is why planning quality is front-loaded here.

## Testing

This is command + subagent-prompt tooling, not unit-testable code.

- **Dry-run mode** — produce the proposed hierarchy + docs to disk *without* writing to Linear,
  to validate structure and doc quality first.
- **End-to-end** — run on a small sandbox project, then hand one `loop-ready` ticket to
  `/implementit` to confirm the resilient plan + milestone spec are genuinely sufficient for
  Sonnet. That run is the contract test.

## Required change to `/implementit`

`/implementit` currently locates a plan by ticket ID. It gains one step: after loading the
plan, also load the **milestone spec** the plan references (by the path recorded in the plan),
and pass both to the implementation. Backwards-compatible — a plan with no milestone-spec
reference behaves as today.

## Open items / deferred

- The `linear_initiative` / `linear_team` CLAUDE.md hint convention should be documented
  alongside the existing `specs_dir` convention.
- Whether the Phase-5 commit of docs is a plain commit or a PR is left to implementation; the
  recommendation is to commit (keep `.claude/docs` tracked).
- The implementation loop, the `/reviewit` status signal, and `claude -p` tooling are their own
  specs.

## Appendix: Linear MCP fields used

- `list_initiatives(query, includeProjects)` — find initiative + its projects.
- `save_project(name, addTeams, addInitiatives, description)` — create/reuse project under an
  initiative + team.
- `save_milestone(project, name, description)` — project milestones.
- `save_issue(title, team, project, milestone, parentId, description, labels, blockedBy)` —
  stories (no parent) and work tickets (parented sub-issues) + dependency relations.
- `create_issue_label` — ensure `user-story` / `loop-ready` exist.
