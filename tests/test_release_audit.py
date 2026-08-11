# -*- coding: utf-8 -*-
import contextlib
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import release_audit


class TestReleaseAudit(unittest.TestCase):
    def test_repository_passes_fail_closed_publication_audit(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = release_audit.audit()
        self.assertEqual(result, 0, output.getvalue())
        self.assertIn("no absolute personal paths", output.getvalue())


if __name__ == "__main__":
    unittest.main()
