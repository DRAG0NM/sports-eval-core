# -*- coding: utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import core_metrics as M


class TestCoreMetrics(unittest.TestCase):
    def test_efficiency_factor_direction(self):
        fast = M.efficiency_factor(1000, 360, 150)
        slow = M.efficiency_factor(1000, 600, 150)
        self.assertAlmostEqual(fast, 1.111, places=3)
        self.assertGreater(fast, slow)

    def test_edwards_trimp(self):
        self.assertEqual(M.trimp_edwards([10, 20, 5, 0, 0]), 65.0)
        self.assertIsNone(M.trimp_edwards([10, 20]))

    def test_monotony_strain_uses_weekly_sum(self):
        result = M.monotony_strain([10, 0, 20, 0, 30, 0, 0])
        self.assertEqual(result["weekly_load"], 60)
        self.assertAlmostEqual(result["strain"], result["weekly_load"] * result["monotony"], delta=0.6)

    def test_acwr_sparse_history_treats_missing_days_as_rest(self):
        loads = {"20260715": 40, "20260720": 60, "20260804": 70, "20260810": 30}
        result = M.acwr(loads, "20260811")
        self.assertIsNotNone(result)
        self.assertTrue(result["experimental"])
        self.assertEqual(result["acute_7d"], 100)

    def test_acwr_requires_history_span(self):
        self.assertIsNone(M.acwr({"20260810": 50}, "20260811"))

    def test_ewma_uses_distinct_time_constants(self):
        result = M.ewma_acwr({"20260714": 20, "20260804": 50, "20260810": 80}, "20260811")
        self.assertEqual(result["acute_lambda"], 0.25)
        self.assertEqual(result["chronic_lambda"], 0.069)

    def test_formal_sri_identical_schedule_is_100(self):
        intervals = [
            {"start": "2026-08-08T23:30:00+08:00", "end": "2026-08-09T07:00:00+08:00"},
            {"start": "2026-08-09T23:30:00+08:00", "end": "2026-08-10T07:00:00+08:00"},
            {"start": "2026-08-10T23:30:00+08:00", "end": "2026-08-11T07:00:00+08:00"},
        ]
        self.assertEqual(M.sleep_regularity_sri(intervals), 100.0)

    def test_circular_sleep_consistency_handles_midnight(self):
        intervals = [
            {"start": "2026-08-08T23:50:00+08:00", "end": "2026-08-09T07:00:00+08:00"},
            {"start": "2026-08-10T00:10:00+08:00", "end": "2026-08-10T07:10:00+08:00"},
            {"start": "2026-08-10T23:55:00+08:00", "end": "2026-08-11T06:55:00+08:00"},
        ]
        self.assertLess(M.sleep_consistency(intervals)["sleep_start_sd_min"], 15)

    def test_recovery_composite_renormalizes_missing_component(self):
        result = M.recovery_composite(0.8, 0.6, None)
        self.assertEqual(result["weights"], {"hrv": 0.625, "sleep": 0.375})
        self.assertAlmostEqual(result["score"], 72.5)


if __name__ == "__main__":
    unittest.main()
