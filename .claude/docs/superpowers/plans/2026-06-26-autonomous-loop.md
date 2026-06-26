# Autonomous Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. TDD throughout — `loop.py` has a real test suite. Steps use `- [ ]`.

**Goal:** Extend `loop.py`'s per-ticket pipeline from `implement→ship→review` to the full autonomous `implement→ship→(review↔address)*→merge`, with bounded alternation and stall handling.

**Architecture:** Pure functions + a state-machine `run_ticket_pipeline`, driven by a mock runner in tests. No real `claude` in tests. No command-file changes.

**Tech stack:** Python stdlib (`unittest`), the `claude -p` status contract from PR #10.

## Global Constraints

- **Depends on PR #11 being merged** (`InvocationResult`/`TicketResult` carry `usage`; `_usage_from_stdout`, `_usage_record`, `_sum_usage`, usage in the summary all exist). Rebase onto `main` after #11 lands before starting.
- Status sentinels (exact): reviewit `APPROVED`/`CHANGES_REQUESTED`; addressit `ADDRESSED`/`PUSHED_BACK`/`BLOCKED`; mergeit `MERGED`/`MERGE_BLOCKED`.
- Stall = disposition `NEEDS_HUMAN` + continue to next ticket. Never stop the wave on a stall.
- Model/effort/max-rounds values are **defaults to retune from usage** — don't hard-code them as if final; keep them in the `models`/`timeouts` maps and a `MAX_ROUNDS`/`--max-rounds`.
- namedtuple changes must stay backward-compatible (defaults on new fields) — existing constructors in tests must keep working.
- Conventional commits; no Linear parenthetical; no co-author; no footer in commits.

---

### Task 1: Status parsers for addressit and mergeit

**Files:** Modify `plugins/personal/scripts/loop.py`; Test `plugins/personal/scripts/test_loop.py`.

**Interfaces — Produces:** `parse_address_status(text) -> "ADDRESSED"|"PUSHED_BACK"|"BLOCKED"|None`; `parse_merge_status(text) -> "MERGED"|"MERGE_BLOCKED"|None`.

- [ ] **Step 1 — failing tests.**

```python
class TestParseAddressStatus(unittest.TestCase):
    def test_addressed(self):
        self.assertEqual(loop.parse_address_status("x\nSTATUS: ADDRESSED"), "ADDRESSED")
    def test_pushed_back(self):
        self.assertEqual(loop.parse_address_status("STATUS: PUSHED_BACK"), "PUSHED_BACK")
    def test_blocked_wins(self):
        self.assertEqual(loop.parse_address_status("STATUS: ADDRESSED\nSTATUS: BLOCKED"), "BLOCKED")
    def test_none(self):
        self.assertIsNone(loop.parse_address_status("nope"))

class TestParseMergeStatus(unittest.TestCase):
    def test_merged(self):
        self.assertEqual(loop.parse_merge_status("done\nSTATUS: MERGED"), "MERGED")
    def test_blocked_wins(self):
        self.assertEqual(loop.parse_merge_status("STATUS: MERGED\nSTATUS: MERGE_BLOCKED"), "MERGE_BLOCKED")
    def test_none(self):
        self.assertIsNone(loop.parse_merge_status("nope"))
```

- [ ] **Step 2 — run, verify fail** (`AttributeError: module 'loop' has no attribute 'parse_address_status'`).
- [ ] **Step 3 — implement** (add after `parse_review_status`):

```python
def parse_address_status(result_text):
    text = result_text or ""
    if "STATUS: BLOCKED" in text:
        return "BLOCKED"
    if "STATUS: PUSHED_BACK" in text:
        return "PUSHED_BACK"
    if "STATUS: ADDRESSED" in text:
        return "ADDRESSED"
    return None


def parse_merge_status(result_text):
    text = result_text or ""
    if "STATUS: MERGE_BLOCKED" in text:
        return "MERGE_BLOCKED"
    if "STATUS: MERGED" in text:
        return "MERGED"
    return None
```

- [ ] **Step 4 — run, verify pass.** Run: `python3 -m pytest test_loop.py -q`. Expected: all green.
- [ ] **Step 5 — commit:** `git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py && git commit -m "feat(personal): add addressit/mergeit status parsers to the loop"`

---

### Task 2: Extend `TicketResult` and the model/timeout maps

**Files:** Modify `loop.py` (namedtuple, `main`'s `models`/`timeouts`).

**Interfaces — Produces:** `TicketResult` with `disposition` (default `None`) and `rounds` (default `0`) after `usage`. `models` keys: `implementit, shipit, reviewit, reviewit_rereview, addressit, mergeit`. `timeouts` keys add `addressit`, `mergeit`.

- [ ] **Step 1 — failing test** (construct with the new fields and the rereview model):

```python
class TestTicketResultShape(unittest.TestCase):
    def test_disposition_and_rounds_default(self):
        r = loop.TicketResult("A-1", True, None, None, None, None)  # 6-arg legacy
        self.assertIsNone(r.disposition)
        self.assertEqual(r.rounds, 0)
    def test_main_models_have_loop_keys(self):
        models = loop.default_models()
        for k in ("reviewit_rereview", "addressit", "mergeit"):
            self.assertIn(k, models)
```

- [ ] **Step 2 — run, verify fail** (`AttributeError: 'TicketResult' object has no attribute 'disposition'`; `default_models` missing).
- [ ] **Step 3 — implement.** Replace the `TicketResult` namedtuple line:

```python
TicketResult = namedtuple(
    "TicketResult",
    ["ticket_id", "implemented", "pr_url", "review_status", "failed_step", "reason", "usage", "disposition", "rounds"],
    defaults=[None, None, 0],
)
```

Add factory helpers near the top (so `main` and tests share one definition):

```python
def default_models():
    return {"implementit": "sonnet", "shipit": "sonnet", "reviewit": "opus",
            "reviewit_rereview": "sonnet", "addressit": "sonnet", "mergeit": "haiku",
            "triage": "sonnet", "guard": "haiku"}


def default_timeouts():
    return {"implementit": 1800, "shipit": 600, "reviewit": 900,
            "addressit": 1800, "mergeit": 1200}
```

In `main`, replace the inline `models = {...}` / `timeouts = {...}` with `models = default_models()` / `timeouts = default_timeouts()`.

- [ ] **Step 4 — run, verify pass** (`python3 -m pytest test_loop.py -q`).
- [ ] **Step 5 — commit:** `feat(personal): widen TicketResult + model/timeout maps for the full loop`

---

### Task 3: State-machine `run_ticket_pipeline`

**Files:** Modify `loop.py` (`run_ticket_pipeline`); update affected tests in `test_loop.py`.

**Interfaces — Consumes:** parsers (Task 1), maps (Task 2). **Produces:** a `TicketResult` carrying `disposition`, `rounds`, `review_status` (last verdict), `usage` (all steps), and on failure `failed_step`/`reason`.

- [ ] **Step 1 — update module test constants + replace superseded tests.** Set `MODELS = loop.default_models()` and `TIMEOUTS = loop.default_timeouts()` in `test_loop.py`. The existing `TestRunTicketPipeline.test_all_steps_succeed`, `test_changes_requested_is_not_a_failure`, `test_uses_correct_models`, and `TestPipelineUsage.*` drive the APPROVED/CHANGES paths to a terminal state that **now** continues into addressit/mergeit — rewrite their scripted runners and assertions to the new flow (below). Add new transition tests:

```python
class TestPipelineStateMachine(unittest.TestCase):
    def _impl(self): return loop.InvocationResult(0, "STATUS: IMPLEMENTED", False)
    def _ship(self): return loop.InvocationResult(0, "PR https://github.com/o/r/pull/1", False)

    def test_approved_first_round_merges(self):
        runner = make_runner([self._impl(), self._ship(),
            loop.InvocationResult(0, "STATUS: APPROVED", False),
            loop.InvocationResult(0, "STATUS: MERGED", False)])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertEqual(r.disposition, "MERGED")
        self.assertEqual(r.rounds, 1)
        self.assertEqual(len(runner.calls["cmds"]), 4)

    def test_changes_then_addressed_then_approved_merges(self):
        runner = make_runner([self._impl(), self._ship(),
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
            loop.InvocationResult(0, "STATUS: ADDRESSED", False),
            loop.InvocationResult(0, "STATUS: APPROVED", False),
            loop.InvocationResult(0, "STATUS: MERGED", False)])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertEqual(r.disposition, "MERGED")
        self.assertEqual(r.rounds, 2)
        # round-2 review uses reviewit_rereview model
        review_cmds = [c for c in runner.calls["cmds"] if "reviewit" in c[2]]
        self.assertEqual(review_cmds[0][review_cmds[0].index("--model")+1], "opus")
        self.assertEqual(review_cmds[1][review_cmds[1].index("--model")+1], "sonnet")

    def test_pushed_back_stalls(self):
        runner = make_runner([self._impl(), self._ship(),
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
            loop.InvocationResult(0, "STATUS: PUSHED_BACK", False)])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertEqual(r.disposition, "NEEDS_HUMAN")
        self.assertIn("impasse", r.reason.lower())

    def test_rounds_exhausted_stalls(self):
        seq = [self._impl(), self._ship()]
        for _ in range(3):  # MAX_ROUNDS=3: review CHANGES + address ADDRESSED, three times
            seq += [loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
                    loop.InvocationResult(0, "STATUS: ADDRESSED", False)]
        r = loop.run_ticket_pipeline({"id": "A-1"}, make_runner(seq), MODELS, TIMEOUTS, max_rounds=3)
        self.assertEqual(r.disposition, "NEEDS_HUMAN")
        self.assertEqual(r.rounds, 3)

    def test_addressit_blocked_stalls(self):
        runner = make_runner([self._impl(), self._ship(),
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
            loop.InvocationResult(0, "STATUS: BLOCKED", False)])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertEqual(r.disposition, "NEEDS_HUMAN")

    def test_merge_blocked_is_needs_human(self):
        runner = make_runner([self._impl(), self._ship(),
            loop.InvocationResult(0, "STATUS: APPROVED", False),
            loop.InvocationResult(0, "STATUS: MERGE_BLOCKED", False)])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertEqual(r.disposition, "NEEDS_HUMAN")
        self.assertIn("merge", r.reason.lower())

    def test_mergeit_not_run_unless_approved(self):
        runner = make_runner([self._impl(), self._ship(),
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
            loop.InvocationResult(0, "STATUS: PUSHED_BACK", False)])
        loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertFalse(any("mergeit" in c[2] for c in runner.calls["cmds"]))
```

- [ ] **Step 2 — run, verify fail** (new tests fail; the superseded ones now assert new flow and also fail until implemented).
- [ ] **Step 3 — implement** the state machine. Add `MAX_ROUNDS = 3` near the constants. Replace `run_ticket_pipeline`:

```python
def run_ticket_pipeline(ticket, runner, models, timeouts, max_rounds=MAX_ROUNDS):
    tid = ticket["id"]
    usages = []

    def step(name, model, timeout):
        res = runner(build_claude_cmd(f"/personal:{name} {tid}", model), timeout)
        usages.append(_usage_record(name, model, res.usage))
        return res

    def fail(at, reason):
        return TicketResult(tid, True, pr_url, last_review, at, reason, usages, "FAILED", rounds)

    def stall(reason):
        return TicketResult(tid, True, pr_url, last_review, None, reason, usages, "NEEDS_HUMAN", rounds)

    pr_url = None
    last_review = None
    rounds = 0

    res = step("implementit", models["implementit"], timeouts["implementit"])
    ok, reason = classify_outcome(res.returncode, res.result_text, res.timed_out, "implementit")
    if not ok:
        return TicketResult(tid, False, None, None, "implementit", reason, usages, "FAILED", 0)

    res = step("shipit", models["shipit"], timeouts["shipit"])
    ok, reason = classify_outcome(res.returncode, res.result_text, res.timed_out, "shipit")
    if not ok:
        return TicketResult(tid, True, None, None, "shipit", reason, usages, "FAILED", 0)
    pr_url = shipit_pr_url(res.result_text)

    while True:
        rounds += 1
        model = models["reviewit"] if rounds == 1 else models["reviewit_rereview"]
        res = step("reviewit", model, timeouts["reviewit"])
        if res.timed_out or res.returncode != 0:
            return fail("reviewit", f"reviewit {'timed out' if res.timed_out else f'exited {res.returncode}'}")
        last_review = parse_review_status(res.result_text)
        if last_review == "APPROVED":
            break
        if last_review != "CHANGES_REQUESTED":
            return fail("reviewit", "reviewit emitted no verdict")

        res = step("addressit", models["addressit"], timeouts["addressit"])
        if res.timed_out or res.returncode != 0:
            return fail("addressit", f"addressit {'timed out' if res.timed_out else f'exited {res.returncode}'}")
        addressed = parse_address_status(res.result_text)
        if addressed == "PUSHED_BACK":
            return stall("impasse: reviewer requested changes, addressit pushed back")
        if addressed == "BLOCKED" or addressed is None:
            return stall("addressit blocked / emitted no status")
        if rounds >= max_rounds:
            return stall(f"max rounds ({max_rounds}) reached without approval")
        # else ADDRESSED → loop for re-review

    res = step("mergeit", models["mergeit"], timeouts["mergeit"])
    if res.timed_out or res.returncode != 0:
        return fail("mergeit", f"mergeit {'timed out' if res.timed_out else f'exited {res.returncode}'}")
    if parse_merge_status(res.result_text) == "MERGED":
        return TicketResult(tid, True, pr_url, last_review, None, None, usages, "MERGED", rounds)
    return stall("merge blocked (CI failed / verdict not ready)")
```

(Note: `classify_outcome` is reused for implementit/shipit only; reviewit/addressit/mergeit use their sentinel parsers + error checks inline, since their success criterion is the STATUS line, not a PR URL.)

- [ ] **Step 4 — run, verify pass** (`python3 -m pytest test_loop.py -q` — all green, including the rewritten legacy tests).
- [ ] **Step 5 — commit:** `feat(personal): drive review↔address↔merge state machine in the loop`

---

### Task 4: Summary shows disposition + rounds

**Files:** Modify `loop.py` (`format_summary`); Test `test_loop.py`.

- [ ] **Step 1 — failing test:**

```python
class TestSummaryDisposition(unittest.TestCase):
    def test_shows_disposition_and_rounds(self):
        r = loop.TicketResult("A-1", True, "https://github.com/o/r/pull/1", "APPROVED",
                              None, None, None, "MERGED", 2)
        out = loop.format_summary([r], [])
        self.assertIn("MERGED", out)
        self.assertIn("2 round", out)
    def test_needs_human_reason_shown(self):
        r = loop.TicketResult("A-2", True, "https://github.com/o/r/pull/2", "CHANGES_REQUESTED",
                              None, "impasse: ...", None, "NEEDS_HUMAN", 3)
        out = loop.format_summary([r], [])
        self.assertIn("NEEDS_HUMAN", out)
        self.assertIn("impasse", out)
```

- [ ] **Step 2 — run, verify fail.**
- [ ] **Step 3 — implement.** In `format_summary`, replace the per-ticket non-failed branch so the line reflects disposition:

```python
        if r.failed_step:
            line = f"  {r.ticket_id}: FAILED at {r.failed_step} — {r.reason}"
        else:
            pr = r.pr_url or "(no PR)"
            disp = r.disposition or (r.review_status or "(no review)")
            line = f"  {r.ticket_id}: {disp} — PR {pr} — {r.rounds} round(s)"
            if r.disposition == "NEEDS_HUMAN" and r.reason:
                line += f" — {r.reason}"
```

(Keep the `if r.usage: line += f" — ${_ticket_cost(r):.4f}"` and the `_format_usage_lines` call unchanged.)

- [ ] **Step 4 — run, verify pass.** Confirm the older `TestFormatSummary` cases still pass (they use 6-arg `TicketResult` → `disposition=None`, `rounds=0`, so the line falls back to `review_status`; assertions `A-1`/`APPROVED`/`pull/1` still hold).
- [ ] **Step 5 — commit:** `feat(personal): report per-ticket disposition and rounds in the summary`

---

### Task 5: `--max-rounds` flag + dry-run output

**Files:** Modify `loop.py` (`parse_args`, `main`); Test `test_loop.py`.

- [ ] **Step 1 — failing test:**

```python
class TestMaxRoundsArg(unittest.TestCase):
    def test_flag_parsed(self):
        self.assertEqual(loop.parse_args(["--max-rounds", "2"]).max_rounds, 2)
    def test_default(self):
        self.assertEqual(loop.parse_args([]).max_rounds, loop.MAX_ROUNDS)
```

- [ ] **Step 2 — run, verify fail.**
- [ ] **Step 3 — implement.** Add to `parse_args`: `p.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)`. In `main`, pass `max_rounds=args.max_rounds` into `run_ticket_pipeline(...)`. Extend the dry-run loop to list the new steps (`reviewit ↔ addressit up to N rounds`, `mergeit`) so `--dry-run` shows the full pipeline.
- [ ] **Step 4 — run, verify pass.** Also run `python3 loop.py --project p --dry-run --tickets A-1` mentally/via test to confirm no crash (the existing `TestMainDryRun` still passes — it injects triage/guard and asserts the pipeline runner isn't called).
- [ ] **Step 5 — commit:** `feat(personal): add --max-rounds and show the full pipeline in --dry-run`

---

### Task 6: Effort feasibility (gated — may be a no-op)

**Files:** Investigation only; possibly `loop.py` (`build_claude_cmd`) + `test_loop.py`.

- [ ] **Step 1 — investigate.** Run `claude -p --help 2>&1 | grep -i effort` (and check for an effort/output-config flag on the headless CLI). Determine whether per-invocation effort is controllable from `claude -p`.
- [ ] **Step 2a — if supported:** TDD a per-step `efforts` map threaded through `build_claude_cmd(prompt, model, effort=None)` (append the documented flag when set); defaults — low: triage/shipit/mergeit; high/xhigh: implementit + round-1 reviewit; medium: addressit/re-reviews. Add a test asserting the flag appears for a step with an effort and is absent otherwise. Commit: `feat(personal): set per-step effort in the loop`.
- [ ] **Step 2b — if NOT supported:** add a one-line comment in `loop.py` near `build_claude_cmd` noting effort isn't headlessly controllable, and record it in the spec's RETUNE table as dropped. No code change. (Do not fabricate a flag.)

---

### Task 7: Progress events (`emit` callback)

**Files:** Modify `loop.py` (`run_ticket_pipeline`, `main`); Test `test_loop.py`.

**Interfaces — Produces:** `run_ticket_pipeline(..., emit=None)` calls `emit(label)` on entry to each step (`implementit`, `shipit`, `reviewit (round r)`, `addressit (round r)`, `mergeit`). Default `None` = no-op (tests stay silent).

- [ ] **Step 1 — failing test:**

```python
class TestProgressEvents(unittest.TestCase):
    def test_pipeline_emits_step_labels(self):
        seen = []
        runner = make_runner([
            loop.InvocationResult(0, "STATUS: IMPLEMENTED", False),
            loop.InvocationResult(0, "PR https://github.com/o/r/pull/1", False),
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
            loop.InvocationResult(0, "STATUS: ADDRESSED", False),
            loop.InvocationResult(0, "STATUS: APPROVED", False),
            loop.InvocationResult(0, "STATUS: MERGED", False),
        ])
        loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, emit=seen.append)
        for label in ("implementit", "shipit", "reviewit (round 1)",
                      "addressit (round 1)", "reviewit (round 2)", "mergeit"):
            self.assertIn(label, seen)
```

- [ ] **Step 2 — run, verify fail** (`emit` not accepted / labels absent).
- [ ] **Step 3 — implement.** Add `emit=None` to the `run_ticket_pipeline` signature; make the inner `step` helper emit:

```python
    def step(name, model, timeout, label=None):
        if emit:
            emit(label or name)
        res = runner(build_claude_cmd(f"/personal:{name} {tid}", model), timeout)
        usages.append(_usage_record(name, model, res.usage))
        return res
```

Pass labels at the review/address call sites: `step("reviewit", model, timeouts["reviewit"], label=f"reviewit (round {rounds})")` and `step("addressit", models["addressit"], timeouts["addressit"], label=f"addressit (round {rounds})")`.

Wire `main` (this **supersedes** Task 5's simpler `max_rounds` wiring — fold both in here). Add `from datetime import datetime, timezone` to the imports, then replace the results-list comprehension:

```python
    def emit(msg):
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

    emit(f"wave: {len(wave)} ticket(s)")
    results = []
    for i, t in enumerate(wave, 1):
        emit(f"[{i}/{len(wave)}] {t['id']}")
        r = run_ticket_pipeline(t, runner, models, timeouts, max_rounds=args.max_rounds, emit=emit)
        if r.disposition == "NEEDS_HUMAN":
            emit(f"{r.ticket_id} → NEEDS_HUMAN: {r.reason}")
        elif r.failed_step:
            emit(f"{r.ticket_id} → FAILED at {r.failed_step}")
        else:
            emit(f"{r.ticket_id} → {r.disposition}")
        results.append(r)
```

- [ ] **Step 4 — run, verify pass.**
- [ ] **Step 5 — commit:** `feat(personal): emit flushed per-step progress through the loop`

---

### Task 8: Detached run + watch command (`--detach`)

**Files:** Modify `loop.py` (`parse_args`, `main`, helpers); Test `test_loop.py`.

**Interfaces — Produces:** `--detach` flag; pure helpers `_loop_log_path(now) -> str` and `_detached_argv(argv) -> list`; `_spawn_detached(argv) -> (pid, log_path)`.

- [ ] **Step 1 — failing tests:**

```python
class TestDetach(unittest.TestCase):
    def test_flag_parsed(self):
        self.assertTrue(loop.parse_args(["--detach"]).detach)

    def test_log_path_shape(self):
        import datetime as dt
        p = loop._loop_log_path(dt.datetime(2026, 6, 26, 14, 5, 9))
        self.assertIn(os.path.join(".claude", "loop", "run-"), p)
        self.assertTrue(p.endswith(".log"))
        self.assertIn("20260626", p)

    def test_detached_argv_strips_detach(self):
        out = loop._detached_argv(["--project", "p", "--detach", "--max-rounds", "2"])
        self.assertNotIn("--detach", out)
        self.assertIn("--project", out)
        self.assertEqual(out[0], sys.executable)
```

- [ ] **Step 2 — run, verify fail.**
- [ ] **Step 3 — implement.** Add `import os` (if not present) and `--detach` to `parse_args` (`p.add_argument("--detach", action="store_true")`). Add:

```python
def _loop_log_path(now):
    return os.path.join(".claude", "loop", f"run-{now.strftime('%Y%m%dT%H%M%SZ')}.log")


def _detached_argv(argv):
    return [sys.executable, os.path.abspath(__file__)] + [a for a in argv if a != "--detach"]


def _spawn_detached(argv):
    log_path = _loop_log_path(datetime.now(timezone.utc))
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    gi = os.path.join(os.path.dirname(log_path), ".gitignore")
    if not os.path.exists(gi):
        with open(gi, "w") as f:
            f.write("*\n")
    logf = open(log_path, "w")
    proc = subprocess.Popen(_detached_argv(argv), stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    return proc.pid, log_path
```

In `main`, immediately after `args = parse_args(argv)` (before the feasibility guard, so the foreground call returns at once and the child runs the guard):

```python
    if args.detach:
        pid, log_path = _spawn_detached(argv)
        print(f"Loop started (pid {pid}).")
        print(f"Watch: tail -f {log_path}")
        return 0
```

- [ ] **Step 4 — run, verify pass** (`python3 -m pytest test_loop.py -q`). Manual acceptance: `python3 loop.py --project X --detach` prints a `tail -f …/run-*.log` command and returns immediately; tailing that file shows the flushed progress lines from Task 7.
- [ ] **Step 5 — commit:** `feat(personal): add --detach to run the loop in the background with a watch command`

---

### Task 9: Version bump + consistency check

**Files:** Modify `plugins/personal/.claude-plugin/plugin.json`.

- [ ] **Step 1 — bump** the `version` minor (from whatever is current on `main` after #11 — e.g. `0.6.0 → 0.7.0`). Also confirm `.claude/loop/.gitignore` (written at runtime by `_spawn_detached`) is not accidentally tracked.
- [ ] **Step 2 — verify.** Run: `python3 -m pytest plugins/personal/scripts/test_loop.py -q` (all green) and `git diff --name-only main -- plugins/personal/commands/` (empty — no command changes).
- [ ] **Step 3 — commit:** `chore(personal): bump plugin for the autonomous loop`

---

## Self-Review (plan author)

- **Spec coverage:** §3 state machine → Task 3. §4 parsers → Task 1. §5 max-rounds → Tasks 3+5. §6 model routing → Tasks 2+3; effort → Task 6; max-rounds → Task 5; caching → non-task. §7 reporting → Tasks 2+4. §8 testing → woven into each task. §9 execution & observability → Tasks 7 (progress) + 8 (detached). §10 version → Task 9. Covered. (Task 7's `main` loop supersedes the simpler `max_rounds` wiring sketched in Task 5 Step 3 — fold both in there.)
- **Backward-compat:** `TicketResult` new fields are defaulted (Task 2); legacy 6-arg constructors in `TestFormatSummary` keep working; pipeline tests that drove APPROVED/CHANGES to a terminal state are explicitly rewritten in Task 3 Step 1 (behavior changed by design).
- **Placeholder scan:** Task 6 is intentionally conditional (real feasibility gate), not a TODO. All other steps have concrete code/commands.
- **Consistency:** sentinel strings and `disposition` values match the spec; `default_models`/`default_timeouts` are the single source for both `main` and tests.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
