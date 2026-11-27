import unittest

from runtime.security.repo_diff_guard import scan_diff_text


class RepoDiffGuardTest(unittest.TestCase):
    def test_diff_with_secret_like_content_blocks(self):
        key = "sk-proj-" + "abcdefghijklmnopqrstuvwxyz1234567890"
        diff = """
diff --git a/.env b/.env
""" + "+OPENAI_API_KEY=" + key + "\n"

        result = scan_diff_text(diff)

        self.assertEqual(result["decision"], "block")
        self.assertEqual(result["reason"], "secret_like_content_detected")
        self.assertEqual(result["finding_count"], 1)
        self.assertNotIn(key, result["redacted_diff"])

    def test_safe_diff_allows(self):
        diff = """
diff --git a/runtime/README.md b/runtime/README.md
+No secrets here.
"""

        result = scan_diff_text(diff)

        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["finding_count"], 0)
        self.assertIn("Pattern-based", result["scope_note"])


if __name__ == "__main__":
    unittest.main()
