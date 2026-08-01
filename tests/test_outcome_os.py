import json
import tempfile
import unittest
from pathlib import Path

import outcome_os


class OutcomeOSTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.ws = outcome_os.Workspace.at(self.root)
        state = outcome_os.initial_state(
            "Ship feature",
            "Implement and verify a feature",
            ["Feature exists", "Tests pass"],
            "owner/repo",
            0.85,
            10,
        )
        self.ws.save(state)
        self.ws.append_event("goal.initialized", {"goal": state["goal"]})

    def tearDown(self):
        self.tempdir.cleanup()

    def test_verification_requires_evidence_and_finished_work(self):
        state = self.ws.load()
        state["work_items"].append(outcome_os.work_item_record("Implement", priority=90))
        self.assertFalse(outcome_os.verify_state(state)["complete"])

        for criterion in state["criteria"]:
            criterion["evidence"].append({"id": "e", "value": "proof"})
        state["work_items"][0]["status"] = "done"
        verdict = outcome_os.verify_state(state)
        self.assertTrue(verdict["complete"])
        self.assertGreaterEqual(verdict["confidence"], 0.85)

    def test_open_blocker_prevents_completion(self):
        state = self.ws.load()
        for criterion in state["criteria"]:
            criterion["evidence"].append({"id": "e", "value": "proof"})
        state["blockers"].append({"id": "b-1", "text": "CI unavailable", "status": "open"})
        self.assertFalse(outcome_os.verify_state(state)["complete"])

    def test_required_check_prevents_completion_until_passed(self):
        state = self.ws.load()
        state["criteria"][0]["required_checks"] = ["tests"]
        for criterion in state["criteria"]:
            criterion["evidence"].append({"id": "e", "value": "proof"})
        self.assertFalse(outcome_os.verify_state(state)["complete"])
        state["checks"]["tests"] = {"passed": True}
        self.assertTrue(outcome_os.verify_state(state)["complete"])

    def test_portfolio_import_normalizes_common_shapes(self):
        payload = {
            "backlog": [
                {"stable_id": "P-1", "summary": "Fix release", "priority": "high", "acceptance_criteria": ["CI green"]},
                "Write documentation",
            ]
        }
        items = outcome_os.load_backlog_items(payload)
        self.assertEqual(items[0]["source_id"], "P-1")
        self.assertEqual(items[0]["priority"], 80)
        self.assertEqual(items[1]["title"], "Write documentation")

    def test_ledger_is_hash_chained(self):
        first = json.loads(self.ws.ledger_path.read_text().splitlines()[0])
        second = self.ws.append_event("test", {"value": 1})
        self.assertEqual(second["previous_hash"], first["hash"])
        event_without_hash = dict(second)
        recorded = event_without_hash.pop("hash")
        self.assertEqual(recorded, outcome_os.sha256_text(outcome_os.canonical_json(event_without_hash)))

    def test_dashboard_is_self_contained(self):
        state = self.ws.load()
        page = outcome_os.render_dashboard(state, outcome_os.verify_state(state))
        self.assertIn("Outcome OS", page)
        self.assertNotIn("<script src=", page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)

    def test_doctor_detects_tampered_ledger(self):
        original = self.ws.ledger_path.read_text()
        self.ws.ledger_path.write_text(original.replace("goal.initialized", "goal.modified"), encoding="utf-8")
        previous = "0" * 64
        errors = []
        for line in self.ws.ledger_path.read_text().splitlines():
            event = json.loads(line)
            recorded = event.pop("hash")
            if event["previous_hash"] != previous:
                errors.append("chain")
            if recorded != outcome_os.sha256_text(outcome_os.canonical_json(event)):
                errors.append("hash")
            previous = recorded
        self.assertIn("hash", errors)


if __name__ == "__main__":
    unittest.main()
