import contextlib
import io
import os
import pathlib
import sys
import tempfile
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
        self.assertEqual(out["done"], [])

    def test_done_key_parsed_when_present(self):
        text = '{"project": "p", "wave": [], "held": [], "done": [{"id": "A-1", "title": "t"}]}'
        out = loop.parse_triage_result(text)
        self.assertEqual(out["done"], [{"id": "A-1", "title": "t"}])

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

    def test_effort_flag_included_when_set(self):
        cmd = loop.build_claude_cmd("/personal:implementit A-1", "sonnet", effort="high")
        self.assertIn("--effort", cmd)
        self.assertEqual(cmd[cmd.index("--effort") + 1], "high")

    def test_effort_flag_absent_when_none(self):
        cmd = loop.build_claude_cmd("/personal:implementit A-1", "sonnet", effort=None)
        self.assertNotIn("--effort", cmd)


class TestDefaultEfforts(unittest.TestCase):
    def test_has_expected_keys(self):
        efforts = loop.default_efforts()
        for k in ("implementit", "shipit", "reviewit", "reviewit_rereview", "addressit", "mergeit"):
            self.assertIn(k, efforts)

    def test_implementit_is_high_effort(self):
        self.assertIn(loop.default_efforts()["implementit"], ("high", "xhigh", "max"))


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
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, merge=True)
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
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, merge=True)
        self.assertIsNone(r.failed_step)
        self.assertEqual(r.review_status, "APPROVED")
        self.assertEqual(r.pr_url, "https://github.com/o/r/pull/8")
        self.assertEqual(r.disposition, "MERGED")

    def test_final_review_after_last_addressit_can_approve(self):
        # Regression: a fix on the LAST allowed round must still get a confirming review.
        # max_rounds=1: review(CHANGES) -> address -> review(APPROVED) -> READY_FOR_REVIEW.
        runner = make_runner([
            loop.InvocationResult(0, "implemented\nSTATUS: IMPLEMENTED", False),
            loop.InvocationResult(0, "PR https://github.com/o/r/pull/10", False),
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
            loop.InvocationResult(0, "STATUS: ADDRESSED", False),
            loop.InvocationResult(0, "STATUS: APPROVED", False),
        ])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, max_rounds=1)
        self.assertIsNone(r.failed_step)
        self.assertEqual(r.review_status, "APPROVED")
        self.assertEqual(r.disposition, "READY_FOR_REVIEW")
        self.assertEqual(len(runner.calls["cmds"]), 5)  # impl, ship, review, address, confirming review

    def test_stall_after_max_rounds_includes_final_review(self):
        # Never approves: max_rounds=2 -> 2 addressits AND a final (3rd) confirming review, then stall.
        runner = make_runner([
            loop.InvocationResult(0, "implemented\nSTATUS: IMPLEMENTED", False),
            loop.InvocationResult(0, "PR https://github.com/o/r/pull/11", False),
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),  # review r1
            loop.InvocationResult(0, "STATUS: ADDRESSED", False),          # address r1
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),  # review r2
            loop.InvocationResult(0, "STATUS: ADDRESSED", False),          # address r2
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),  # review r3 (final) -> stall
        ])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, max_rounds=2)
        self.assertEqual(r.disposition, "NEEDS_HUMAN")
        self.assertIn("max rounds (2)", r.reason)
        self.assertEqual(len(runner.calls["cmds"]), 7)  # impl, ship, rev, addr, rev, addr, rev
        reviews = [c for c in runner.calls["cmds"] if "/personal:reviewit" in c[2]]
        addresses = [c for c in runner.calls["cmds"] if "/personal:addressit" in c[2]]
        self.assertEqual(len(reviews), 3)    # max_rounds + 1 (confirming review)
        self.assertEqual(len(addresses), 2)  # max_rounds

    def test_uses_correct_models(self):
        runner = make_runner([
            loop.InvocationResult(0, "x\nSTATUS: IMPLEMENTED", False),
            loop.InvocationResult(0, "https://github.com/o/r/pull/9", False),
            loop.InvocationResult(0, "STATUS: APPROVED", False),
            loop.InvocationResult(0, "STATUS: MERGED", False),
        ])
        loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, merge=True)
        cmds = runner.calls["cmds"]
        self.assertEqual(cmds[0][cmds[0].index("--model") + 1], "sonnet")   # implementit
        self.assertEqual(cmds[2][cmds[2].index("--model") + 1], "sonnet")   # reviewit round 1
        self.assertEqual(cmds[3][cmds[3].index("--model") + 1], "haiku")    # mergeit


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


class TestMaxRoundsArg(unittest.TestCase):
    def test_flag_parsed(self):
        self.assertEqual(loop.parse_args(["--max-rounds", "2"]).max_rounds, 2)
    def test_default(self):
        self.assertEqual(loop.parse_args([]).max_rounds, loop.MAX_ROUNDS)


class TestMergeArg(unittest.TestCase):
    def test_flag_parsed(self):
        self.assertTrue(loop.parse_args(["--merge"]).merge)

    def test_default_false(self):
        self.assertFalse(loop.parse_args([]).merge)


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


class TestRepoNameFromUrl(unittest.TestCase):
    def test_ssh_remote(self):
        self.assertEqual(loop._repo_name_from_url("git@github.com:tomboone/claude-skills.git"), "claude-skills")

    def test_https_remote(self):
        self.assertEqual(loop._repo_name_from_url("https://github.com/org/report-exporters.git"), "report-exporters")

    def test_without_git_suffix(self):
        self.assertEqual(loop._repo_name_from_url("https://github.com/org/report-exporters"), "report-exporters")

    def test_trailing_slash(self):
        self.assertEqual(loop._repo_name_from_url("https://github.com/org/report-exporters/"), "report-exporters")

    def test_empty_or_none(self):
        self.assertIsNone(loop._repo_name_from_url(""))
        self.assertIsNone(loop._repo_name_from_url(None))


class TestRepoArg(unittest.TestCase):
    def test_flag_parsed(self):
        self.assertEqual(loop.parse_args(["--repo", "myrepo"]).repo, "myrepo")

    def test_default_none(self):
        self.assertIsNone(loop.parse_args([]).repo)


class TestResolveRepoLabel(unittest.TestCase):
    def test_explicit_flag_wins(self):
        args = loop.parse_args(["--repo", "backend"])
        label = loop.resolve_repo_label(args, read_claude_md=lambda: "linear_repo: other\n",
                                        remote_url_fn=lambda: "git@github.com:o/remote-repo.git")
        self.assertEqual(label, "repo:backend")

    def test_claude_md_hint_second(self):
        args = loop.parse_args([])
        label = loop.resolve_repo_label(args, read_claude_md=lambda: "linear_initiative: X\nlinear_repo: bi-api\n",
                                        remote_url_fn=lambda: "git@github.com:o/remote-repo.git")
        self.assertEqual(label, "repo:bi-api")

    def test_git_remote_fallback(self):
        args = loop.parse_args([])
        label = loop.resolve_repo_label(args, read_claude_md=lambda: "",
                                        remote_url_fn=lambda: "https://github.com/o/report-exporters.git")
        self.assertEqual(label, "repo:report-exporters")

    def test_aborts_when_unresolvable(self):
        args = loop.parse_args([])
        with self.assertRaises(SystemExit):
            loop.resolve_repo_label(args, read_claude_md=lambda: "", remote_url_fn=lambda: None)


class TestTriagePrompt(unittest.TestCase):
    def test_prompt_includes_repo_and_parent_guard(self):
        rendered = loop.TRIAGE_PROMPT.format(project="P", label="loop-ready", repo_label="repo:backend")
        self.assertIn("repo:backend", rendered)
        self.assertIn("loop-ready", rendered)
        # parent / user-story exclusion must be present
        self.assertIn("sub-issues", rendered)
        self.assertIn("user-story", rendered)
        # JSON contract is unchanged
        self.assertIn('"wave"', rendered)
        self.assertIn('"held"', rendered)


class TestSubprocessRunnerParsing(unittest.TestCase):
    def test_extracts_result_field(self):
        # _result_from_stdout is the pure JSON-extraction half of subprocess_runner
        stdout = '{"session_id": "s", "result": "the answer", "total_cost_usd": 0.1}'
        self.assertEqual(loop._result_from_stdout(stdout), "the answer")

    def test_missing_result_returns_empty(self):
        self.assertEqual(loop._result_from_stdout("not json"), "")


class TestMainDryRun(unittest.TestCase):
    def test_dry_run_prints_commands_without_running_pipeline(self):
        wave = {"project": "p", "wave": [{"id": "A-1", "title": "t"}], "held": []}
        calls = []
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = loop.main(
                ["--project", "p", "--repo", "testrepo", "--dry-run"],
                runner=lambda cmd, timeout: calls.append(cmd) or loop.InvocationResult(0, "", False),
                triage_fn=lambda project, label, repo_label, runner: wave,
                guard_fn=lambda runner: (True, "ok"),
            )
        self.assertEqual(rc, 0)
        # pipeline must not run in dry-run:
        self.assertEqual(calls, [])
        # the resolved repo filter is surfaced:
        self.assertIn("Repo filter: repo:testrepo", buf.getvalue())


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


class TestTicketsPathNoRepoResolve(unittest.TestCase):
    def test_tickets_path_does_not_call_resolve_repo_label(self):
        import unittest.mock
        # Make resolve_repo_label raise SystemExit — it must never be reached on --tickets path.
        with unittest.mock.patch("loop.resolve_repo_label", side_effect=SystemExit("should not be called")):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = loop.main(
                    ["--project", "p", "--tickets", "A-1", "--dry-run"],
                    runner=lambda cmd, timeout: loop.InvocationResult(0, "", False),
                    guard_fn=lambda runner: (True, "ok"),
                )
        self.assertEqual(rc, 0)
        self.assertIn("(none — explicit tickets)", buf.getvalue())


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
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, merge=True)
        self.assertEqual([u["step"] for u in r.usage], ["implementit", "shipit", "reviewit", "mergeit"])
        self.assertEqual(r.usage[2]["model"], "sonnet")
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
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, merge=True)
        self.assertEqual(r.disposition, "MERGED")
        self.assertEqual(r.rounds, 1)
        self.assertEqual(len(runner.calls["cmds"]), 4)

    def test_changes_then_addressed_then_approved_merges(self):
        runner = make_runner([self._impl(), self._ship(),
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
            loop.InvocationResult(0, "STATUS: ADDRESSED", False),
            loop.InvocationResult(0, "STATUS: APPROVED", False),
            loop.InvocationResult(0, "STATUS: MERGED", False)])
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, merge=True)
        self.assertEqual(r.disposition, "MERGED")
        self.assertEqual(r.rounds, 2)
        # both rounds use sonnet (round-1 reviewit and round-2 reviewit_rereview)
        review_cmds = [c for c in runner.calls["cmds"] if "reviewit" in c[2]]
        self.assertEqual(review_cmds[0][review_cmds[0].index("--model")+1], "sonnet")
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
        for _ in range(3):  # max_rounds=3: review CHANGES + address ADDRESSED, three times
            seq += [loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
                    loop.InvocationResult(0, "STATUS: ADDRESSED", False)]
        # the 3rd addressit still gets a confirming re-review; it too returns CHANGES -> stall
        seq += [loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False)]
        r = loop.run_ticket_pipeline({"id": "A-1"}, make_runner(seq), MODELS, TIMEOUTS, max_rounds=3)
        self.assertEqual(r.disposition, "NEEDS_HUMAN")
        self.assertIn("max rounds (3)", r.reason)
        self.assertEqual(r.rounds, 4)  # 3 address rounds + 1 confirming review

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
        r = loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, merge=True)
        self.assertEqual(r.disposition, "NEEDS_HUMAN")
        self.assertIn("merge", r.reason.lower())

    def test_mergeit_not_run_unless_approved(self):
        runner = make_runner([self._impl(), self._ship(),
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
            loop.InvocationResult(0, "STATUS: PUSHED_BACK", False)])
        loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, merge=True)
        self.assertFalse(any("mergeit" in c[2] for c in runner.calls["cmds"]))

    def test_effort_per_step_reaches_invocations(self):
        # effort must land on the actual per-step claude commands, and the round-2
        # re-review must use reviewit_rereview's effort (not round-1 reviewit's).
        runner = make_runner([self._impl(), self._ship(),
            loop.InvocationResult(0, "STATUS: CHANGES_REQUESTED", False),
            loop.InvocationResult(0, "STATUS: ADDRESSED", False),
            loop.InvocationResult(0, "STATUS: APPROVED", False),
            loop.InvocationResult(0, "STATUS: MERGED", False)])
        efforts = loop.default_efforts()
        loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, efforts=efforts, merge=True)
        cmds = runner.calls["cmds"]
        def eff(c):
            return c[c.index("--effort") + 1]
        self.assertEqual(eff(cmds[0]), efforts["implementit"])         # implementit
        self.assertEqual(eff(cmds[1]), efforts["shipit"])              # shipit
        self.assertEqual(eff(cmds[2]), efforts["reviewit"])            # reviewit round 1
        self.assertEqual(eff(cmds[3]), efforts["addressit"])           # addressit round 1
        self.assertEqual(eff(cmds[4]), efforts["reviewit_rereview"])   # reviewit round 2
        self.assertEqual(eff(cmds[5]), efforts["mergeit"])             # mergeit


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
        loop.run_ticket_pipeline({"id": "A-1"}, runner, MODELS, TIMEOUTS, emit=seen.append, merge=True)
        for label in ("implementit", "shipit", "reviewit (round 1)",
                      "addressit (round 1)", "reviewit (round 2)", "mergeit"):
            self.assertIn(label, seen)


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


class TestResolveBase(unittest.TestCase):
    def _args(self, *argv):
        return loop.parse_args(list(argv))

    def test_explicit_flag_wins(self):
        base = loop.resolve_base(
            self._args("--base", "release/0.3.0"),
            read_claude_md=lambda: "loop_base: ignored\n",
            current_branch_fn=lambda: "main",
            default_branch_fn=lambda: "main",
            unmerged_releases_fn=lambda d: [],
        )
        self.assertEqual(base, "release/0.3.0")

    def test_claude_md_hint_second(self):
        base = loop.resolve_base(
            self._args(),
            read_claude_md=lambda: "linear_repo: x\nloop_base: release/0.3.0\n",
            current_branch_fn=lambda: "feat/NEU-1-thing",
            default_branch_fn=lambda: "main",
            unmerged_releases_fn=lambda d: [],
        )
        self.assertEqual(base, "release/0.3.0")

    def test_current_branch_third(self):
        base = loop.resolve_base(
            self._args(),
            read_claude_md=lambda: "",
            current_branch_fn=lambda: "release/0.3.0",
            default_branch_fn=lambda: "main",
            unmerged_releases_fn=lambda d: ["release/0.3.0"],
        )
        self.assertEqual(base, "release/0.3.0")

    def test_current_branch_main_is_respected(self):
        # Explicit checkout of the default branch is honored; auto-select must NOT override it.
        base = loop.resolve_base(
            self._args(),
            read_claude_md=lambda: "",
            current_branch_fn=lambda: "main",
            default_branch_fn=lambda: "main",
            unmerged_releases_fn=lambda d: ["release/0.3.0"],
        )
        self.assertEqual(base, "main")

    def test_work_branch_head_falls_through_to_default(self):
        base = loop.resolve_base(
            self._args(),
            read_claude_md=lambda: "",
            current_branch_fn=lambda: "fix/NEU-2-bug",
            default_branch_fn=lambda: "main",
            unmerged_releases_fn=lambda d: [],
        )
        self.assertEqual(base, "main")

    def test_detached_head_falls_through_to_default(self):
        base = loop.resolve_base(
            self._args(),
            read_claude_md=lambda: "",
            current_branch_fn=lambda: "HEAD",
            default_branch_fn=lambda: "main",
            unmerged_releases_fn=lambda d: [],
        )
        self.assertEqual(base, "main")

    def test_fallback_auto_selects_lone_unmerged_release(self):
        logged = []
        base = loop.resolve_base(
            self._args(),
            read_claude_md=lambda: "",
            current_branch_fn=lambda: "HEAD",          # fallback path
            default_branch_fn=lambda: "main",
            unmerged_releases_fn=lambda d: ["release/0.3.0"],
            emit=logged.append,
        )
        self.assertEqual(base, "release/0.3.0")
        self.assertTrue(any("release/0.3.0" in m for m in logged))

    def test_fallback_keeps_default_when_multiple_releases(self):
        base = loop.resolve_base(
            self._args(),
            read_claude_md=lambda: "",
            current_branch_fn=lambda: "HEAD",
            default_branch_fn=lambda: "main",
            unmerged_releases_fn=lambda d: ["release/0.3.0", "release/0.4.0"],
        )
        self.assertEqual(base, "main")


class TestBaseThreading(unittest.TestCase):
    def test_base_flag_parsed(self):
        self.assertEqual(loop.parse_args(["--base", "release/0.3.0"]).base, "release/0.3.0")

    def test_base_defaults_none(self):
        self.assertIsNone(loop.parse_args([]).base)

    def test_base_threaded_to_implementit_and_shipit_only(self):
        prompts = []

        def recording_runner(cmd, timeout):
            prompts.append(cmd[2])  # build_claude_cmd → ["claude","-p",prompt,...]
            text = "STATUS: IMPLEMENTED https://github.com/o/r/pull/1 STATUS: APPROVED"
            return loop.InvocationResult(0, text, False, None)

        loop.run_ticket_pipeline(
            {"id": "NEU-9", "title": ""}, recording_runner,
            loop.default_models(), loop.default_timeouts(),
            efforts=loop.default_efforts(), base="release/0.3.0", merge=False)

        impl = [p for p in prompts if p.startswith("/personal:implementit ")]
        ship = [p for p in prompts if p.startswith("/personal:shipit ")]
        review = [p for p in prompts if p.startswith("/personal:reviewit ")]
        self.assertTrue(impl and impl[0].endswith("--base release/0.3.0"))
        self.assertTrue(ship and ship[0].endswith("--base release/0.3.0"))
        self.assertTrue(review and "--base" not in review[0])

    def test_no_base_means_no_flag(self):
        prompts = []

        def recording_runner(cmd, timeout):
            prompts.append(cmd[2])
            text = "STATUS: IMPLEMENTED https://github.com/o/r/pull/1 STATUS: APPROVED"
            return loop.InvocationResult(0, text, False, None)

        loop.run_ticket_pipeline(
            {"id": "NEU-9", "title": ""}, recording_runner,
            loop.default_models(), loop.default_timeouts(),
            efforts=loop.default_efforts(), base=None, merge=False)
        self.assertTrue(all("--base" not in p for p in prompts))


class TestNotifyArg(unittest.TestCase):
    def test_absent_is_none(self):
        self.assertIsNone(loop.parse_args([]).notify)

    def test_bare_flag_defaults_macos(self):
        self.assertEqual(loop.parse_args(["--notify"]).notify, "macos")

    def test_explicit_backend(self):
        self.assertEqual(loop.parse_args(["--notify", "pushover"]).notify, "pushover")


class TestApplescriptQuote(unittest.TestCase):
    def test_wraps_in_quotes(self):
        self.assertEqual(loop._applescript_quote("hi"), '"hi"')

    def test_escapes_double_quote_and_backslash(self):
        # input chars: a " b \ c  ->  "a\"b\\c"
        self.assertEqual(loop._applescript_quote('a"b\\c'), '"a\\"b\\\\c"')


class TestMacosNotify(unittest.TestCase):
    def test_builds_osascript_command(self):
        seen = {}
        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            return None
        loop._macos_notify("My Title", "My Body", run=fake_run)
        cmd = seen["cmd"]
        self.assertEqual(cmd[0], "osascript")
        self.assertEqual(cmd[1], "-e")
        self.assertIn("display notification", cmd[2])
        self.assertIn('"My Body"', cmd[2])
        self.assertIn('"My Title"', cmd[2])


class TestPushoverNotify(unittest.TestCase):
    def test_no_post_when_env_missing(self):
        import unittest.mock
        called = []
        def fake_urlopen(req, **kw):
            called.append(req)
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            loop._pushover_notify("t", "m", urlopen=fake_urlopen)
        self.assertEqual(called, [])

    def test_posts_when_env_present(self):
        import unittest.mock
        captured = {}
        def fake_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["data"] = req.data
        env = {"PUSHOVER_APP_TOKEN": "tok", "PUSHOVER_USER_KEY": "usr"}
        with unittest.mock.patch.dict(os.environ, env, clear=True):
            loop._pushover_notify("Title", "Body", urlopen=fake_urlopen)
        self.assertEqual(captured["url"], "https://api.pushover.net/1/messages.json")
        body = captured["data"].decode()
        self.assertIn("token=tok", body)
        self.assertIn("user=usr", body)
        self.assertIn("Title", body)
        self.assertIn("Body", body)


class TestNotifyDispatch(unittest.TestCase):
    def test_none_backend_no_call(self):
        calls = []
        loop.notify(None, "t", "m", notifiers={"macos": lambda *a: calls.append(a)})
        self.assertEqual(calls, [])

    def test_unknown_backend_no_call(self):
        calls = []
        loop.notify("nope", "t", "m", notifiers={"macos": lambda *a: calls.append(a)})
        self.assertEqual(calls, [])

    def test_known_backend_called(self):
        calls = []
        loop.notify("macos", "t", "m", notifiers={"macos": lambda *a: calls.append(a)})
        self.assertEqual(calls, [("t", "m")])

    def test_swallows_backend_exception(self):
        def boom(*a):
            raise RuntimeError("x")
        loop.notify("macos", "t", "m", notifiers={"macos": boom})  # must not raise

    def test_registry_has_builtin_backends(self):
        self.assertIn("macos", loop.NOTIFIERS)
        self.assertIn("pushover", loop.NOTIFIERS)


class TestNotificationMessages(unittest.TestCase):
    def test_failed_ticket_title_and_step(self):
        r = loop.TicketResult("A-1", True, None, None, "shipit",
                              "shipit produced no PR URL", None, "FAILED", 0)
        title, body = loop._ticket_notification(r)
        self.assertIn("A-1", title)
        self.assertIn("FAILED at shipit", title)
        self.assertIn("shipit produced no PR URL", body)

    def test_needs_human_reason_in_body(self):
        r = loop.TicketResult("A-2", True, "https://github.com/o/r/pull/2",
                              "CHANGES_REQUESTED", None, "impasse: ...", None, "NEEDS_HUMAN", 3)
        title, body = loop._ticket_notification(r)
        self.assertIn("NEEDS_HUMAN", title)
        self.assertIn("impasse", body)

    def test_ready_for_review_includes_pr_and_cost(self):
        usage = [{"step": "implementit", "cost_usd": 1.5}]
        r = loop.TicketResult("A-3", True, "https://github.com/o/r/pull/3",
                              "APPROVED", None, None, usage, "READY_FOR_REVIEW", 1)
        title, body = loop._ticket_notification(r)
        self.assertIn("READY_FOR_REVIEW", title)
        self.assertIn("pull/3", body)
        self.assertIn("$1.5000", body)

    def test_summary_counts_by_disposition(self):
        results = [
            loop.TicketResult("A-1", True, "u", "APPROVED", None, None, None, "MERGED", 1),
            loop.TicketResult("A-2", True, "u", "APPROVED", None, None, None, "MERGED", 1),
            loop.TicketResult("A-3", True, None, None, "shipit", "x", None, "FAILED", 0),
        ]
        title, body = loop._summary_notification(results)
        self.assertIn("3 ticket(s)", title)
        self.assertIn("MERGED: 2", body)
        self.assertIn("FAILED: 1", body)

    def test_summary_empty(self):
        title, body = loop._summary_notification([])
        self.assertIn("0 ticket(s)", title)
        self.assertIn("no tickets", body)


class TestMainNotify(unittest.TestCase):
    def _driving_runner(self):
        def runner(cmd, timeout):
            p = cmd[2]
            if "/personal:implementit" in p:
                return loop.InvocationResult(0, "STATUS: IMPLEMENTED", False)
            if "/personal:shipit" in p:
                return loop.InvocationResult(0, "PR https://github.com/o/r/pull/1", False)
            if "/personal:reviewit" in p:
                return loop.InvocationResult(0, "STATUS: APPROVED", False)
            return loop.InvocationResult(0, "", False)
        return runner

    def _wave(self, *ids):
        return {"project": "p", "wave": [{"id": i, "title": ""} for i in ids], "held": []}

    def test_fires_per_ticket_and_summary(self):
        calls = []
        with contextlib.redirect_stdout(io.StringIO()):
            rc = loop.main(
                ["--project", "p", "--repo", "r", "--notify"],
                runner=self._driving_runner(),
                triage_fn=lambda *a, **k: self._wave("A-1", "A-2"),
                guard_fn=lambda runner: (True, "ok"),
                notify_fn=lambda *a: calls.append(a),
            )
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 3)               # 2 per-ticket + 1 summary
        self.assertEqual(calls[-1][0], "macos")
        self.assertIn("Loop finished", calls[-1][1])

    def test_no_notify_means_no_calls(self):
        calls = []
        with contextlib.redirect_stdout(io.StringIO()):
            loop.main(
                ["--project", "p", "--repo", "r"],
                runner=self._driving_runner(),
                triage_fn=lambda *a, **k: self._wave("A-1"),
                guard_fn=lambda runner: (True, "ok"),
                notify_fn=lambda *a: calls.append(a),
            )
        self.assertEqual(calls, [])

    def test_dry_run_no_notify_calls(self):
        calls = []
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            loop.main(
                ["--project", "p", "--repo", "r", "--notify", "--dry-run"],
                runner=self._driving_runner(),
                triage_fn=lambda *a, **k: self._wave("A-1"),
                guard_fn=lambda runner: (True, "ok"),
                notify_fn=lambda *a: calls.append(a),
            )
        self.assertEqual(calls, [])
        self.assertIn("Notifications: macos", buf.getvalue())

    def test_unknown_backend_warns_and_disables(self):
        calls = []
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            loop.main(
                ["--project", "p", "--repo", "r", "--notify", "bogus"],
                runner=self._driving_runner(),
                triage_fn=lambda *a, **k: self._wave("A-1"),
                guard_fn=lambda runner: (True, "ok"),
                notify_fn=lambda *a: calls.append(a),
            )
        self.assertEqual(calls, [])
        self.assertIn("unknown backend", err.getvalue())


class TestDotenv(unittest.TestCase):
    def test_parse_basic(self):
        self.assertEqual(loop._parse_dotenv("A=1\nB = two\n"), {"A": "1", "B": "two"})

    def test_parse_skips_comments_and_blanks(self):
        self.assertEqual(loop._parse_dotenv("# c\n\nA=1\n"), {"A": "1"})

    def test_parse_strips_one_pair_of_quotes(self):
        self.assertEqual(loop._parse_dotenv("A=\"q\"\nB='s'\n"), {"A": "q", "B": "s"})

    def test_parse_ignores_lines_without_equals(self):
        self.assertEqual(loop._parse_dotenv("novalue\nA=1"), {"A": "1"})

    def test_parse_keeps_inner_equals(self):
        self.assertEqual(loop._parse_dotenv("A=b=c"), {"A": "b=c"})

    def _write_env(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        f.write(text)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return pathlib.Path(f.name)

    def test_load_sets_missing_keys(self):
        path = self._write_env("PUSHOVER_APP_TOKEN=tok\n")
        environ = {}
        used = loop.load_dotenv(candidates=[path], environ=environ)
        self.assertEqual(used, path)
        self.assertEqual(environ["PUSHOVER_APP_TOKEN"], "tok")

    def test_real_env_wins(self):
        path = self._write_env("PUSHOVER_APP_TOKEN=fromfile\n")
        environ = {"PUSHOVER_APP_TOKEN": "fromenv"}
        loop.load_dotenv(candidates=[path], environ=environ)
        self.assertEqual(environ["PUSHOVER_APP_TOKEN"], "fromenv")

    def test_first_existing_candidate_wins(self):
        missing = pathlib.Path("/nonexistent/does-not-exist.env")
        path = self._write_env("K=real\n")
        environ = {}
        used = loop.load_dotenv(candidates=[missing, path], environ=environ)
        self.assertEqual(used, path)
        self.assertEqual(environ["K"], "real")

    def test_returns_none_when_no_candidate_exists(self):
        environ = {}
        used = loop.load_dotenv(
            candidates=[pathlib.Path("/nonexistent/x.env")], environ=environ
        )
        self.assertIsNone(used)
        self.assertEqual(environ, {})


class TestRunTriage(unittest.TestCase):
    def test_raises_on_failure(self):
        with self.assertRaises(SystemExit):
            loop.run_triage("p", "loop-ready", "repo:r", lambda cmd, timeout: loop.InvocationResult(1, "", False))

    def test_raises_with_the_agents_reply_when_json_is_unparseable(self):
        def runner(cmd, timeout):
            return loop.InvocationResult(0, "I don't have access to the Linear MCP right now.", False)

        with self.assertRaises(SystemExit) as ctx:
            loop.run_triage("p", "loop-ready", "repo:r", runner)
        self.assertIn("Linear MCP", str(ctx.exception))


class TestRunExplicitWave(unittest.TestCase):
    def test_formats_prompt_and_parses_result(self):
        calls = []

        def runner(cmd, timeout):
            calls.append(cmd)
            return loop.InvocationResult(
                0, '{"project": "p", "wave": [{"id": "A-1", "title": "t"}], "held": [], "done": []}', False)

        out = loop.run_explicit_wave("p", ["A-1", "A-2"], runner)
        self.assertEqual(out["wave"], [{"id": "A-1", "title": "t"}])
        prompt = calls[0][2]
        self.assertIn("A-1, A-2", prompt)
        self.assertIn("p", prompt)

    def test_raises_on_failure(self):
        with self.assertRaises(SystemExit):
            loop.run_explicit_wave("p", ["A-1"], lambda cmd, timeout: loop.InvocationResult(1, "", False))

    def test_raises_with_the_agents_reply_when_json_is_unparseable(self):
        """Zero exit, no timeout, but the agent's final message wasn't JSON (asked a clarifying
        question, hit an MCP error, explained a problem in prose, ...) — must not be a bare
        traceback, and must surface what the agent actually said."""
        def runner(cmd, timeout):
            return loop.InvocationResult(0, "I couldn't find a project by that name — did you mean 'Foo Bar'?", False)

        with self.assertRaises(SystemExit) as ctx:
            loop.run_explicit_wave("p", ["A-1"], runner)
        self.assertIn("Foo Bar", str(ctx.exception))


class TestParseWaveResult(unittest.TestCase):
    def test_passes_through_valid_json(self):
        out = loop._parse_wave_result("Triage call", '{"project": "p", "wave": [], "held": []}')
        self.assertEqual(out["project"], "p")

    def test_wraps_unparseable_text_in_systemexit_with_the_raw_reply(self):
        with self.assertRaises(SystemExit) as ctx:
            loop._parse_wave_result("Triage call", "Sorry, I need more information to proceed.")
        msg = str(ctx.exception)
        self.assertIn("Triage call", msg)
        self.assertIn("Sorry, I need more information to proceed.", msg)

    def test_handles_none_result_text(self):
        with self.assertRaises(SystemExit) as ctx:
            loop._parse_wave_result("Triage call", None)
        self.assertIn("(empty)", str(ctx.exception))


class TestWavesRequiresMerge(unittest.TestCase):
    def test_waves_without_merge_errors_before_anything_runs(self):
        def boom(*a, **k):
            raise AssertionError("should not run")

        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            rc = loop.main(
                ["--project", "p", "--repo", "r", "--waves"],
                runner=boom,
                guard_fn=boom,
            )
        self.assertEqual(rc, 2)
        self.assertIn("--waves requires --merge", buf.getvalue())

    def test_waves_with_merge_passes_validation(self):
        wave_seq = iter([
            {"project": "p", "wave": [], "held": [], "done": []},
        ])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = loop.main(
                ["--project", "p", "--repo", "r", "--waves", "--merge"],
                runner=lambda cmd, timeout: loop.InvocationResult(0, "", False),
                triage_fn=lambda project, label, repo_label, runner: next(wave_seq),
                guard_fn=lambda runner: (True, "ok"),
            )
        self.assertEqual(rc, 0)
        self.assertIn("complete", buf.getvalue())


def _merged_ticket_calls():
    """Scripted runner responses for one ticket that sails straight through to MERGED."""
    return [
        loop.InvocationResult(0, "implemented\nSTATUS: IMPLEMENTED", False),
        loop.InvocationResult(0, "PR https://github.com/o/r/pull/7", False),
        loop.InvocationResult(0, "STATUS: APPROVED", False),
        loop.InvocationResult(0, "STATUS: MERGED", False),
    ]


class TestMainWavesLabelMode(unittest.TestCase):
    def test_stops_when_a_wave_is_empty_and_nothing_held(self):
        """Label-triage mode: empty wave + no held tickets means the project is complete."""
        wave_seq = iter([
            {"project": "p", "wave": [{"id": "A-1", "title": "t"}], "held": [], "done": []},
            {"project": "p", "wave": [], "held": [], "done": []},
        ])
        runner = make_runner(_merged_ticket_calls())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = loop.main(
                ["--project", "p", "--repo", "r", "--waves", "--merge"],
                runner=runner,
                triage_fn=lambda project, label, repo_label, runner: next(wave_seq),
                guard_fn=lambda runner: (True, "ok"),
            )
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("wave 1:", out)
        # round 2's wave came back empty, so no "wave 2:" processing line is emitted —
        # only the final stop reason:
        self.assertNotIn("wave 2:", out)
        self.assertIn("complete", out)
        self.assertIn("MERGED", out)

    def test_stops_when_wave_is_empty_but_something_is_held(self):
        wave_seq = iter([
            {"project": "p", "wave": [], "held": [{"id": "A-2", "title": "t", "waiting_on": ["A-9"]}], "done": []},
        ])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = loop.main(
                ["--project", "p", "--repo", "r", "--waves", "--merge"],
                runner=lambda cmd, timeout: loop.InvocationResult(0, "", False),
                triage_fn=lambda project, label, repo_label, runner: next(wave_seq),
                guard_fn=lambda runner: (True, "ok"),
            )
        self.assertEqual(rc, 0)
        self.assertIn("stalled", buf.getvalue())

    def test_stops_when_a_wave_makes_no_progress(self):
        """A ticket that fails outright (no MERGED result) must not be retried forever."""
        wave_seq = iter([
            {"project": "p", "wave": [{"id": "A-1", "title": "t"}], "held": [], "done": []},
            {"project": "p", "wave": [{"id": "A-1", "title": "t"}], "held": [], "done": []},
        ])
        runner = make_runner([loop.InvocationResult(1, "", False)])  # implementit fails outright
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = loop.main(
                ["--project", "p", "--repo", "r", "--waves", "--merge"],
                runner=runner,
                triage_fn=lambda project, label, repo_label, runner: next(wave_seq),
                guard_fn=lambda runner: (True, "ok"),
            )
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertEqual(out.count("wave 1:"), 1)  # only one round ran, never a "wave 2:"
        self.assertIn("no progress", out)
        # a failed ticket is excluded from being retried even if triage would resurface it:
        self.assertEqual(len(runner.calls["cmds"]), 1)

    def test_hits_max_waves_safety_cap(self):
        """Every round merges a fresh ticket forever — the cap must still terminate the loop."""
        import itertools
        import unittest.mock

        def infinite_waves():
            for n in itertools.count(1):
                yield {"project": "p", "wave": [{"id": f"A-{n}", "title": "t"}], "held": [], "done": []}
        gen = infinite_waves()

        runner = make_runner([r for _ in range(10) for r in _merged_ticket_calls()])
        buf = io.StringIO()
        with unittest.mock.patch("loop.MAX_WAVES", 3):
            with contextlib.redirect_stdout(buf):
                rc = loop.main(
                    ["--project", "p", "--repo", "r", "--waves", "--merge"],
                    runner=runner,
                    triage_fn=lambda project, label, repo_label, runner: next(gen),
                    guard_fn=lambda runner: (True, "ok"),
                )
        self.assertEqual(rc, 0)
        self.assertIn("wave 3:", buf.getvalue())
        self.assertNotIn("wave 4:", buf.getvalue())
        self.assertIn("safety cap", buf.getvalue())


class TestMainWavesTicketsMode(unittest.TestCase):
    def test_plain_tickets_without_waves_never_calls_explicit_wave_fn(self):
        runner = make_runner(_merged_ticket_calls())
        buf = io.StringIO()

        def boom(project, ids, runner):
            raise AssertionError("explicit_wave_fn should not be called without --waves")

        with contextlib.redirect_stdout(buf):
            rc = loop.main(
                ["--project", "p", "--tickets", "A-1", "--merge"],
                runner=runner,
                explicit_wave_fn=boom,
                guard_fn=lambda runner: (True, "ok"),
            )
        self.assertEqual(rc, 0)
        self.assertIn("MERGED", buf.getvalue())

    def test_tickets_with_waves_shrinks_candidates_across_rounds(self):
        """A-1 merges in round 1; round 2's explicit_wave_fn call must only ask about A-2."""
        seen_candidate_sets = []

        def explicit_wave_fn(project, ids, runner):
            seen_candidate_sets.append(list(ids))
            if "A-1" in ids:
                return {"project": project, "wave": [{"id": "A-1", "title": "t"}], "held": [], "done": []}
            return {"project": project, "wave": [{"id": "A-2", "title": "t"}], "held": [], "done": []}

        runner = make_runner(_merged_ticket_calls() + _merged_ticket_calls())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = loop.main(
                ["--project", "p", "--tickets", "A-1", "A-2", "--waves", "--merge"],
                runner=runner,
                explicit_wave_fn=explicit_wave_fn,
                guard_fn=lambda runner: (True, "ok"),
            )
        self.assertEqual(rc, 0)
        self.assertEqual(seen_candidate_sets[0], ["A-1", "A-2"])
        self.assertEqual(seen_candidate_sets[1], ["A-2"])  # A-1 excluded after merging
        self.assertIn("complete", buf.getvalue())

    def test_tickets_with_waves_does_not_call_resolve_repo_label(self):
        import unittest.mock
        with unittest.mock.patch("loop.resolve_repo_label", side_effect=SystemExit("should not be called")):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = loop.main(
                    ["--project", "p", "--tickets", "A-1", "--waves", "--merge"],
                    runner=make_runner(_merged_ticket_calls()),
                    explicit_wave_fn=lambda project, ids, runner: {
                        "project": project, "wave": [{"id": t, "title": ""} for t in ids],
                        "held": [], "done": [],
                    },
                    guard_fn=lambda runner: (True, "ok"),
                )
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
