import unittest

from runtime.security.secret_patterns import is_secret_path
from runtime.security.secret_scan import redact_text, scan_text


class SecretScanTest(unittest.TestCase):
    def test_openai_key_is_detected_and_redacted(self):
        key = "sk-proj-" + "abcdefghijklmnopqrstuvwxyz1234567890"
        text = "OPENAI_API_KEY=" + key

        result = scan_text(text, source="unit")

        self.assertTrue(result.has_findings)
        self.assertEqual(result.findings[0].kind, "openai_api_key")
        self.assertNotIn(key, result.redacted_text)
        self.assertIn("[REDACTED_OPENAI_API_KEY]", result.redacted_text)

    def test_database_dsn_and_bearer_token_are_redacted(self):
        dsn = "postgres://" + "user:pass@example.com:5432/app"
        token = "abcdefghijklmnopqrstuvwxyz123456"
        text = (
            "DATABASE_URL=" + dsn + "\n"
            "Authorization: Bearer " + token
        )

        redacted = redact_text(text, source="unit")

        self.assertNotIn(dsn, redacted)
        self.assertNotIn(token, redacted)
        self.assertIn("[REDACTED_DATABASE_DSN]", redacted)
        self.assertIn("Bearer [REDACTED_TOKEN]", redacted)

    def test_clean_scan_carries_scope_note_without_secret_finding(self):
        result = scan_text("No synthetic secrets here.", source="unit")

        self.assertFalse(result.has_findings)
        self.assertEqual(result.findings, ())
        self.assertIn("Pattern-based", result.scope_note)
        self.assertEqual(result.to_dict()["finding_count"], 0)

    def test_secret_path_detection_is_conservative(self):
        self.assertTrue(is_secret_path(".env"))
        self.assertTrue(is_secret_path("config/.env.local"))
        self.assertTrue(is_secret_path("keys/prod.pem"))
        self.assertTrue(is_secret_path("credentials.json"))
        self.assertFalse(is_secret_path("runtime/security/secret_scan.py"))
        self.assertFalse(is_secret_path("docs/secret_boundary.md"))


if __name__ == "__main__":
    unittest.main()
