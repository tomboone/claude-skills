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
