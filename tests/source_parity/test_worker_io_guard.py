import unittest

from runtime.security.worker_io_guard import (
    guard_worker_input_scope,
    redact_worker_payload,
    scan_worker_payload,
)


class WorkerIOGuardTest(unittest.TestCase):
    def test_secret_paths_block_worker_scope(self):
        result = guard_worker_input_scope({
            "paths_allowed": ["runtime/README.md", ".env.local"],
            "paths_excluded": [],
        })

        self.assertEqual(result["decision"], "block")
        self.assertIn("secret_path_in_worker_scope", result["reasons"])
        self.assertEqual(result["secret_paths"], [".env.local"])

    def test_worker_payload_scan_detects_secret_like_output(self):
        key = "sk-proj-" + "abcdefghijklmnopqrstuvwxyz1234567890"
        payload = {
            "content": {
                "summary": "candidate",
                "snippet": "OPENAI_API_KEY=" + key,
            }
        }

        result = scan_worker_payload(payload)

        self.assertEqual(result["decision"], "block")
        self.assertEqual(result["finding_count"], 1)
        self.assertEqual(result["findings"][0]["kind"], "openai_api_key")
        self.assertIn("Pattern-based", result["scope_note"])

    def test_clean_worker_payload_scan_carries_scope_note_without_blocking(self):
        result = scan_worker_payload({"content": "No synthetic secrets here."})

        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["finding_count"], 0)
        self.assertIn("Pattern-based", result["scope_note"])

    def test_worker_payload_redaction_preserves_shape(self):
        key = "tmrr_" + "abcdefghijk123456789"
        payload = {
            "content": {
                "summary": "candidate",
                "snippet": "token " + key,
            },
            "items": ["safe"],
        }

        redacted = redact_worker_payload(payload)

        self.assertEqual(redacted["items"], ["safe"])
        self.assertNotIn(key, redacted["content"]["snippet"])
        self.assertIn("[REDACTED_TRUSTMRR_API_KEY]", redacted["content"]["snippet"])


if __name__ == "__main__":
    unittest.main()
