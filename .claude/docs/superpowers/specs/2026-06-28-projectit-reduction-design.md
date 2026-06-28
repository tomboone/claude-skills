# Reduce `/projectit` to project-shaping; move planning just-in-time

**Status:** Approved (design)
**Date:** 2026-06-28
**Affects:** `plugins/personal/commands/projectit.md`, `plugins/personal/commands/planit.md`
**Reverses:** the Phase 4 bulk doc-generation added in `2026-06-28-projectit-per-ticket-specs-design.md`

## Motivation

`/projectit` currently scaffolds a Linear project (Phases 0–3) **and** bulk-generates a
self-contained spec + plan for every ticket up front via Opus subagents (Phase 4), then wires
those plans into Linear ticket descriptions and applies loop-selector labels (Phase 5).

Two shifts make that up-front bulk planning the wrong default:

1. **Native iOS push notifications** (enabled this session via `agentPushNotifEnabled` /
   `inputNeededNotifEnabled` + Remote Control) remove the need to run work unattended through the
   headless loop. Work returns to interactive, subscription-billed sessions, where planning each
   ticket **just-in-time** with `/planit` is natural.
2. **Just-in-time plans are better, not just cheaper.** A plan written immediately before
   implementing a ticket is less stale and incorporates what earlier tickets actually shipped.
   Bulk plans written weeks ahead bake in assumptions that earlier work invalidates.

So `/projectit` should shape the project (brainstorm → milestones → stories → tickets in Linear)
and stop there. Per-ticket spec/plan authoring moves to `/planit`, run in the target repo when the
ticket is picked up.

## Cross-ticket coherence: A + a dash of B

Dropping Phase 4 loses its one non-planning function: a cross-ticket design pass that made siblings
(e.g. a backend ticket and the frontend ticket consuming it) agree on shared contracts. Coherence is
preserved by two cheap mechanisms instead of regenerated for all tickets:

- **A — dependency order (primary).** Tickets are worked in `blockedBy` order. `/planit` reads a
  ticket's already-merged dependencies' **actual shipped spec/code** as ground truth when planning.
- **B — up-front contracts in the milestone (the dash).** The genuinely up-front decisions both
  sides must agree on *before either is built* are captured in the **milestone description** at
  cut-time. `/planit` reads the parent milestone and feeds those contracts into planning.

No project- or milestone-level doc files; no contract inlined into N specs. Contracts live in Linear
(milestone descriptions) and travel with the project.

## `/projectit` — reduced design

Unchanged framing: all Linear writes are deferred to a single batch after the Phase 3 gate, and the
batch is idempotent (look up by id/name/title; update matches rather than duplicate).

**Removed wholesale:** Phase 4 (bulk doc generation, subagents, cross-ticket design pass written to
disk), Phase 5 (label bootstrapping, plan/spec wiring into ticket descriptions, GitHub plan-URL
attachments). With them go the `docs_dir_for(repo)` resolution, per-repo `specs_dir` pinning, repo
local-path discovery, and **all** labels (`loop-ready`, `repo:<name>`, `user-story`).

### Phase 0 — Resolve the Linear target  ■ gate

Initiative, team, project (reuse-or-create), as today. Repo resolution shrinks to names only: **if**
the project spans multiple repos, resolve the set of repo **names** (from a `linear_repos:` list in
`CLAUDE.md`, else ask) so tickets can carry a target-repo line. No local paths, no `specs_dir`
pinning, no `docs_dir_for`. Single-repo projects skip repo handling entirely. Gate on the resolved
initiative / team / project decision. Still offer to write `linear_initiative` / `linear_team` back
to `CLAUDE.md` if unset.

### Phase 1 — Project description  ■ gate

`superpowers:brainstorming` framed on the idea + initiative context → project description. Held for
the batch. Unchanged.

### Phase 2 — Milestones + shared contracts  ■ gate

Propose milestones as `{name, goal, order}`. For each milestone, also capture the cross-cutting
decisions siblings must agree on up front (API shape, shared data model, naming) — folded into the
**milestone description** (this is mechanism B). User edits/approves. Held for the batch.

### Phase 3 — User stories & work tickets  ■ gate

Stories, and under each, work tickets. Granularity: one work ticket = one `/implementit` run = one
PR; stories hold user-facing acceptance criteria. Note inter-ticket `blockedBy` dependencies.

**Target repo (multi-repo projects only):** assign each work ticket one repo name from Phase 0 and
record it as a plain `**Target repo:** <name>` line in the ticket description — informational, so the
user knows where to run `/planit`. Never silently guess; ask when ambiguous. No `repo:` label.

**■ Gate** — the single gate after which all Linear writes happen. On approval, batch-create
top-down (dry-run prints each call instead):

1. **Project** — create or update with the held Phase-1 description.
2. **Milestones** — `save_milestone(project, name, description=<goal + shared contracts>)`.
3. **Stories** — `save_issue(..., description=<story + acceptance criteria>)`. **No label.**
4. **Tickets** — `save_issue(..., description=<intent [+ "**Target repo:** <name>" line]>)`.
5. **Dependencies** — for each "B builds on A", `save_issue(id=B, blockedBy=[A])`.

### Done — summary

Print project URL + counts (milestones / stories / work tickets). Next-step line:

> Next: run `/personal:planit {TICKET}` in the ticket's repo to plan it just-in-time, then
> `/personal:implementit {TICKET}`.

## `/planit` — touch-ups for A + B

Plan storage is already `/implementit`-compatible (`DOCS_DIR/superpowers/{specs,plans}/<TICKET_ID>-<slug>.md`,
found by ticket id) — **no naming change.** Two additions to Step 2 (ticket fetch):

1. **Milestone contracts (B):** fetch the ticket's parent **milestone** and surface its description's
   shared-contracts section; feed it into the `superpowers:brainstorming` / `writing-plans` handoff so
   the plan honors the up-front contracts.
2. **Shipped dependencies as ground truth (A):** for `blockedBy` tickets already merged/Done, direct
   planning to read their **actual shipped spec and code**, not just the Linear text, so the new plan
   matches what was really built.

Everything else in `/planit` (DOCS_DIR resolution + `specs_dir` pin offer, existing-spec sufficiency
check, handoff to Superpowers, convention-path save) is unchanged.

## Non-goals / out of scope

- **The loop and the other wrapper commands** (`implementit`, `shipit`, `reviewit`, `addressit`,
  `mergeit`) are **not** touched here. They remain; pruning them is a separate, staged decision after
  the interactive + notifications workflow is validated on real tickets.
- No change to the spec/plan convention docs or `implementit`'s plan-discovery.

## Acceptance criteria

- `/projectit` contains only Phases 0–3 + a Done summary; no Phase 4 or 5, no `docs_dir_for`, no
  `specs_dir` pinning, no label creation/application, no plan/spec wiring into tickets.
- Milestone descriptions produced by `/projectit` carry the up-front shared contracts.
- Multi-repo runs tag each work ticket with a `**Target repo:** <name>` line; single-repo runs omit
  repo handling.
- `/projectit` still defers all Linear writes to one post-Phase-3 batch and is idempotent on re-run;
  `--dry-run` still prints every Linear write instead of executing.
- `/planit` reads the parent milestone's contracts and treats merged `blockedBy` dependencies'
  shipped code/spec as ground truth, with unchanged storage naming.
- The Done summary points the user at `/planit` (not at a loop-ready label).
