# -*- coding: utf-8 -*-
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import state_layers as S


class TestStateLayers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "examples", "synthetic_week.json"), encoding="utf-8") as handle:
            payload = json.load(handle)
        cls.daily = payload["history_daily"] + payload["daily"]

    def test_raw_signals_preserve_value_and_pointer(self):
        cards = S.raw_signal_snapshot(self.daily, "20260810", "20260811")
        sleep = next(item for item in cards if item["key"] == "sleep_duration_min")
        self.assertEqual(sleep["latest"], 455)
        self.assertEqual(sleep["n_week"], 2)
        self.assertEqual(sleep["n_baseline"], 14)
        self.assertEqual(sleep["pointer"], "/daily/15/sleep_duration_min")

    def test_multidomain_is_experimental_and_confidence_separate(self):
        state = S.multidomain_state(self.daily, "20260810", "20260811")
        self.assertEqual(state["status"], "experimental")
        self.assertEqual(state["anchor"], 50)
        self.assertEqual(state["axes"][-1]["id"], "data_confidence")
        self.assertGreaterEqual(sum(axis["available"] for axis in state["axes"][:-1]), 4)

    def test_change_candidates_fail_closed_with_short_history(self):
        result = S.change_candidates(self.daily[-5:], "20260811")
        self.assertEqual(result["signals"], [])
        self.assertEqual(result["candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()
