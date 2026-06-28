# projectit: per-ticket specs (drop the milestone-spec model) — Design Spec

**Status:** Approved design
**Date:** 2026-06-28
**Repo:** `~/claude-skills` (personal plugin)
**Affects:** `plugins/personal/commands/projectit.md` (primary), `plugins/personal/commands/implementit.md` (one small companion change)

---

## 1. Problem

projectit resolves a **single** `DOCS_DIR` and writes one **milestone spec per milestone** plus a ticket plan per ticket, all into that one location. implementit and the loop are **per-repo** — each resolves its own `DOCS_DIR` from the repo it runs in. In a **multi-repo** (umbrella) project this breaks two ways:

1. **Placement:** projectit writes every ticket's plan to one `DOCS_DIR`, but the loop running in repo B reads from repo B's `DOCS_DIR` — so repo B's plans aren't found.
2. **Cross-repo coupling:** a ticket plan links its milestone spec via a relative `../specs/…` path. When the plan and its milestone spec must live in different repos, that link can't resolve.

The milestone-spec file is the root of the coupling: it is a project-level artifact that per-repo plans reference.

## 2. Decision

**Drop the milestone-spec model. projectit produces a self-contained `spec + plan` per ticket, written into that ticket's own repo — exactly matching `/personal:planit`'s output shape.**

This:
- Eliminates the cross-repo coupling (no shared spec file; nothing to duplicate or cross-link).
- Unifies the two commands: planit already writes `specs/{TICKET_ID}-slug.md` + `plans/{TICKET_ID}-slug.md` per ticket. projectit becomes "planit in bulk + Linear scaffolding," one mental model.
- Keeps per-repo **placement** (still required so the loop finds each ticket's docs in its repo), but removes the milestone-spec **duplication/linking** problem entirely.

**Tradeoff (accepted):** the milestone spec's real value was locking cross-cutting decisions in one editable file so sibling tickets stay consistent — most valuable for a cross-stack milestone (BE produces a contract FE consumes). With per-ticket specs there is no single source-of-truth file; a shared decision is inlined into each ticket's spec. Two things make this acceptable:
- projectit still does a **cross-ticket design pass** (in context, not as a file) and feeds the shared decisions to each ticket subagent, so the specs are written *consistently* — they just inline what they need.
- The workflow already grounds a downstream ticket's plan against the **shipped** upstream code (we plan FE after BE merges), so the spec was never the load-bearing contract — the shipped code is.

## 3. Current behavior → change map (`projectit.md`)

### Conventions (line 6)
- **Was:** "Resolve `DOCS_DIR` exactly as `/personal:planit` does" (one `DOCS_DIR`).
- **Now:** resolve `DOCS_DIR` **per the ticket's assigned repo** — `docs_dir_for(repo)`: read *that repo's* `CLAUDE.md` (`specs_dir` override → `<umbrella>/docs` → `<repo>/.claude/docs`), resolved from that repo's root, cached per repo. Single-repo projects resolve once → identical to today.

### Phase 0 — step 7 (REPOS)
- Also record each repo's **local path** (not just canonical name) — needed to read its `CLAUDE.md` and write its docs. The sibling-scan (tier b) already yields paths; for repos from `linear_repos:`/GitHub (tiers a/c) without a known local path, locate by workspace scan or ask. **If an assigned repo isn't checked out locally, warn and skip generating its docs** (projectit can't write there) — the ticket is still created/labeled in Linear; its docs are authored later (e.g. via planit in that repo).

### Phase 4 — Bulk doc generation (rewrite)
- **Drop Round 1 (milestone specs) / Round 2 split.**
- **Cross-ticket design pass (in context, no file):** before dispatching, the controller (Opus) drafts each milestone's cross-cutting decisions / shared contracts from the Phase-1 description + Phase-3 breakdown, and holds them as notes to feed subagents. Not written to disk.
- **One subagent per ticket** (batched ≤5, **dependency order** so a ticket's `blockedBy` specs exist first and can be passed as context). Each subagent receives: the project description, the relevant milestone shared-decision notes, the ticket's story + intent, its `blockedBy` prerequisites' specs, and **its repo path** (explores real code). It writes BOTH:
  - `docs_dir_for(ticket.repo)/superpowers/specs/<TICKET-ID>-<slug>.md` — a **self-contained spec**: purpose/scope; architecture & approach; the cross-cutting decisions it depends on (inlined, not linked); acceptance; explicit out-of-scope.
  - `docs_dir_for(ticket.repo)/superpowers/plans/<TICKET-ID>-<slug>.md` — a **resilient plan**: what to build, acceptance criteria, which part of the design it realizes, testing intent; light on exact signatures. It MUST start with:

        **Spec:** ../specs/<TICKET-ID>-<slug>.md
        **Depends on:** <TICKET-ID, …>   (omit if no blockers)

    The `../specs/<TICKET-ID>-<slug>.md` link is **same-repo** (both files in the ticket's `DOCS_DIR`), so it always resolves.
- Returns both paths + a one-line summary. (Dry-run: write under each ticket repo's `DOCS_DIR/superpowers/.dryrun/{specs,plans}/`.)

### Phase 4 — review gate
- Table: ticket → spec path + plan path (grouped by story/milestone), each with its repo and one-line summary.

### Phase 5 — Link & mark ready
- **Step 2:** compute the relative plan path AND spec path against the **ticket's repo** `DOCS_DIR`; GitHub URL (best-effort) from **that repo's** remote. Prepend to the ticket description:

        **Plan:** <relative plan path>
        **Spec:** <relative spec path>

  (was `**Milestone spec (repo):**`). Labels `["loop-ready", "repo:<assigned-repo>"]` unchanged.
- **Step 3 (milestone descriptions): removed** — milestones no longer have a spec file. (Milestones remain Linear groupings; their design intent lives in the per-ticket specs + the project description.)
- Step 1 (labels) and Step 4 (summary) unchanged.

### implementit.md — Step 3 (companion change)
- implementit Step 3 currently loads a spec referenced by a line beginning **`**Milestone spec:** `**. Broaden it to also recognize **`**Spec:** `** so the per-ticket spec is loaded as design context alongside the plan. Keep recognizing `**Milestone spec:**` for backward compatibility with existing plans (M4/M5/M6).

## 4. Backward compatibility
- **Single-repo projects:** per-repo resolution collapses to the one repo → behavior identical to today (minus the milestone-spec file, which becomes per-ticket specs).
- **Existing plans** that use `**Milestone spec:**` (the M4/M5/M6 plans already on disk) keep working — implementit still recognizes that header.
- **planit** already produces per-ticket specs; no change required. (Optional future alignment: planit's plan could also emit the `**Spec:**` header — out of scope here.)

## 5. Out of scope
- Changing implementit/the loop's per-repo resolution (already correct).
- Auto-cloning repos that aren't checked out locally.
- Committing/pushing generated docs.
- Reintroducing any project- or milestone-level shared spec **file**.

## 6. Testing
projectit is a prose command (no unit tests). Verify via `--dry-run` on a **multi-repo** project:
- each ticket's `.dryrun` **spec and plan** land under **its assigned repo's** `DOCS_DIR/superpowers/{specs,plans}/`;
- each plan's `**Spec:**` line points to a same-repo `../specs/<TICKET-ID>-…` path;
- no file is written outside an assigned repo's `DOCS_DIR`; a ticket whose repo isn't checked out is reported as skipped.
Also a single-repo `--dry-run` to confirm unchanged behavior. Confirm implementit Step 3 recognizes a `**Spec:**` header (read-through of the edited command).
