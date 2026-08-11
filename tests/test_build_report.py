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

    def test_synthetic_report_is_partial_and_auditable(self):
        report = R.render_report(self.payload)
        self.assertIn("截至 2026-08-11，当前周未完", report)
        self.assertIn("合成示例数据", report)
        self.assertIn("ACWR（实验）", report)
        self.assertIn("理论范围 -100~100", report)
        self.assertIn("轻松跑", report)
        self.assertNotIn("诊断", report.split("## 数据边界", 1)[0])

    def test_user_notes_survive_regeneration(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "weekly.md")
            generated = R.render_report(self.payload)
            R.upsert_report(path, generated)
            self.assertTrue(read_text(path).startswith("---\n"))
            self.assertLess(read_text(path).index("synthetic: true"), read_text(path).index(R.AUTO_BEGIN))
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


class TestPublicationBoundary(unittest.TestCase):
    def test_no_vendor_endpoint_or_browser_token_logic_in_public_scripts(self):
        forbidden = ("accessToken", "dbankcloud", "health.cloud", "sessionStorage", "华为", "huawei")
        for name in os.listdir(os.path.join(ROOT, "scripts")):
            if not name.endswith(".py") or name == "release_audit.py":
                continue
            content = read_text(os.path.join(ROOT, "scripts", name)).lower()
            for needle in forbidden:
                self.assertNotIn(needle.lower(), content, "%s contains %s" % (name, needle))

    def test_no_raw_wearable_files_or_env(self):
        forbidden_suffixes = (".fit", ".tcx", ".gpx", ".har")
        for base, _, files in os.walk(ROOT):
            for name in files:
                path = os.path.join(base, name)
                rel = os.path.relpath(path, ROOT)
                self.assertFalse(name.lower().endswith(forbidden_suffixes), rel)
                self.assertNotEqual(name, ".env", rel)


if __name__ == "__main__":
    unittest.main()
