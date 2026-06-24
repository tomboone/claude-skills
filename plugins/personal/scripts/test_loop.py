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


if __name__ == "__main__":
    unittest.main()
