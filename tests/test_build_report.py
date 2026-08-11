# -*- coding: utf-8 -*-
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_report as R


def read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class TestBuildReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "examples", "synthetic_week.json"), encoding="utf-8") as handle:
            cls.payload = json.load(handle)

    def test_synthetic_report_is_layered_and_auditable(self):
        report = R.render_report(self.payload)
        self.assertIn("截至 2026-08-11，当前周未完", report)
        self.assertIn("合成示例数据", report)
        self.assertIn("ACWR（实验）", report)
        self.assertIn("原始单指标（无阈值、无加权）", report)
        self.assertIn("多维个人状态（实验）", report)
        self.assertIn("50 是个人历史中性锚点", report)
        self.assertNotIn("诊断", report.split("## 数据边界", 1)[0])

    def test_user_notes_survive_regeneration(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "weekly.md")
            generated = R.render_report(self.payload)
            R.upsert_report(path, generated)
            first = read_text(path).replace(R.NOTES_PLACEHOLDER, "RPE 5，路线为合成示例。")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(first)
            R.upsert_report(path, generated.replace("轻松跑", "恢复跑"))
            second = read_text(path)
            self.assertIn("恢复跑", second)
            self.assertIn("RPE 5，路线为合成示例。", second)
            self.assertGreater(second.index(R.NOTES_HEADER), second.index(R.AUTO_END))

    def test_invalid_schema_rejected(self):
        invalid = dict(self.payload)
        invalid["schema_version"] = 2
        with self.assertRaises(ValueError):
            R.render_report(invalid)


if __name__ == "__main__":
    unittest.main()
