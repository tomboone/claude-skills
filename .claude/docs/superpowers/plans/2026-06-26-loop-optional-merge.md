# Loop Optional Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the loop stop after the review↔address loop reaches APPROVED by default (new `READY_FOR_REVIEW` disposition), running `mergeit` only when `--merge` is passed.

**Architecture:** A `--merge` flag (default off) flows into `run_ticket_pipeline` via a `merge=False` parameter. At the point the review loop breaks on APPROVED, the pipeline either returns the new terminal disposition `READY_FOR_REVIEW` (default) or runs the existing `mergeit` block (`--merge`). `main` threads the flag and reflects it in the `--dry-run` preview. `format_summary` and the per-ticket emit need no change — both render dispositions generically.

**Tech Stack:** Python 3 standard library (`argparse`, `unittest`); the loop is `plugins/personal/scripts/loop.py`.

## Global Constraints

- **Spec:** `.claude/docs/superpowers/specs/2026-06-26-loop-optional-merge-design.md` — every task realizes part of it.
- **Match existing `loop.py` style:** plain functions, **no type annotations**. The file uses none; do not add any.
- **Flag:** `--merge`, `action="store_true"`, default `False`.
- **Disposition string:** exactly `READY_FOR_REVIEW` (a success — `implemented=True`, `pr_url` set, `failed_step=None`, `reason=None`).
- **`run_ticket_pipeline`'s new param** is `merge`, default `False`, added **last** in the signature (after `emit`) to preserve positional calls.
- **`TicketResult` field order** (from the existing MERGED return): `TicketResult(tid, implemented, pr_url, review_status, failed_step, reason, usage, disposition, rounds)`.
- **Run tests from** `plugins/personal/scripts/` with `python -m unittest test_loop -v`.
- **Commits:** Conventional Commits, no Linear ticket → no parenthetical; code → `feat(personal): …`, docs → `docs: …`. No `Co-Authored-By` trailer, no footer on commit messages.

## File Structure

- **Modify** `plugins/personal/scripts/loop.py`
  - `parse_args` — add `--merge`.
  - `run_ticket_pipeline` — add `merge=False` param; insert the `READY_FOR_REVIEW` branch before the existing `mergeit` step.
  - `main` — pass `merge=args.merge` to `run_ticket_pipeline`; gate the `--dry-run` `mergeit` line on `args.merge`.
- **Modify** `plugins/personal/scripts/test_loop.py`
  - New `TestMergeArg`, `TestOptionalMerge`, `TestMainDryRunMergeToggle`.
  - Add `merge=True` to the **ten** existing pipeline tests that drive the merge path.
- **Modify** `README.md` — document `--merge` and the `READY_FOR_REVIEW` disposition.

---

## Task 1: `--merge` flag

**Files:**
- Modify: `plugins/personal/scripts/loop.py` (`parse_args`)
- Test: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Produces: `parse_args(...)` result gains a `.merge` attribute (`bool`, default `False`).

- [ ] **Step 1: Write the failing test**

Add after `TestMaxRoundsArg` (currently ends near line 295) in `test_loop.py`:

```python
class TestMergeArg(unittest.TestCase):
    def test_flag_parsed(self):
        self.assertTrue(loop.parse_args(["--merge"]).merge)

    def test_default_false(self):
        self.assertFalse(loop.parse_args([]).merge)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest test_loop.TestMergeArg -v`
Expected: FAIL — `--merge` is an unrecognized argument (SystemExit) / `Namespace` has no attribute `merge`.

- [ ] **Step 3: Add the flag**

In `parse_args` (the `add_argument` block, currently lines 313-322), add alongside the other flags (e.g. after `--detach`):

```python
    p.add_argument("--merge", action="store_true")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest test_loop.TestMergeArg -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(personal): add --merge flag to the loop"
```

---

## Task 2: `READY_FOR_REVIEW` default in the pipeline

**Files:**
- Modify: `plugins/personal/scripts/loop.py` (`run_ticket_pipeline`)
- Test: `plugins/personal/scripts/test_loop.py` (new `TestOptionalMerge`; update ten existing tests)

**Interfaces:**
- Consumes: nothing new.
- Produces: `run_ticket_pipeline(ticket, runner, models, timeouts, max_rounds=MAX_ROUNDS, efforts=None, emit=None, merge=False)`. When the review loop reaches APPROVED and `merge` is falsy, returns a `TicketResult` with `disposition="READY_FOR_REVIEW"`, `implemented=True`, `pr_url` set, `failed_step=None`. When `merge` is truthy, behaves exactly as today (`MERGED` / `NEEDS_HUMAN` "merge blocked").

- [ ] **Step 1: Write the failing tests**

Add a new class after `TestPipelineStateMachine` (near line 558) in `test_loop.py`:

```python
class TestOptionalMerge(unittest.TestCase):
    def _impl(self): return loop.InvocationResult(0, "STATUS: IMPLEMENTED", False)
    def _ship(self): return loop.InvocationResult(0, "PR https://github.com/o/r/pull/3", False)

    def test_default_stops_at_ready_for_review(self):
        # merge defaults False: implementit -> shipit -> reviewit(APPROVED), then STOP (no mergeit)
        runner = make_runner([self._impl(), self._ship(),
            loop.InvocationResult(0, "STATUS: APPROVED", False)])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertEqual(r.disposition, "READY_FOR_REVIEW")
        self.assertTrue(r.implemented)
        self.assertEqual(r.pr_url, "https://github.com/o/r/pull/3")
        self.assertEqual(r.review_status, "APPROVED")
        self.assertIsNone(r.failed_step)
        self.assertEqual(len(runner.calls["cmds"]), 3)                       # mergeit never invoked
        self.assertFalse(any("mergeit" in c[2] for c in runner.calls["cmds"]))

    def test_merge_flag_runs_mergeit(self):
        runner = make_runner([self._impl(), self._ship(),
            loop.InvocationResult(0, "STATUS: APPROVED", False),
            loop.InvocationResult(0, "STATUS: MERGED", False)])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, merge=True)
        self.assertEqual(r.disposition, "MERGED")
        self.assertTrue(any("mergeit" in c[2] for c in runner.calls["cmds"]))
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m unittest test_loop.TestOptionalMerge -v`
Expected: FAIL — `test_merge_flag_runs_mergeit` errors with `unexpected keyword argument 'merge'`; `test_default_stops_at_ready_for_review` fails because the pipeline tries a 4th (mergeit) runner call against a 3-item script (IndexError / disposition is not `READY_FOR_REVIEW`).

- [ ] **Step 3: Add the `merge` param and the `READY_FOR_REVIEW` branch**

In `loop.py`, change the `run_ticket_pipeline` signature (line 144) to add `merge=False` last:

```python
def run_ticket_pipeline(ticket, runner, models, timeouts, max_rounds=MAX_ROUNDS, efforts=None, emit=None, merge=False):
```

Then, immediately after the review `while` loop (right after it `break`s on APPROVED) and **before** the existing `res = step("mergeit", ...)` line (currently line 202), insert:

```python
    if not merge:
        return TicketResult(tid, True, pr_url, last_review, None, None, usages, "READY_FOR_REVIEW", rounds)
```

Leave the existing `mergeit` block (currently lines 202-207) unchanged.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `python -m unittest test_loop.TestOptionalMerge -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full suite — the ten merge-path tests now fail**

Run: `python -m unittest test_loop -v`
Expected: FAIL — the ten tests that drive the merge path now stop at `READY_FOR_REVIEW` instead of `MERGED` (they call `run_ticket_pipeline` without `merge=True`). This is expected; fix them in Step 6.

- [ ] **Step 6: Add `merge=True` to the ten merge-path tests**

In `test_loop.py`, add `merge=True` to each of these `run_ticket_pipeline(...)` calls (exact current locations):

```
test_all_steps_succeed                          (~L208):  ..., MODELS, TIMEOUTS)                       -> ..., MODELS, TIMEOUTS, merge=True)
test_changes_requested_is_not_a_failure         (~L252):  ..., MODELS, TIMEOUTS)                       -> ..., MODELS, TIMEOUTS, merge=True)
test_uses_correct_models                        (~L265):  ..., MODELS, TIMEOUTS)                       -> ..., MODELS, TIMEOUTS, merge=True)
test_records_usage_per_step                     (~L460):  ..., MODELS, TIMEOUTS)                       -> ..., MODELS, TIMEOUTS, merge=True)
test_approved_first_round_merges                (~L481):  ..., MODELS, TIMEOUTS)                       -> ..., MODELS, TIMEOUTS, merge=True)
test_changes_then_addressed_then_approved_merges(~L492):  ..., MODELS, TIMEOUTS)                       -> ..., MODELS, TIMEOUTS, merge=True)
test_merge_blocked_is_needs_human               (~L528):  ..., MODELS, TIMEOUTS)                       -> ..., MODELS, TIMEOUTS, merge=True)
test_mergeit_not_run_unless_approved            (~L536):  ..., MODELS, TIMEOUTS)                       -> ..., MODELS, TIMEOUTS, merge=True)
test_effort_per_step_reaches_invocations        (~L548):  ..., MODELS, TIMEOUTS, efforts=efforts)      -> ..., MODELS, TIMEOUTS, efforts=efforts, merge=True)
test_pipeline_emits_step_labels                 (~L571):  ..., MODELS, TIMEOUTS, emit=seen.append)     -> ..., MODELS, TIMEOUTS, emit=seen.append, merge=True)
```

Do **not** add `merge=True` to the early-exit / stall tests (`test_implement_failure_skips_rest`, `test_implement_noop_without_sentinel_skips_rest`, `test_ship_failure_skips_review`, `test_pushed_back_stalls`, `test_rounds_exhausted_stalls`, `test_addressit_blocked_stalls`, `test_records_usage_for_failed_step`) — they never reach the APPROVED break, so the merge flag is irrelevant to them.

(Note: `test_mergeit_not_run_unless_approved` stalls before APPROVED, so it never reaches `mergeit` either way; it gets `merge=True` so its assertion — "mergeit not run *unless approved*" — actually tests that condition rather than passing trivially because merge is off.)

- [ ] **Step 7: Run the full suite to verify everything passes**

Run: `python -m unittest test_loop -v`
Expected: PASS (all tests — the two new `TestOptionalMerge` tests plus the full existing suite, with the ten updated calls green).

- [ ] **Step 8: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(personal): default the loop to stop at READY_FOR_REVIEW unless merging"
```

---

## Task 3: Wire `--merge` through `main` + dry-run preview

**Files:**
- Modify: `plugins/personal/scripts/loop.py` (`main`)
- Test: `plugins/personal/scripts/test_loop.py` (new `TestMainDryRunMergeToggle`)

**Interfaces:**
- Consumes: `parse_args().merge` (Task 1); `run_ticket_pipeline(..., merge=...)` (Task 2).
- Produces: real runs pass `merge=args.merge` into the pipeline; the `--dry-run` preview prints the `mergeit` "would run" line only when `--merge` is set, otherwise a stop-at-`READY_FOR_REVIEW` note.

- [ ] **Step 1: Write the failing test**

Add after `TestMainDryRun` (near line 405) in `test_loop.py`:

```python
class TestMainDryRunMergeToggle(unittest.TestCase):
    def _run(self, argv):
        import io
        import contextlib
        wave = {"project": "p", "wave": [{"id": "A-1", "title": "t"}], "held": []}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = loop.main(
                argv,
                runner=lambda cmd, timeout: loop.InvocationResult(0, "", False),
                triage_fn=lambda project, label, repo_label, runner: wave,
                guard_fn=lambda runner: (True, "ok"),
            )
        return rc, buf.getvalue()

    def test_dry_run_default_omits_mergeit(self):
        rc, out = self._run(["--project", "p", "--repo", "r", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertNotIn("/personal:mergeit", out)
        self.assertIn("READY_FOR_REVIEW", out)

    def test_dry_run_merge_includes_mergeit(self):
        rc, out = self._run(["--project", "p", "--repo", "r", "--merge", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("/personal:mergeit", out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest test_loop.TestMainDryRunMergeToggle -v`
Expected: FAIL — `test_dry_run_default_omits_mergeit` fails because the dry-run currently always prints the `mergeit` line (so `/personal:mergeit` is present and `READY_FOR_REVIEW` is absent).

- [ ] **Step 3: Gate the dry-run `mergeit` line and pass the flag through**

In `loop.py`, in the `--dry-run` block, replace the unconditional `mergeit` print (currently lines 479-480):

```python
            cmd = build_claude_cmd(f"/personal:mergeit {t['id']}", models["mergeit"], effort=efforts.get("mergeit"))
            print("  would run:", " ".join(cmd))
```

with:

```python
            if args.merge:
                cmd = build_claude_cmd(f"/personal:mergeit {t['id']}", models["mergeit"], effort=efforts.get("mergeit"))
                print("  would run:", " ".join(cmd))
            else:
                print("  then stop on approval → READY_FOR_REVIEW (merge disabled; pass --merge to auto-merge)")
```

Then update the real-run pipeline call (currently line 491) to pass the flag:

```python
        r = run_ticket_pipeline(t, runner, models, timeouts, max_rounds=args.max_rounds, efforts=efforts, emit=emit, merge=args.merge)
```

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `python -m unittest test_loop -v`
Expected: PASS (all tests, including the new `TestMainDryRunMergeToggle` and the existing `TestMainDryRun`).

- [ ] **Step 5: Smoke-test both dry-run previews from this repo**

Run (from `plugins/personal/scripts/`):
`python loop.py --project "Anything" --repo claude-skills --dry-run`
and
`python loop.py --project "Anything" --repo claude-skills --merge --dry-run`
Expected: the live feasibility-guard / triage `claude -p` calls may error in a non-interactive shell, but where the per-ticket preview prints, the first omits the `mergeit` line and shows the `READY_FOR_REVIEW` note, and the second shows the `mergeit` line. (If triage can't run here, this step is best-effort — the unit tests in Step 4 are the binding evidence.)

- [ ] **Step 6: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat(personal): thread --merge through the loop run and dry-run preview"
```

---

## Task 4: Document `--merge` and `READY_FOR_REVIEW` in the README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the flag and disposition from Tasks 1-3.
- Produces: user-facing docs next to the existing loop-flag documentation.

- [ ] **Step 1: Locate the loop-flags documentation**

Run: `grep -n '\-\-project\|\-\-max-rounds\|\-\-detach\|loop-ready' README.md`
Expected: the table/section documenting the loop's CLI flags (the `--project` row is around line 123).

- [ ] **Step 2: Add the flag and disposition**

In the loop-flags documentation, add a row/line for `--merge` matching the surrounding style, e.g.:

```markdown
| `--merge` | Run `mergeit` after the review↔address loop reaches APPROVED. **Off by default** — without it the loop stops at the `READY_FOR_REVIEW` disposition (PR opened and loop-approved, left for a human/team to merge). Use it on repos where auto-merge is wanted; omit it where PRs require team approval. |
```

If the README has a section describing run dispositions/outcomes, add `READY_FOR_REVIEW` there too: "the review↔address loop reached APPROVED and `--merge` was not set — the PR is open and ready for the human/team merge." If no such section exists, the flag row above suffices.

- [ ] **Step 3: Verify the docs**

Run: `grep -n '\-\-merge\|READY_FOR_REVIEW' README.md`
Expected: the new `--merge` entry (and any disposition mention) present and adjacent to the existing loop flags.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document the loop --merge flag and READY_FOR_REVIEW disposition"
```

---

## Self-Review

**Spec coverage:**
- `--merge` flag, default off → Task 1. ✓
- Default stops at `READY_FOR_REVIEW`; `--merge` runs `mergeit` unchanged; all other paths untouched → Task 2. ✓
- `run_ticket_pipeline` `merge=False` param mirroring the CLI default; existing merge-path tests updated → Task 2 (Steps 6 enumerates all ten). ✓
- `main` passes `merge=args.merge`; dry-run preview reflects merge state → Task 3. ✓
- `format_summary` / emit unchanged → honored (no task touches them; the new disposition renders generically). ✓
- README documents `--merge` + `READY_FOR_REVIEW` (spec's deferred doc item, pulled in) → Task 4. ✓

**Placeholder scan:** No `TBD`/`TODO`/"handle edge cases"; every code step shows complete code; every command shows expected output. The `~Lxxx` markers in Task 2 Step 6 are current-location hints for finding each call, not unfilled content — the exact edit (`merge=True`) is shown for each. ✓

**Type/name consistency:** `merge=False` param defined in Task 2 is consumed by `main` in Task 3 as `merge=args.merge`, and by tests as `merge=True`. Disposition string `READY_FOR_REVIEW` is identical across the pipeline branch (Task 2), the dry-run note + test (Task 3), and the docs (Task 4). `TicketResult(tid, True, pr_url, last_review, None, None, usages, "READY_FOR_REVIEW", rounds)` matches the field order of the existing MERGED return. No annotations introduced. ✓
