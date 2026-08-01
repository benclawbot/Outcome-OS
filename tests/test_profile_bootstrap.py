import json
import tempfile
import unittest
from pathlib import Path

import profile_bootstrap


class ProfileBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.profile = self.root / "goal.json"
        self.profile.write_text(json.dumps({
            "title": "Medusa completion",
            "objective": "Complete one issue",
            "repository": "benclawbot/Medusa",
            "confidence_threshold": 0.9,
            "criteria": ["PR merged", "Issue closed"],
            "operating_rules": ["One issue at a time"],
        }), encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_initializes_workspace_and_embeds_rules(self):
        destination = self.root / "workspace"
        workspace = profile_bootstrap.initialize_from_profile(self.profile, destination)
        state = workspace.load()
        self.assertEqual(state["goal"]["repository"], "benclawbot/Medusa")
        self.assertEqual(state["goal"]["confidence_threshold"], 0.9)
        self.assertIn("One issue at a time", state["goal"]["objective"])
        self.assertEqual(state["operating_rules"], ["One issue at a time"])

    def test_rejects_invalid_threshold(self):
        value = json.loads(self.profile.read_text())
        value["confidence_threshold"] = 1.5
        self.profile.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(ValueError):
            profile_bootstrap.load_profile(self.profile)


if __name__ == "__main__":
    unittest.main()
