# Design: Review/Address loop commands + autonomous-pipeline readiness

- **Date:** 2026-06-26
- **Status:** Approved (design)
- **Scope:** `plugins/personal` — new `/addressit` command; changes to `/reviewit`, `/mergeit`, `/shipit`, `/implementit`; new shared context convention. **No `loop.py` changes in this work.**

## 1. Motivation

The headless loop (`plugins/personal/scripts/loop.py`) currently runs `implementit → shipit → reviewit` per ticket and stops. The goal is a **fully autonomous per-ticket pipeline**: implement a plan, open a PR, then alternate review and response until the PR is approved, merge it, clean up branches, and let the GitHub↔Linear connector auto-close the ticket — *before the next ticket starts*. Finishing each ticket to merge before branching the next keeps every new branch rooted on an up-to-date `main`, reducing downstream conflicts.

This work prepares the **commands** for that orchestration. It does not modify the loop itself; wiring the alternation and merge step into `loop.py` is a deliberate follow-up (see §9).

## 2. Goals / Non-goals

**Goals**
- Add a new `/addressit {TICKET_ID}` command that responds to `/reviewit`'s findings: implements valid fixes, pushes back on unnecessary ones, pushes fix commits to the PR branch, and posts its disposition as a PR comment.
- Give both `/reviewit` and `/addressit` full, identical context: the Linear ticket (plus related tickets, project, milestone, parent/sub-issues, relations) and the spec/plan — via a shared, cached, per-ticket context bundle.
- Make `/mergeit` loop-ready: headless-safe (never prompts), merges only on an `APPROVED` verdict, cleans up the context bundle, and emits a machine-parseable status.
- Make recommended adjustments to `/shipit` (uniform status) and `/implementit` (branch from up-to-date `main`) that support the autonomous flow.
- Freeze a status-sentinel contract across all five commands so the loop can later key off it mechanically.

**Non-goals**
- No changes to `loop.py` or `test_loop.py` (the alternation, merge-step wiring, and stall/max-rounds detection are a separate follow-up).
- No manual manipulation of Linear ticket status (the connector handles it on merge).

## 3. Target autonomous pipeline (the contract being frozen)

Orchestrated *later* by `loop.py`; documented here so command signals line up:

```
implementit {T}  → STATUS: IMPLEMENTED | NO_PLAN
shipit {T}       → PR URL  (+ STATUS: SHIPPED)
repeat up to N rounds:
    reviewit {T}     → STATUS: APPROVED | CHANGES_REQUESTED
        APPROVED → break
    addressit {T}    → STATUS: ADDRESSED | PUSHED_BACK | BLOCKED
        ADDRESSED → loop (re-review)
        PUSHED_BACK twice consecutively → break, surface to human
mergeit {T}      → STATUS: MERGED | MERGE_BLOCKED   (only runs when reviewit verdict is APPROVED)
                   → deletes context bundle, deletes branch, syncs main; ticket auto-closes via connector
→ next ticket branches from freshly-synced main
```

### Status vocabulary

| Command | Emits | New? |
|---|---|---|
| implementit | `STATUS: IMPLEMENTED` / `STATUS: NO_PLAN` | exists |
| shipit | PR URL + `STATUS: SHIPPED` | URL exists; status new |
| reviewit | `STATUS: APPROVED` / `STATUS: CHANGES_REQUESTED` | exists |
| addressit | `STATUS: ADDRESSED` / `STATUS: PUSHED_BACK` / `STATUS: BLOCKED` | new |
| mergeit | `STATUS: MERGED` / `STATUS: MERGE_BLOCKED` | new |

Every sentinel is emitted as the **very last line** of the command's response, matching the existing `implementit`/`reviewit` convention so `loop.py`'s substring checks keep working.

## 4. Shared review context

Two layers.

### 4.1 Static recipe (committed) — `plugins/personal/review-context-convention.md`

A new convention doc, mirroring the existing `spec-and-plan-convention.md`. Single source of truth for *how* to gather review context and *how* the bundle behaves. `/reviewit`, `/addressit`, and `/mergeit` reference it rather than duplicating the logic. It specifies the contents, location, naming, gitignore requirement, and lifecycle below.

### 4.2 Per-ticket generated bundle (ephemeral)

- **Path:** `<DOCS_DIR>/superpowers/context/<TICKET_ID>-review-context.md`, where `DOCS_DIR` is resolved exactly as in `implementit` Step 1 (`specs_dir` override → umbrella `<umbrella>/docs` → single-repo `<repo>/.claude/docs`).
- **Contents = stable intent only:**
  - Linear ticket: title, description, state; its project; its milestone; parent and sub-issues; `blockedBy`/`blocks`/related tickets — fetched via the Linear MCP.
  - Spec and plan files for the ticket (both the `superpowers/specs|plans` and flat `specs|plans` layouts, as `implementit` already searches), plus the milestone spec if the plan references one.
- **Generated once, reused:** the first command to need it (normally `reviewit`) fetches and writes it; later runs (`addressit`, re-runs of `reviewit`) read it. Keeps both commands' understanding identical and avoids re-hitting Linear each round. Regenerate only if the file is missing.
- **Unique per ticket** via `<TICKET_ID>` in the filename, so concurrent runs on different tickets never collide.
- **Gitignored:** for single-repo layouts (where `DOCS_DIR` is inside the code repo), the bundle must never be committed into the PR. The convention doc instructs ensuring a `.gitignore` entry covering `<DOCS_DIR-relative>/superpowers/context/` exists before writing. (Umbrella layouts store `DOCS_DIR` outside the code repo, so there is no pollution risk there.)
- **Deleted by `mergeit`** after a successful merge.

### 4.3 Fetched live every run (never cached)

The PR diff and the **full comment thread** (top-level `## Code Review` / `## Review Response` comments, inline review comments, and formal reviews) change between rounds, so both commands always fetch them live. This is what keeps the commands "fully context-aware of the comments on the PR."

## 5. `/addressit {TICKET_ID}` — new command (thin wrapper on `superpowers:receiving-code-review`)

1. **Resolve the PR** for the ticket (same logic as `reviewit` Step 1; accept a bare PR number too).
2. **Load-or-generate** the context bundle (§4.1 doc); fetch the **live** PR diff and full comment thread.
3. **Identify findings:** take the most recent `## Code Review` comment from `reviewit` as the findings to respond to. Read prior `## Review Response` comments and inline threads so already-resolved or already-disputed items are not re-litigated.
4. **Invoke `superpowers:receiving-code-review`:** evaluate each finding against codebase reality + spec/plan + Linear intent. Implement valid fixes one at a time (test each, per the skill). **Hold ground** on wrong/unnecessary/out-of-scope findings, posting technical reasoning — do not cave to keep the loop moving.
5. **Commit & push fixes** to the PR branch: Conventional Commit, `{TICKET_ID}` trailing parenthetical, no co-author line, no footer in the commit message.
6. **Post a `## Review Response` comment** with per-item disposition (`Fixed: …` / `Pushed back: … <reasoning>`), ending with the `🤖 Generated with [Claude Code](https://claude.com/claude-code)` footer — mirroring `reviewit`'s comment style.
7. **Emit status** as the last line:
   - `STATUS: ADDRESSED` — at least one fix was committed and pushed (re-review warranted).
   - `STATUS: PUSHED_BACK` — zero code changes; all findings disputed with posted reasoning (potential stall).
   - `STATUS: BLOCKED` — could not operate (no `## Code Review` comment found, branch checkout failed, etc.).

## 6. `/reviewit` changes

- Replace the spec-only fetch (current Step 2) with **load-or-generate the context bundle** (§4.1 doc): full Linear ticket + related + project/milestone + spec **and** plan. As the typically-first runner, `reviewit` is what creates the bundle.
- Pass that richer intent to the `requesting-code-review` reviewer, alongside the prior-review-thread context already added (so it judges against full ticket intent, not just the spec file).
- Status vocabulary unchanged (`APPROVED` / `CHANGES_REQUESTED`); `APPROVED` is the "ready to merge" signal the loop will key on.

## 7. `/mergeit` — loop-ready

- **Headless-safe — never prompt.** Determine the latest `reviewit` verdict from the live thread. Merge **only** if the most recent verdict is `APPROVED`. If it is "Needs changes" or there is no review comment, do not ask — emit `STATUS: MERGE_BLOCKED` and stop.
- **Bounded CI wait:** poll `gh pr checks`, but on any check failure or a timeout, emit `STATUS: MERGE_BLOCKED`.
- **Cleanup on success:** after the squash-merge + `--delete-branch` + local `main` sync (already present), **delete the per-ticket context bundle** (§4.2).
- **Do not touch Linear status** — the connector auto-closes the ticket on merge.
- **Emit** `STATUS: MERGED` or `STATUS: MERGE_BLOCKED` as the last line.

## 8. Recommended adjustments to `/shipit` and `/implementit`

- **`implementit` (serves "fewer conflicts downstream"):** before creating the work branch, **sync local `main` with origin and branch from `origin/main`** (`git fetch origin main`, then branch off `origin/main`), so each ticket starts from the merged state of every prior ticket in the wave. Today it checks out from `main` without guaranteeing `main` is current.
- **`shipit` (uniform contract):** add a `STATUS: SHIPPED` sentinel as the last line, alongside the existing PR URL. The loop already keys on the PR URL; this makes the status contract uniform across commands. *(Approved for inclusion.)*

## 9. Future loop semantics (NOT implemented in this work)

Documented so the follow-up is mechanical:

- `loop.py`'s per-ticket pipeline extends to: `implementit → shipit → (reviewit ↔ addressit)* → mergeit`.
- Alternation reads `reviewit`'s `APPROVED`/`CHANGES_REQUESTED` and `addressit`'s `ADDRESSED`/`PUSHED_BACK`/`BLOCKED`.
- Termination: `APPROVED` → run `mergeit`. A stall (`CHANGES_REQUESTED` then `PUSHED_BACK` with no progress, or `BLOCKED`) → stop and surface to human. A max-rounds cap (`N`) guards against infinite alternation.
- `mergeit` joins the pipeline; its `MERGED`/`MERGE_BLOCKED` status feeds the run summary.
- Model/timeout entries in `loop.py` get extended for `addressit` and `mergeit`; `test_loop.py` gains coverage for the new parsing.

## 10. Versioning & verification

- **Version bump:** feature addition → `plugins/personal/.claude-plugin/plugin.json` minor bump (`0.4.0 → 0.5.0`).
- **Verification (this work is markdown commands + one convention doc, no runtime code):**
  - Internal consistency: every command that reads/writes/deletes the bundle agrees with `review-context-convention.md` on path, naming, and lifecycle.
  - Status sentinels are emitted as the last line and match the table in §3.
  - Manual trace of a `reviewit → addressit → reviewit → mergeit` cycle confirms the bundle is created once, reused, and deleted on merge, and that `mergeit` is non-interactive.
  - No `loop.py`/`test_loop.py` changes; existing tests remain green.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
