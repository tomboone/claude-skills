import os
import sys
import unittest
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

    def test_implementit_without_completion_sentinel_is_hard_fail(self):
        # exit 0 alone is not enough — implementit bails with code 0 (e.g. no plan found)
        ok, reason = loop.classify_outcome(0, "done", False, "implementit")
        self.assertFalse(ok)
        self.assertIn("did not complete", reason)

    def test_implementit_no_plan_sentinel_gives_clear_reason(self):
        ok, reason = loop.classify_outcome(0, "...\nSTATUS: NO_PLAN", False, "implementit")
        self.assertFalse(ok)
        self.assertIn("planit", reason.lower())

    def test_implementit_with_completion_sentinel_is_ok(self):
        ok, _ = loop.classify_outcome(0, "all tasks done\nSTATUS: IMPLEMENTED", False, "implementit")
        self.assertTrue(ok)


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
        self.assertIn("waiting on A-1", out) # waiting_on shown

    def test_empty_wave_message(self):
        out = loop.format_summary([], [])
        self.assertIn("no", out.lower())      # e.g. "no tickets processed"


class TestTicketResultShape(unittest.TestCase):
    def test_disposition_and_rounds_default(self):
        r = loop.TicketResult("A-1", True, None, None, None, None)  # 6-arg legacy
        self.assertIsNone(r.disposition)
        self.assertEqual(r.rounds, 0)
    def test_main_models_have_loop_keys(self):
        models = loop.default_models()
        for k in ("reviewit_rereview", "addressit", "mergeit"):
            self.assertIn(k, models)


MODELS = loop.default_models()
TIMEOUTS = loop.default_timeouts()


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
            loop.InvocationResult(0, "implemented\nSTATUS: IMPLEMENTED", False),
            loop.InvocationResult(0, "PR https://github.com/o/r/pull/7", False),
            loop.InvocationResult(0, "review done\nSTATUS: APPROVED", False),
            loop.InvocationResult(0, "STATUS: MERGED", False),
        ])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertTrue(r.implemented)
        self.assertEqual(r.pr_url, "https://github.com/o/r/pull/7")
        self.assertEqual(r.review_status, "APPROVED")
        self.assertIsNone(r.failed_step)
        self.assertEqual(r.disposition, "MERGED")
        self.assertEqual(len(runner.calls["cmds"]), 4)

    def test_implement_failure_skips_rest(self):
        runner = make_runner([loop.InvocationResult(1, "", False)])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertFalse(r.implemented)
        self.assertEqual(r.failed_step, "implementit")
        self.assertEqual(len(runner.calls["cmds"]), 1)   # ship/review/merge never run

    def test_implement_noop_without_sentinel_skips_rest(self):
        # exit 0 but no STATUS: IMPLEMENTED — e.g. implementit found no plan and bailed
        runner = make_runner([loop.InvocationResult(0, "no plan; run planit\nSTATUS: NO_PLAN", False)])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertFalse(r.implemented)
        self.assertEqual(r.failed_step, "implementit")
        self.assertEqual(len(runner.calls["cmds"]), 1)   # ship/review/merge never run

    def test_ship_failure_skips_review(self):
        runner = make_runner([
            loop.InvocationResult(0, "implemented\nSTATUS: IMPLEMENTED", False),
            loop.InvocationResult(0, "no pr produced", False),
        ])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertTrue(r.implemented)
        self.assertIsNone(r.pr_url)
        self.assertEqual(r.failed_step, "shipit")
        self.assertEqual(len(runner.calls["cmds"]), 2)   # review/merge never run

    def test_changes_requested_is_not_a_failure(self):
        # CHANGES_REQUESTED → addressit → re-review → merge
        runner = make_runner([
            loop.InvocationResult(0, "implemented\nSTATUS: IMPLEMENTED", False),
            loop.InvocationResult(0, "PR https://github.com/o/r/pull/8", False),
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
            loop.InvocationResult(0, "STATUS: ADDRESSED", False),
            loop.InvocationResult(0, "STATUS: APPROVED", False),
            loop.InvocationResult(0, "STATUS: MERGED", False),
        ])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertIsNone(r.failed_step)
        self.assertEqual(r.review_status, "APPROVED")
        self.assertEqual(r.pr_url, "https://github.com/o/r/pull/8")
        self.assertEqual(r.disposition, "MERGED")

    def test_uses_correct_models(self):
        runner = make_runner([
            loop.InvocationResult(0, "x\nSTATUS: IMPLEMENTED", False),
            loop.InvocationResult(0, "https://github.com/o/r/pull/9", False),
            loop.InvocationResult(0, "STATUS: APPROVED", False),
            loop.InvocationResult(0, "STATUS: MERGED", False),
        ])
        loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        cmds = runner.calls["cmds"]
        self.assertEqual(cmds[0][cmds[0].index("--model") + 1], "sonnet")   # implementit
        self.assertEqual(cmds[2][cmds[2].index("--model") + 1], "opus")     # reviewit round 1
        self.assertEqual(cmds[3][cmds[3].index("--model") + 1], "haiku")    # mergeit


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


class TestUsageFromStdout(unittest.TestCase):
    def test_extracts_cost_and_tokens(self):
        stdout = (
            '{"result": "x", "total_cost_usd": 0.42, '
            '"usage": {"input_tokens": 1000, "output_tokens": 200, '
            '"cache_read_input_tokens": 800, "cache_creation_input_tokens": 50}}'
        )
        u = loop._usage_from_stdout(stdout)
        self.assertEqual(u["cost_usd"], 0.42)
        self.assertEqual(u["input_tokens"], 1000)
        self.assertEqual(u["output_tokens"], 200)
        self.assertEqual(u["cache_read_input_tokens"], 800)
        self.assertEqual(u["cache_creation_input_tokens"], 50)

    def test_returns_none_on_bad_json(self):
        self.assertIsNone(loop._usage_from_stdout("not json"))

    def test_missing_usage_object_yields_none_token_fields(self):
        u = loop._usage_from_stdout('{"result": "x", "total_cost_usd": 0.1}')
        self.assertEqual(u["cost_usd"], 0.1)
        self.assertIsNone(u["input_tokens"])


def _usage(cost, inp, out):
    return {
        "cost_usd": cost, "input_tokens": inp, "output_tokens": out,
        "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
    }


class TestPipelineUsage(unittest.TestCase):
    def test_records_usage_per_step(self):
        runner = make_runner([
            loop.InvocationResult(0, "x\nSTATUS: IMPLEMENTED", False, _usage(1.0, 100, 10)),
            loop.InvocationResult(0, "https://github.com/o/r/pull/5", False, _usage(0.2, 50, 5)),
            loop.InvocationResult(0, "STATUS: APPROVED", False, _usage(2.0, 300, 30)),
            loop.InvocationResult(0, "STATUS: MERGED", False, _usage(0.1, 20, 5)),
        ])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertEqual([u["step"] for u in r.usage], ["implementit", "shipit", "reviewit", "mergeit"])
        self.assertEqual(r.usage[2]["model"], "opus")
        self.assertEqual(r.usage[2]["cost_usd"], 2.0)

    def test_records_usage_for_failed_step(self):
        runner = make_runner([loop.InvocationResult(1, "", False, _usage(0.5, 20, 0))])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS)
        self.assertEqual(len(r.usage), 1)
        self.assertEqual(r.usage[0]["step"], "implementit")
        self.assertEqual(r.usage[0]["cost_usd"], 0.5)


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


class TestFormatSummaryUsage(unittest.TestCase):
    def _rec(self, step, model, cost, inp, out):
        return {
            "step": step, "model": model, "cost_usd": cost,
            "input_tokens": inp, "output_tokens": out,
            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
        }

    def test_renders_per_step_and_total(self):
        usage = [self._rec("implementit", "sonnet", 1.0, 100, 10),
                 self._rec("reviewit", "opus", 2.0, 300, 30)]
        results = [loop.TicketResult("A-1", True, "https://github.com/o/r/pull/1", "APPROVED", None, None, usage)]
        out = loop.format_summary(results, [])
        self.assertIn("implementit", out)
        self.assertIn("reviewit", out)
        self.assertIn("3.0000", out)   # total cost 1.0 + 2.0
        self.assertIn("TOTAL", out)

    def test_no_usage_section_when_usage_absent(self):
        results = [loop.TicketResult("A-1", True, "https://github.com/o/r/pull/1", "APPROVED", None, None)]
        out = loop.format_summary(results, [])
        self.assertNotIn("TOTAL", out)


if __name__ == "__main__":
    unittest.main()
