# Design: Autonomous implementation loop

- **Date:** 2026-06-26
- **Status:** Approved (design)
- **Scope:** `plugins/personal/scripts/loop.py` + `test_loop.py` only. No command-file changes.
- **Depends on:** PR #10 (commands `/addressit`, loop-ready `/reviewit` `/mergeit` `/shipit` `/implementit` — merged) and **PR #11** (per-step usage logging — `InvocationResult`/`TicketResult` carry `usage`). This plan assumes both are on `main`.

## 1. Motivation

`loop.py` today runs `implementit → shipit → reviewit` per ticket and **stops before merge**. The commands already emit a full status contract (PR #10). This work wires the orchestration so each ticket is driven to merge autonomously — `implementit → shipit → (reviewit ↔ addressit)* → mergeit` — and **fully merged (ticket auto-closed by the connector) before the next ticket starts**, so each new branch roots on an up-to-date `main` and downstream conflicts shrink.

The four cost levers from the usage discussion are folded in here (this is where they live), with their tunable values **parameterized and flagged RETUNE** — set conservatively now, corrected from the per-step usage numbers PR #11 produces.

## 2. Goals / Non-goals

**Goals**
- A per-ticket state machine adding the review↔address alternation and the merge step.
- Parse the new sentinels: `/addressit` (`ADDRESSED`/`PUSHED_BACK`/`BLOCKED`), `/mergeit` (`MERGED`/`MERGE_BLOCKED`).
- Bounded alternation (max-rounds cap) with stall handling = **record needs-human + continue to next ticket**.
- Merge only when the latest review verdict is `APPROVED`.
- Fold in cost levers: model routing (per-step + per-round map), effort (feasibility-gated), max-rounds cap, caching (non-task).
- Per-ticket disposition + round count in the run summary (on top of PR #11's usage breakdown).
- **Detached execution** (`--detach`) that starts the run in the background and returns a `tail -f` watch command, plus **flushed progress lines** so a watcher sees the current ticket / step / round live.

**Non-goals**
- No command-file behavior changes (PR #10 froze that surface).
- No changes to triage / feasibility-guard semantics.
- Not reading usage to *set* the tunable values in this work — values are parameterized; retuning is a follow-up once real numbers exist.

## 3. Per-ticket state machine

```
implementit            IMPLEMENTED?  no  → record failed(implementit), next ticket
shipit                 PR URL?       no  → record failed(shipit),      next ticket
round = 1
loop:
    reviewit(round)    APPROVED            → break → merge
                       CHANGES_REQUESTED   → addressit(round)
                       (neither / error)   → record failed(reviewit),  next ticket
    addressit(round)   ADDRESSED           → round += 1
                                              round > MAX_ROUNDS → stall("max rounds")
                                              else → continue loop
                       PUSHED_BACK         → stall("impasse: reviewer vs responder")
                       BLOCKED             → stall("addressit blocked")
                       (error)             → record failed(addressit), next ticket
merge (only reached on APPROVED):
    mergeit            MERGED              → done(merged)
                       MERGE_BLOCKED       → stall("merge blocked")
                       (error)             → record failed(mergeit),   next ticket
```

- **Stall** = record the ticket's disposition as `NEEDS_HUMAN` with the reason, then **continue to the next ticket** (per decision). The next ticket branches from `main` without the stalled ticket's changes — acceptable.
- The wave stays sequential (`for ticket in wave`), one full pipeline per ticket, so a merged ticket is on `main` before the next `implementit` branches.

## 4. Status parsing

New pure functions mirroring `parse_review_status`, with defensive precedence (a command emits exactly one sentinel as its last line; precedence only guards against accidental duplicates):

- `parse_address_status(text)` → `BLOCKED` > `PUSHED_BACK` > `ADDRESSED` > `None`.
- `parse_merge_status(text)` → `MERGE_BLOCKED` > `MERGED` > `None`.
- `/shipit`'s `STATUS: SHIPPED` is **not** load-bearing — the PR URL remains the success signal (unchanged `classify_outcome`).

## 5. Termination & rounds

- `MAX_ROUNDS` constant (default **3**), overridable via `--max-rounds`. One "round" = one `reviewit` + (if not approved) one `addressit`.
- `APPROVED` at any round → merge. Rounds exhausted without `APPROVED` → stall. `PUSHED_BACK`/`BLOCKED` → immediate stall.

## 6. Cost levers (folded in)

| Lever | This spec | RETUNE? |
|---|---|---|
| **Model routing** | `models` map gains `addressit`, `mergeit`, and splits review into `reviewit` (round 1) vs `reviewit_rereview` (rounds ≥2). Defaults: implementit `sonnet`, shipit `sonnet`, reviewit `opus`, reviewit_rereview `sonnet`, addressit `sonnet`, mergeit `haiku`, triage `sonnet`, guard `haiku`. | reviewit_rereview model — confirm Sonnet re-reviews are good enough from usage/quality data |
| **Effort** | **Feasibility-gated task:** determine whether `claude -p` exposes a per-invocation effort control headlessly. If yes → per-step effort map (low: triage/shipit/mergeit; high/xhigh: implementit + round-1 reviewit; medium: addressit/re-reviews) plumbed through `build_claude_cmd`. If no → document that it's not headlessly controllable and drop the lever. | effort values, if supported |
| **Max-rounds** | The `MAX_ROUNDS` cap (§5) — the primary structural cost control. | the value (3) |
| **Caching** | Non-task. Per-ticket bundle cache already exists (PR #10); cross-process caching between separate `claude -p` runs is inherently limited. | — |

## 7. Reporting

`TicketResult` gains `disposition` (`MERGED` / `NEEDS_HUMAN` / `FAILED`) and `rounds` (int). Summary line per ticket shows disposition + reason + round count; the §PR-11 "Usage by step" breakdown is unchanged and now also covers `addressit`/`mergeit` rows.

## 8. Testing

Unit + state-machine tests (mock runner, no real `claude`): the two new parsers (incl. precedence); APPROVED-first → merge; CHANGES→ADDRESSED→APPROVED→merge (2 rounds); CHANGES→PUSHED_BACK → stall; rounds exhausted → stall; addressit BLOCKED → stall; MERGE_BLOCKED → NEEDS_HUMAN; reviewit error → FAILED; per-round model routing (round-1 opus, round-2 `reviewit_rereview`); mergeit runs **only** after APPROVED; usage still recorded for the new steps.

## 9. Execution & observability

**Foreground (default):** runs the wave to completion, emitting the progress lines below.

**Detached (`--detach`):** `main` re-launches itself (same argv minus `--detach`) with `start_new_session=True`, redirecting stdout+stderr to a timestamped log at `<repo>/.claude/loop/run-<UTC-stamp>.log`. The `.claude/loop/` dir is self-ignored (a `.claude/loop/.gitignore` containing `*` is written on first use, so nothing under it is ever committed). `main` then prints the child PID and a watch command — `tail -f <logpath>` — and exits 0 immediately, freeing the CLI. Because progress lines are flushed, the tail is live.

**Progress events:** an `emit(msg)` callback is threaded through the pipeline (default no-op, so tests stay silent). `run_ticket_pipeline` emits on entry to each step — `implementit`, `shipit`, `reviewit (round r)`, `addressit (round r)`, `mergeit`. `main` wires `emit` to a timestamped, `flush=True` print (which also feeds the detached log) and additionally emits wave start (`wave: N ticket(s)`), per-ticket start (`[i/N] <TID>`), and the per-ticket disposition (`<TID> → MERGED | NEEDS_HUMAN: <reason> | FAILED at <step>`). This line stream is what a `tail -f` watcher reads to know where the loop is.

## 10. Versioning & verification

- Plugin minor bump.
- Verification: `test_loop.py` green; a `--dry-run` shows the extended pipeline; no command-file diffs.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
