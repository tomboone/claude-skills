# Implementation Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `plugins/personal/scripts/loop.py`, a headless Python orchestrator that drives `/implementit → /shipit → /reviewit` via `claude -p` for one wave of `loop-ready` Linear tickets per run (stopping before merge), plus add a machine-readable `STATUS:` line to `/reviewit`.

**Architecture:** A single stdlib-only Python script composed of small pure functions (triage-result parsing, command building, outcome classification, summary formatting, and a pipeline state machine that takes an **injectable runner**) plus a thin integration layer (real `subprocess` runner, triage call, feasibility guard, `argparse`/`main`). The pure functions and the pipeline are unit-tested with `unittest`; the live-`claude -p` path is exercised via `--dry-run` and a user-run end-to-end test.

**Tech Stack:** Python 3 standard library only (`subprocess`, `json`, `argparse`, `re`, `collections`, `unittest`) — no third-party dependencies. `claude -p` CLI; Linear + GitHub MCP (used by the invoked commands, not by the script directly).

## Global Constraints

These apply to every task; values copied verbatim from the spec.

- Script path: `plugins/personal/scripts/loop.py`. Tests: `plugins/personal/scripts/test_loop.py` (flat, alongside, so `import loop` works). Run tests with: `cd plugins/personal/scripts && python3 -m unittest test_loop -v`.
- **Standard library only** — no `pip` dependencies, in script or tests.
- Pipeline per ticket is exactly `/personal:implementit` → `/personal:shipit` → `/personal:reviewit`. **Never** `/mergeit` (stop before merge).
- Each step is an **independent** `claude -p` invocation: flags `--output-format json --permission-mode bypassPermissions --model <model>`. **No** `--resume`, **no** `--bare`, **no** `--max-turns` (not a real flag).
- Models: `implementit`→`sonnet`, `shipit`→`sonnet`, `reviewit`→`opus`, triage→`sonnet`, feasibility guard→`haiku`.
- Triage selects tickets that are `loop-ready` **and** have every `blockedBy` blocker `Done` **and** are still un-started (`Todo`/`Backlog`). Returns JSON `{"project", "wave":[{id,title}], "held":[{id,title,waiting_on}]}`. Parser extracts the **last** JSON object from the result text.
- Project resolution is non-interactive: `--project`, else repo `CLAUDE.md` `linear_initiative`/`linear_team` hints; else abort.
- Hard failure = nonzero exit **or** timeout **or** `shipit` produced no PR URL. On hard failure: record + skip the ticket's remaining steps, continue. No PR → skip `reviewit`. A review verdict of `CHANGES_REQUESTED` is **not** a failure.
- `/reviewit` emits a final line `STATUS: APPROVED` or `STATUS: CHANGES_REQUESTED` (mapped from its existing "Ready to merge" / "Needs changes" assessment).
- Exit code: `0` if the run completed (even with skipped tickets); nonzero only if the loop could not run at all (guard or triage failed).
- Commit messages: Conventional Commits, no Linear parenthetical (no ticket maps to this work), **no footer**, no co-author.

---

## File Structure

**Create:**
- `plugins/personal/scripts/loop.py` — the orchestrator (built across Tasks 2–6).
- `plugins/personal/scripts/test_loop.py` — `unittest` tests (added per task).

**Modify:**
- `plugins/personal/commands/reviewit.md` — add the `STATUS:` line (Task 1).

**Shared data types** (defined in `loop.py` in Task 2, used throughout):

```python
from collections import namedtuple
InvocationResult = namedtuple("InvocationResult", ["returncode", "result_text", "timed_out"])
TicketResult = namedtuple("TicketResult", ["ticket_id", "implemented", "pr_url", "review_status", "failed_step", "reason"])
```

---

## Task 1: `/reviewit` machine-readable STATUS line

**Files:**
- Modify: `plugins/personal/commands/reviewit.md`

**Interfaces:**
- Produces: a final response line `STATUS: APPROVED` or `STATUS: CHANGES_REQUESTED` that the loop's `parse_review_status` (Task 2) reads.

- [ ] **Step 1: Add the STATUS instruction**

Read `reviewit.md`. In the final step (where it tells the user the assessment), add an instruction to emit, as the **last line of the response**, exactly one of:

```
STATUS: APPROVED
STATUS: CHANGES_REQUESTED
```

Map it from the existing assessment: "Ready to merge" → `STATUS: APPROVED`; any Critical/Important issues ("Needs changes") → `STATUS: CHANGES_REQUESTED`. Keep the existing human-facing assessment and the posted PR comment unchanged — this is one additional line.

- [ ] **Step 2: Validate (structural — no test framework for prose)**

Re-read `reviewit.md`. Confirm: (a) both token spellings appear exactly as above; (b) the mapping from the existing assessment is stated; (c) it is the last line of the response (lands in `--output-format json` `result`); (d) interactive behavior is otherwise unchanged.

- [ ] **Step 3: Commit**

```bash
git add plugins/personal/commands/reviewit.md
git commit -m "feat: emit machine-readable STATUS line from reviewit"
```

---

## Task 2: Data types + triage/review result parsers

**Files:**
- Create: `plugins/personal/scripts/loop.py`
- Create: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Produces:
  - `InvocationResult`, `TicketResult` namedtuples (signatures above).
  - `parse_triage_result(result_text: str) -> dict` → normalized `{"project": str|None, "wave": list[dict], "held": list[dict]}`; raises `ValueError` if no JSON object is present.
  - `parse_review_status(result_text: str) -> str | None` → `"APPROVED"`, `"CHANGES_REQUESTED"`, or `None`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/personal/scripts/test_loop.py`:

```python
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loop


class TestParseTriageResult(unittest.TestCase):
    def test_clean_json(self):
        text = '{"project": "p", "wave": [{"id": "A-1", "title": "t"}], "held": []}'
        out = loop.parse_triage_result(text)
        self.assertEqual(out["project"], "p")
        self.assertEqual(out["wave"], [{"id": "A-1", "title": "t"}])
        self.assertEqual(out["held"], [])

    def test_json_with_surrounding_prose(self):
        text = 'Here is the wave:\n{"project": "p", "wave": [], "held": []}\nDone.'
        out = loop.parse_triage_result(text)
        self.assertEqual(out["wave"], [])

    def test_returns_last_json_object(self):
        text = '{"project": "old", "wave": [], "held": []} ... {"project": "new", "wave": [], "held": []}'
        self.assertEqual(loop.parse_triage_result(text)["project"], "new")

    def test_missing_keys_default_to_empty(self):
        out = loop.parse_triage_result('{"project": "p"}')
        self.assertEqual(out["wave"], [])
        self.assertEqual(out["held"], [])

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            loop.parse_triage_result("no json here")


class TestParseReviewStatus(unittest.TestCase):
    def test_approved(self):
        self.assertEqual(loop.parse_review_status("...\nSTATUS: APPROVED"), "APPROVED")

    def test_changes_requested(self):
        self.assertEqual(loop.parse_review_status("x STATUS: CHANGES_REQUESTED x"), "CHANGES_REQUESTED")

    def test_changes_requested_wins_when_both_present(self):
        # defensive: if both somehow appear, treat as changes requested
        self.assertEqual(loop.parse_review_status("STATUS: APPROVED\nSTATUS: CHANGES_REQUESTED"), "CHANGES_REQUESTED")

    def test_none_when_absent(self):
        self.assertIsNone(loop.parse_review_status("no status line"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/personal/scripts && python3 -m unittest test_loop -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'loop'` (or `AttributeError` once the file exists).

- [ ] **Step 3: Write minimal implementation**

Create `plugins/personal/scripts/loop.py`:

```python
#!/usr/bin/env python3
"""Headless orchestrator: runs /implementit -> /shipit -> /reviewit per loop-ready ticket."""
import json
import re
from collections import namedtuple

InvocationResult = namedtuple("InvocationResult", ["returncode", "result_text", "timed_out"])
TicketResult = namedtuple("TicketResult", ["ticket_id", "implemented", "pr_url", "review_status", "failed_step", "reason"])


def parse_triage_result(result_text):
    """Extract the last JSON object from triage output; normalize keys."""
    text = (result_text or "").strip()
    decoder = json.JSONDecoder()
    last = None
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = decoder.raw_decode(text[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                last = obj
    if last is None:
        raise ValueError("no JSON object found in triage result")
    return {
        "project": last.get("project"),
        "wave": last.get("wave", []),
        "held": last.get("held", []),
    }


def parse_review_status(result_text):
    """Return APPROVED / CHANGES_REQUESTED / None from a /reviewit result."""
    if "STATUS: CHANGES_REQUESTED" in (result_text or ""):
        return "CHANGES_REQUESTED"
    if "STATUS: APPROVED" in (result_text or ""):
        return "APPROVED"
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/personal/scripts && python3 -m unittest test_loop -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat: add triage and review-status parsers to loop"
```

---

## Task 3: Command builder + outcome classifier

**Files:**
- Modify: `plugins/personal/scripts/loop.py`
- Modify: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Consumes: `shipit` PR detection used by `classify_outcome`.
- Produces:
  - `build_claude_cmd(prompt: str, model: str) -> list[str]` → argv with `claude -p <prompt> --model <model> --output-format json --permission-mode bypassPermissions`.
  - `shipit_pr_url(result_text: str) -> str | None`.
  - `classify_outcome(returncode: int, result_text: str, timed_out: bool, step: str) -> tuple[bool, str]` → `(ok, reason)`.

- [ ] **Step 1: Write the failing tests**

Append to `test_loop.py`:

```python
class TestBuildClaudeCmd(unittest.TestCase):
    def test_includes_required_flags(self):
        cmd = loop.build_claude_cmd("/personal:implementit A-1", "sonnet")
        self.assertEqual(cmd[:3], ["claude", "-p", "/personal:implementit A-1"])
        self.assertIn("--output-format", cmd)
        self.assertIn("json", cmd)
        self.assertIn("--permission-mode", cmd)
        self.assertIn("bypassPermissions", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "sonnet")

    def test_excludes_forbidden_flags(self):
        cmd = loop.build_claude_cmd("/personal:reviewit A-1", "opus")
        self.assertNotIn("--resume", cmd)
        self.assertNotIn("--bare", cmd)
        self.assertNotIn("--max-turns", cmd)


class TestShipitPrUrl(unittest.TestCase):
    def test_finds_pr_url(self):
        text = "Opened PR: https://github.com/tomboone/repo/pull/42 ready for review"
        self.assertEqual(loop.shipit_pr_url(text), "https://github.com/tomboone/repo/pull/42")

    def test_none_when_absent(self):
        self.assertIsNone(loop.shipit_pr_url("no url"))


class TestClassifyOutcome(unittest.TestCase):
    def test_timeout_is_hard_fail(self):
        ok, reason = loop.classify_outcome(0, "", True, "implementit")
        self.assertFalse(ok)
        self.assertIn("timed out", reason)

    def test_nonzero_exit_is_hard_fail(self):
        ok, reason = loop.classify_outcome(1, "", False, "implementit")
        self.assertFalse(ok)
        self.assertIn("exited 1", reason)

    def test_shipit_without_pr_is_hard_fail(self):
        ok, reason = loop.classify_outcome(0, "no pr here", False, "shipit")
        self.assertFalse(ok)
        self.assertIn("no PR", reason)

    def test_shipit_with_pr_is_ok(self):
        ok, _ = loop.classify_outcome(0, "https://github.com/o/r/pull/1", False, "shipit")
        self.assertTrue(ok)

    def test_implementit_zero_exit_is_ok(self):
        ok, _ = loop.classify_outcome(0, "done", False, "implementit")
        self.assertTrue(ok)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/personal/scripts && python3 -m unittest test_loop -v`
Expected: FAIL — `AttributeError: module 'loop' has no attribute 'build_claude_cmd'`.

- [ ] **Step 3: Write minimal implementation**

Append to `loop.py`:

```python
_PR_RE = re.compile(r"https://github\.com/[^\s)]+/pull/\d+")


def build_claude_cmd(prompt, model):
    return [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "json",
        "--permission-mode", "bypassPermissions",
    ]


def shipit_pr_url(result_text):
    m = _PR_RE.search(result_text or "")
    return m.group(0) if m else None


def classify_outcome(returncode, result_text, timed_out, step):
    if timed_out:
        return (False, f"{step} timed out")
    if returncode != 0:
        return (False, f"{step} exited {returncode}")
    if step == "shipit" and shipit_pr_url(result_text) is None:
        return (False, "shipit produced no PR URL")
    return (True, "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/personal/scripts && python3 -m unittest test_loop -v`
Expected: PASS (all prior + 9 new).

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat: add claude command builder and outcome classifier"
```

---

## Task 4: Summary formatter

**Files:**
- Modify: `plugins/personal/scripts/loop.py`
- Modify: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Consumes: `TicketResult` (Task 2).
- Produces: `format_summary(results: list[TicketResult], held: list[dict]) -> str`.

- [ ] **Step 1: Write the failing tests**

Append to `test_loop.py`:

```python
class TestFormatSummary(unittest.TestCase):
    def test_renders_success_and_failure_and_held(self):
        results = [
            loop.TicketResult("A-1", True, "https://github.com/o/r/pull/1", "APPROVED", None, None),
            loop.TicketResult("A-2", True, None, None, "shipit", "shipit produced no PR URL"),
        ]
        held = [{"id": "A-3", "title": "later", "waiting_on": ["A-1"]}]
        out = loop.format_summary(results, held)
        self.assertIn("A-1", out)
        self.assertIn("pull/1", out)
        self.assertIn("APPROVED", out)
        self.assertIn("A-2", out)
        self.assertIn("shipit", out)          # failed step shown
        self.assertIn("A-3", out)             # held shown
        self.assertIn("A-1", out)             # waiting_on shown

    def test_empty_wave_message(self):
        out = loop.format_summary([], [])
        self.assertIn("no", out.lower())      # e.g. "no tickets processed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/personal/scripts && python3 -m unittest test_loop -v`
Expected: FAIL — `AttributeError: module 'loop' has no attribute 'format_summary'`.

- [ ] **Step 3: Write minimal implementation**

Append to `loop.py`:

```python
def format_summary(results, held):
    lines = ["", "=== Loop run summary ==="]
    if not results:
        lines.append("No tickets processed.")
    for r in results:
        if r.failed_step:
            lines.append(f"  {r.ticket_id}: FAILED at {r.failed_step} — {r.reason}")
        else:
            pr = r.pr_url or "(no PR)"
            review = r.review_status or "(no review)"
            lines.append(f"  {r.ticket_id}: PR {pr} — review {review}")
    if held:
        lines.append("Held for a future run (blockers not yet merged):")
        for h in held:
            waiting = ", ".join(h.get("waiting_on", [])) or "?"
            lines.append(f"  {h.get('id')}: waiting on {waiting}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/personal/scripts && python3 -m unittest test_loop -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat: add run summary formatter"
```

---

## Task 5: Per-ticket pipeline (injectable runner)

**Files:**
- Modify: `plugins/personal/scripts/loop.py`
- Modify: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Consumes: `build_claude_cmd`, `classify_outcome`, `shipit_pr_url`, `parse_review_status`, `TicketResult`, `InvocationResult`.
- Produces: `run_ticket_pipeline(ticket: dict, runner, models: dict, timeouts: dict) -> TicketResult`, where `runner(cmd: list[str], timeout: int) -> InvocationResult`. `models` keys: `implementit`/`shipit`/`reviewit`. `timeouts` same keys.

- [ ] **Step 1: Write the failing tests**

Append to `test_loop.py`:

```python
MODELS = {"implementit": "sonnet", "shipit": "sonnet", "reviewit": "opus"}
TIMEOUTS = {"implementit": 1800, "shipit": 600, "reviewit": 900}


def make_runner(scripted):
    """scripted: list of InvocationResult returned in order per call."""
    calls = {"cmds": []}
    seq = iter(scripted)
    def runner(cmd, timeout):
        calls["cmds"].append(cmd)
        return next(seq)
    runner.calls = calls
    return runner


class TestRunTicketPipeline(unittest.TestCase):
    def test_all_steps_succeed(self):
        runner = make_runner([
            loop.InvocationResult(0, "implemented", False),
            loop.InvocationResult(0, "PR https://github.com/o/r/pull/7", False),
            loop.InvocationResult(0, "review done\nSTATUS: APPROVED", False),
        ])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertTrue(r.implemented)
        self.assertEqual(r.pr_url, "https://github.com/o/r/pull/7")
        self.assertEqual(r.review_status, "APPROVED")
        self.assertIsNone(r.failed_step)
        self.assertEqual(len(runner.calls["cmds"]), 3)

    def test_implement_failure_skips_rest(self):
        runner = make_runner([loop.InvocationResult(1, "", False)])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertFalse(r.implemented)
        self.assertEqual(r.failed_step, "implementit")
        self.assertEqual(len(runner.calls["cmds"]), 1)   # ship/review never run

    def test_ship_failure_skips_review(self):
        runner = make_runner([
            loop.InvocationResult(0, "implemented", False),
            loop.InvocationResult(0, "no pr produced", False),
        ])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertTrue(r.implemented)
        self.assertIsNone(r.pr_url)
        self.assertEqual(r.failed_step, "shipit")
        self.assertEqual(len(runner.calls["cmds"]), 2)   # review never run

    def test_changes_requested_is_not_a_failure(self):
        runner = make_runner([
            loop.InvocationResult(0, "implemented", False),
            loop.InvocationResult(0, "PR https://github.com/o/r/pull/8", False),
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
        ])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertIsNone(r.failed_step)
        self.assertEqual(r.review_status, "CHANGES_REQUESTED")
        self.assertEqual(r.pr_url, "https://github.com/o/r/pull/8")

    def test_uses_correct_models(self):
        runner = make_runner([
            loop.InvocationResult(0, "x", False),
            loop.InvocationResult(0, "https://github.com/o/r/pull/9", False),
            loop.InvocationResult(0, "STATUS: APPROVED", False),
        ])
        loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        cmds = runner.calls["cmds"]
        self.assertEqual(cmds[0][cmds[0].index("--model") + 1], "sonnet")   # implementit
        self.assertEqual(cmds[2][cmds[2].index("--model") + 1], "opus")     # reviewit
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/personal/scripts && python3 -m unittest test_loop -v`
Expected: FAIL — `AttributeError: module 'loop' has no attribute 'run_ticket_pipeline'`.

- [ ] **Step 3: Write minimal implementation**

Append to `loop.py`:

```python
def run_ticket_pipeline(ticket, runner, models, timeouts):
    tid = ticket["id"]

    res = runner(build_claude_cmd(f"/personal:implementit {tid}", models["implementit"]), timeouts["implementit"])
    ok, reason = classify_outcome(res.returncode, res.result_text, res.timed_out, "implementit")
    if not ok:
        return TicketResult(tid, False, None, None, "implementit", reason)

    res = runner(build_claude_cmd(f"/personal:shipit {tid}", models["shipit"]), timeouts["shipit"])
    ok, reason = classify_outcome(res.returncode, res.result_text, res.timed_out, "shipit")
    if not ok:
        return TicketResult(tid, True, None, None, "shipit", reason)
    pr_url = shipit_pr_url(res.result_text)

    res = runner(build_claude_cmd(f"/personal:reviewit {tid}", models["reviewit"]), timeouts["reviewit"])
    ok, reason = classify_outcome(res.returncode, res.result_text, res.timed_out, "reviewit")
    if not ok:
        return TicketResult(tid, True, pr_url, None, "reviewit", reason)

    return TicketResult(tid, True, pr_url, parse_review_status(res.result_text), None, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/personal/scripts && python3 -m unittest test_loop -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat: add per-ticket pipeline state machine"
```

---

## Task 6: Integration layer — real runner, triage, guard, project resolution, main

**Files:**
- Modify: `plugins/personal/scripts/loop.py`
- Modify: `plugins/personal/scripts/test_loop.py`

**Interfaces:**
- Consumes: everything from Tasks 2–5.
- Produces:
  - `subprocess_runner(cmd, timeout) -> InvocationResult` (real `claude -p`; parses `result` out of `--output-format json` stdout; sets `timed_out=True` on `subprocess.TimeoutExpired`).
  - `run_triage(project, label, runner) -> dict` (builds the triage prompt, runs it on `sonnet`, returns `parse_triage_result(...)`).
  - `feasibility_guard(runner) -> tuple[bool, str]` (runs a trivial `claude -p` on `haiku`; returns `(ok, message)`).
  - `resolve_project(args, read_claude_md) -> str` (`--project`, else `linear_initiative`/`linear_team` hint via the injected `read_claude_md() -> str`; raises `SystemExit` with a clear message if unresolved).
  - `main(argv) -> int`.

- [ ] **Step 1: Write the failing tests (unit-testable seams)**

Append to `test_loop.py`:

```python
class TestResolveProject(unittest.TestCase):
    def test_explicit_flag_wins(self):
        args = loop.parse_args(["--project", "myproj"])
        self.assertEqual(loop.resolve_project(args, lambda: ""), "myproj")

    def test_falls_back_to_claude_md_hint(self):
        args = loop.parse_args([])
        md = "specs_dir: docs\nlinear_initiative: BigApp\nlinear_team: ENG\n"
        self.assertEqual(loop.resolve_project(args, lambda: md), "BigApp")

    def test_aborts_when_unresolvable(self):
        args = loop.parse_args([])
        with self.assertRaises(SystemExit):
            loop.resolve_project(args, lambda: "no hints here")


class TestSubprocessRunnerParsing(unittest.TestCase):
    def test_extracts_result_field(self):
        # _result_from_stdout is the pure JSON-extraction half of subprocess_runner
        stdout = '{"session_id": "s", "result": "the answer", "total_cost_usd": 0.1}'
        self.assertEqual(loop._result_from_stdout(stdout), "the answer")

    def test_missing_result_returns_empty(self):
        self.assertEqual(loop._result_from_stdout("not json"), "")


class TestMainDryRun(unittest.TestCase):
    def test_dry_run_prints_commands_without_running_pipeline(self):
        # inject a triage that returns a 1-ticket wave; a recording runner that must NOT be
        # called for the pipeline in dry-run.
        wave = {"project": "p", "wave": [{"id": "A-1", "title": "t"}], "held": []}
        calls = []
        rc = loop.main(
            ["--project", "p", "--dry-run"],
            runner=lambda cmd, timeout: calls.append(cmd) or loop.InvocationResult(0, "", False),
            triage_fn=lambda project, label, runner: wave,
            guard_fn=lambda runner: (True, "ok"),
        )
        self.assertEqual(rc, 0)
        # dry-run may call triage/guard via injected fns (not runner); pipeline must not run:
        self.assertEqual(calls, [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd plugins/personal/scripts && python3 -m unittest test_loop -v`
Expected: FAIL — `AttributeError` on `parse_args` / `resolve_project` / `_result_from_stdout` / `main` signature.

- [ ] **Step 3: Write minimal implementation**

Append to `loop.py`:

```python
import argparse
import subprocess
import sys

TRIAGE_PROMPT = (
    "Using the Linear MCP, find work tickets in project {project!r} that are ready for the "
    "implementation loop: they carry the {label!r} label, every one of their blockedBy blockers "
    "has status Done, and the ticket itself is still un-started (status Todo or Backlog, not "
    "In Progress/In Review/Done). Return ONLY a JSON object as your final message, no prose:\n"
    '{{"project": "{project}", "wave": [{{"id": "...", "title": "..."}}], '
    '"held": [{{"id": "...", "title": "...", "waiting_on": ["..."]}}]}}'
)


def parse_args(argv):
    p = argparse.ArgumentParser(description="Run one wave of loop-ready tickets through implement/ship/review.")
    p.add_argument("--project")
    p.add_argument("--label", default="loop-ready")
    p.add_argument("--tickets", nargs="*")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--notify", action="store_true")
    return p.parse_args(argv)


def _result_from_stdout(stdout):
    try:
        return json.loads(stdout).get("result", "") or ""
    except (json.JSONDecodeError, AttributeError):
        return ""


def subprocess_runner(cmd, timeout):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return InvocationResult(proc.returncode, _result_from_stdout(proc.stdout), False)
    except subprocess.TimeoutExpired:
        return InvocationResult(-1, "", True)


def _read_repo_claude_md():
    for name in ("CLAUDE.md", ".claude/CLAUDE.md"):
        try:
            with open(name, "r") as f:
                return f.read()
        except OSError:
            continue
    return ""


def resolve_project(args, read_claude_md=_read_repo_claude_md):
    if args.project:
        return args.project
    for line in read_claude_md().splitlines():
        if line.strip().lower().startswith("linear_initiative:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("Cannot resolve project: pass --project or set 'linear_initiative:' in the repo CLAUDE.md.")


def feasibility_guard(runner):
    res = runner(build_claude_cmd("Reply with exactly: LOOP_OK", "haiku"), 120)
    if res.timed_out or res.returncode != 0:
        return (False, "claude -p did not run (check CLI/auth/MCP availability)")
    if "LOOP_OK" not in (res.result_text or ""):
        return (False, f"unexpected guard output: {res.result_text!r}")
    return (True, "ok")


def run_triage(project, label, runner):
    res = runner(build_claude_cmd(TRIAGE_PROMPT.format(project=project, label=label), "sonnet"), 300)
    if res.timed_out or res.returncode != 0:
        raise SystemExit("Triage call failed.")
    return parse_triage_result(res.result_text)


def main(argv, runner=subprocess_runner, triage_fn=run_triage, guard_fn=feasibility_guard):
    args = parse_args(argv)
    models = {"implementit": "sonnet", "shipit": "sonnet", "reviewit": "opus"}
    timeouts = {"implementit": 1800, "shipit": 600, "reviewit": 900}

    ok, msg = guard_fn(runner)
    if not ok:
        print(f"Feasibility check failed: {msg}", file=sys.stderr)
        return 2
    if args.check:
        print("Feasibility check passed.")
        return 0

    project = resolve_project(args)
    if args.tickets:
        triage = {"project": project, "wave": [{"id": t, "title": ""} for t in args.tickets], "held": []}
    else:
        triage = triage_fn(project, args.label, runner)

    wave = triage["wave"][: args.limit] if args.limit else triage["wave"]

    if args.dry_run:
        print(f"Project: {project}. Wave ({len(wave)}): {[t['id'] for t in wave]}")
        for t in wave:
            for step, model in (("implementit", models["implementit"]), ("shipit", models["shipit"]), ("reviewit", models["reviewit"])):
                print("  would run:", " ".join(build_claude_cmd(f"/personal:{step} {t['id']}", model)))
        print(format_summary([], triage["held"]))
        return 0

    results = [run_ticket_pipeline(t, runner, models, timeouts) for t in wave]
    print(format_summary(results, triage["held"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd plugins/personal/scripts && python3 -m unittest test_loop -v`
Expected: PASS (all tasks' tests).

- [ ] **Step 5: Make the script executable and smoke-check `--help`**

Run:
```bash
chmod +x plugins/personal/scripts/loop.py
python3 plugins/personal/scripts/loop.py --help
```
Expected: argparse usage text prints, exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/personal/scripts/loop.py plugins/personal/scripts/test_loop.py
git commit -m "feat: add loop integration layer (runner, triage, guard, main)"
```

---

## Task 7: End-to-end validation + permission spike (user-run)

**Files:** none (validation only)

**Interfaces:**
- Consumes: the finished `loop.py`, the modified `/reviewit`, and a `/projectit` sandbox project with `loop-ready` tickets.

- [ ] **Step 1: Permission/feasibility spike**

Manually confirm the load-bearing assumptions the unit tests cannot:
- `claude -p "/personal:implementit <id>"` actually resolves the plugin command headless (run `python3 plugins/personal/scripts/loop.py --check` from a repo).
- Linear + GitHub MCP are reachable under `claude -p`.
- **Deny-rules survive `--permission-mode bypassPermissions`:** in a scratch repo, run `claude -p "merge PR #<n>" --permission-mode bypassPermissions` (or another guardrail-blocked op) and confirm it is refused. If deny-rules do NOT survive bypass, stop and revisit the permission model before any real run.

- [ ] **Step 2: Dry-run against the sandbox**

From the sandbox app repo: `python3 .../loop.py --project <sandbox> --dry-run`. Confirm the wave matches the `loop-ready`, unblocked, un-started tickets and the printed commands are correct.

- [ ] **Step 3: Real one-wave run**

`python3 .../loop.py --project <sandbox> --limit 1`. Confirm: a feature branch + PR is opened for the ticket, `/reviewit` posts a comment with a `STATUS:` line, the ticket moved to In Review (so a re-run won't repick it), and the summary is accurate. Do NOT merge (loop stops before merge by design).

- [ ] **Step 4: Re-run idempotency check**

Run the loop again. Confirm the just-processed ticket is excluded (now In Review, not un-started) and only genuinely new/unblocked tickets appear.

- [ ] **Step 5: Clean up the sandbox**

Close the test PR(s), delete the branch(es), and archive/reset the sandbox tickets.

---

## Self-Review

**Spec coverage** (spec section → task):
- `loop.py` script + CLI → Tasks 2–6 (CLI in Task 6).
- Run flow (guard → triage → pipeline → summary) → Task 6 `main`, composing Tasks 2–5.
- Triage (label + blockers Done + un-started; JSON `{project,wave,held}`; last-JSON parse) → Task 2 (`parse_triage_result`) + Task 6 (`run_triage` prompt).
- Per-ticket pipeline (independent `claude -p`; bypassPermissions; models; skip-on-failure; no-PR→skip review; CHANGES_REQUESTED not a failure) → Task 5 + Task 3 (cmd/flags/classifier).
- Wall-clock timeout instead of `--max-turns` → Task 5/6 (`timeouts`, `subprocess_runner` TimeoutExpired).
- Non-interactive project resolution → Task 6 (`resolve_project`).
- Feasibility guard → Task 6 (`feasibility_guard`) + Task 7 (spike incl. deny-rule check).
- `/reviewit` STATUS line → Task 1; consumed by `parse_review_status` (Task 2) / pipeline (Task 5).
- Summary + exit codes → Task 4 + Task 6 (`main` returns 0 / 2).
- `--dry-run` / `--check` → Task 6.
- Notifications (optional) → flag parsed in Task 6; emission deferred (optional per spec) — acceptable, not wired, matches "lowest priority / may ship in a follow-up."

**Placeholder scan:** No TBD/"handle edge cases"/"similar to" placeholders; every code step shows complete code, every test step shows real assertions and the run command + expected result.

**Type consistency:** `InvocationResult(returncode, result_text, timed_out)` and `TicketResult(ticket_id, implemented, pr_url, review_status, failed_step, reason)` are defined once (Task 2) and used identically in Tasks 4–6. `build_claude_cmd(prompt, model)`, `classify_outcome(returncode, result_text, timed_out, step) -> (ok, reason)`, `run_ticket_pipeline(ticket, runner, models, timeouts)`, and `main(argv, runner, triage_fn, guard_fn)` signatures match across their defining and consuming tasks. `--notify` is parsed but intentionally not yet emitting (documented above).
