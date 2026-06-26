# Loop Optional Merge — Default Stop Before Merge, `--merge` to Opt In (Design Spec)

- **Date:** 2026-06-26
- **Status:** Approved design (brainstorming output)
- **Repo:** `claude-skills` (the `personal` plugin)
- **Linear ticket:** none (exploratory personal work)

## Summary

The autonomous loop (`plugins/personal/scripts/loop.py`) runs each `loop-ready` ticket through a
fixed pipeline ending in `mergeit`. On projects whose PRs require team approval (e.g. the
`~/ingest/*` work repos with branch protection), auto-merge is impossible — `mergeit` fails and
the ticket lands as a misleading `NEEDS_HUMAN` "merge blocked" stall after a wasted `mergeit`
invocation.

This change makes **merge opt-in**: by default the loop stops after the review↔address loop
reaches `APPROVED`, reporting a new terminal disposition **`READY_FOR_REVIEW`** (a clean success
— the PR is up and loop-approved, awaiting the human/team review+merge). Passing **`--merge`**
restores the full pipeline through `mergeit` exactly as today.

## Context

`run_ticket_pipeline` (in `loop.py`) runs a hardcoded sequence:

```
implementit → shipit → (reviewit ↔ addressit until APPROVED, capped by --max-rounds) → mergeit
```

Terminal dispositions today: `MERGED`, `FAILED`, `NEEDS_HUMAN`. There is no way to select or skip
steps. On a branch-protected repo the `mergeit` step returns `MERGE_BLOCKED`, so the loop returns
`stall("merge blocked ...")` → `NEEDS_HUMAN`, even though the automation succeeded and the PR is
correctly sitting open for team review.

`format_summary` renders a non-failed result generically as
`{ticket_id}: {disposition} — PR {pr} — {rounds} round(s)`, and `main`'s per-ticket `emit` falls
through to printing the disposition for any non-`NEEDS_HUMAN`/non-failed result. Both therefore
handle a new disposition string **without modification**.

## Key decisions (from brainstorming)

1. **Merge is opt-in via a flag, not a `CLAUDE.md` hint.** No per-repo config for now — a single
   `--merge` flag keeps it simple and explicit.
2. **Default is to NOT merge.** This flips the prior always-merge behavior for *every* project,
   including personal ones — they now pass `--merge` to auto-merge. Safer default.
3. **New terminal disposition `READY_FOR_REVIEW`.** Distinct from `MERGED`/`FAILED`/`NEEDS_HUMAN`;
   it is a *success* outcome. The mild overlap with the per-round `reviewit` verdict (`APPROVED`/
   `CHANGES_REQUESTED`) is acceptable — one is a ticket disposition, the other a review-round
   verdict, in different namespaces.
4. **`format_summary` is unchanged** — it already renders arbitrary dispositions generically
   (verified). The new disposition flows through with no summary-code change.
5. **`run_ticket_pipeline`'s `merge` param defaults to `False`**, mirroring the CLI default rather
   than preserving legacy behavior. Existing tests that assert the merge path are updated to pass
   `merge=True` (see Testing).

## Behavior

`--merge` (default off). The pipeline is unchanged through
`implementit → shipit → (reviewit ↔ addressit until APPROVED)`. At the point the review loop
breaks on `APPROVED`:

- **Default (`merge=False`):** do **not** invoke `mergeit`. Return
  `TicketResult(tid, implemented=True, pr_url=pr_url, review=last_review, failed_step=None,
  reason=None, usage=usages, disposition="READY_FOR_REVIEW", rounds=rounds)`.
- **`--merge` (`merge=True`):** run the existing `mergeit` block unchanged — `MERGED` on success,
  or `stall("merge blocked ...")` → `NEEDS_HUMAN`.

Every other path is untouched: `implementit`/`shipit` failure, `reviewit` no-verdict, `addressit`
`PUSHED_BACK`/`BLOCKED`, and `max-rounds` reached all behave exactly as today.

## Code touch points (all in `plugins/personal/scripts/loop.py`)

1. **`parse_args`:** add `p.add_argument("--merge", action="store_true")` (default `False`).
2. **`run_ticket_pipeline`:** add a `merge=False` parameter. After the `while` loop breaks on
   `APPROVED` and before the current `mergeit` step, insert:
   `if not merge: return TicketResult(tid, True, pr_url, last_review, None, None, usages,
   "READY_FOR_REVIEW", rounds)`. The existing `mergeit` block follows unchanged.
3. **`main`:** pass `merge=args.merge` into the `run_ticket_pipeline(...)` call. Update the
   `--dry-run` preview so the `mergeit` "would run" line prints **only** when `args.merge` is set;
   otherwise print a line such as
   `then stop on approval → READY_FOR_REVIEW (merge disabled; pass --merge to auto-merge)`.
4. **No change:** `format_summary` (renders the disposition generically) and `main`'s per-ticket
   `emit` (the non-failed/non-`NEEDS_HUMAN` branch already emits `r.disposition`).

## Reporting

- **Run summary:** `READY_FOR_REVIEW` renders as
  `  <TICKET-ID>: READY_FOR_REVIEW — PR <url> — <n> round(s)` — a success line, no `reason`.
- **Live emit:** `<TICKET-ID> → READY_FOR_REVIEW`.
- **Dry-run:** the pipeline preview reflects the merge state — `mergeit` appears only with
  `--merge`; without it the preview shows the stop-at-`READY_FOR_REVIEW` line.

## Testing

`test_loop.py` (unittest). Run from `plugins/personal/scripts/` with `python -m unittest test_loop`.

**New tests:**
- `parse_args`: `--merge` absent → `args.merge is False`; present → `True`.
- `run_ticket_pipeline(..., merge=False)`: scripted `implementit → shipit → reviewit(APPROVED)`
  with **no** `mergeit` invocation in the runner sequence → disposition `READY_FOR_REVIEW`,
  `pr_url` set, `failed_step is None`, and `mergeit` is never called (assert the runner saw no
  `mergeit` command).
- Dry-run toggle: `main([... "--dry-run"])` output omits the `mergeit` line and includes the
  `READY_FOR_REVIEW`/merge-disabled note; `main([... "--merge", "--dry-run"])` includes the
  `mergeit` line.

**Updated existing tests** (add `merge=True` so they still exercise the merge path):
`test_all_steps_succeed`, `test_approved_first_round_merges`,
`test_changes_then_addressed_then_approved_merges`, `test_merge_blocked_is_needs_human`,
`test_mergeit_not_run_unless_approved`. (Any other `run_ticket_pipeline` test that scripts a
`mergeit` response must pass `merge=True`.)

## Out of scope

- A per-repo `CLAUDE.md` hint (e.g. `loop_merge:`) to set the default per project — deferred;
  the flag suffices for now.
- A general `--stop-after <step>` / step-selection mechanism — YAGNI; the need is binary
  (merge or not).
- Any change to `mergeit` itself or the review↔address state machine.

## Open items / deferred

- Whether to later add a `loop_merge:` `CLAUDE.md` hint so branch-protected repos default off and
  others default on without a flag — revisit if the flag proves easy to forget.
- README: document the new `--merge` flag and the `READY_FOR_REVIEW` disposition alongside the
  existing loop flags.
