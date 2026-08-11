# -*- coding: utf-8 -*-
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import coach_core as C


class TestCoachCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "examples", "synthetic_week.json"), encoding="utf-8") as handle:
            cls.payload = json.load(handle)
        with open(os.path.join(ROOT, "examples", "synthetic_response.json"), encoding="utf-8") as handle:
            cls.response = json.load(handle)

    def test_context_is_budgeted_and_content_addressed(self):
        first = C.build_context(self.payload, "daily_guidance", "synthetic question")
        second = C.build_context(self.payload, "daily_guidance", "synthetic question")
        self.assertEqual(first["content_sha256"], second["content_sha256"])
        self.assertTrue(first["context_metrics"]["within_budget"])
        self.assertEqual(first["safety_gate"]["level"], "green")

    def test_synthetic_response_has_exact_evidence(self):
        context = C.build_context(self.payload, "daily_guidance")
        result = C.validate_response(self.response, context)
        self.assertTrue(result["valid"], result["errors"])

    def test_observed_value_mismatch_fails(self):
        context = C.build_context(self.payload, "daily_guidance")
        response = json.loads(json.dumps(self.response))
        response["observations"][0]["evidence"][0]["observed_value"] = 999
        result = C.validate_response(response, context)
        self.assertFalse(result["valid"])
        self.assertIn("value_mismatch", {item["code"] for item in result["errors"]})

    def test_context_tampering_fails(self):
        context = C.build_context(self.payload, "daily_guidance")
        context["views"]["raw_signals"][0]["latest"] = 999
        result = C.validate_response(self.response, context)
        self.assertFalse(result["valid"])
        self.assertIn("context_hash", {item["code"] for item in result["errors"]})

    def test_red_gate_blocks_training_action(self):
        payload = json.loads(json.dumps(self.payload))
        payload["subjective_events"] = [{"date": "20260811", "type": "pain_followup",
                                          "pain": 8, "red_flags": ["cannot_bear_weight"]}]
        context = C.build_context(payload, "pain_followup")
        self.assertEqual(context["safety_gate"]["level"], "red")
        response = json.loads(json.dumps(self.response))
        response["task"] = "pain_followup"
        response["recommendations"][0]["action_type"] = "rest"
        response["risks"][0]["level"] = "red"
        result = C.validate_response(response, context)
        self.assertFalse(result["valid"])
        self.assertIn("safety_action", {item["code"] for item in result["errors"]})

    def test_plan_change_requires_confirmation(self):
        context = C.build_context(self.payload, "weekly_review")
        response = json.loads(json.dumps(self.response))
        response["task"] = "weekly_review"
        response["recommendations"][0].update({"action_type": "draft_plan",
                                                "changes_plan": True,
                                                "requires_confirmation": False})
        result = C.validate_response(response, context)
        self.assertIn("confirmation", {item["code"] for item in result["errors"]})


if __name__ == "__main__":
    unittest.main()
