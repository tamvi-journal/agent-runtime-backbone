import unittest

from runtime.contracts.enums import (
    MONITOR_STATUS_CLAIM_BLOCKED,
    MONITOR_STATUS_VERIFIED_COMPLETE,
    OBSIDIAN_CANDIDATE,
    OBSIDIAN_CANONICAL_REFERENCE,
    OBSIDIAN_NON_AUTHORITATIVE,
    VERIFICATION_FAILED,
    VERIFICATION_PARTIAL,
    VERIFICATION_PASSED,
)
from runtime.canonical.promotion import evaluate_promotion_request
from runtime.core.bridge import build_obsidian_vault_write


class CanonicalPromotionGateTest(unittest.TestCase):
    def test_blocks_promotion_when_verification_not_passed(self):
        result = evaluate_promotion_request(
            verification_status=VERIFICATION_PARTIAL,
            completion_claim_allowed=True,
            commit_status=MONITOR_STATUS_VERIFIED_COMPLETE,
            display_state="success",
            evidence_handles=["/tmp/evidence.txt"],
            reasons=[],
            current_canonical_status=OBSIDIAN_NON_AUTHORITATIVE,
            requested_target=OBSIDIAN_CANDIDATE,
            origin_kind="mainbrain",
        )

        self.assertEqual(result["decision"], "promotion_blocked")
        self.assertFalse(result["promotion_allowed"])
        self.assertEqual(result["target_status"], OBSIDIAN_NON_AUTHORITATIVE)

    def test_blocks_promotion_when_completion_claim_not_allowed(self):
        result = evaluate_promotion_request(
            verification_status=VERIFICATION_PASSED,
            completion_claim_allowed=False,
            commit_status=MONITOR_STATUS_VERIFIED_COMPLETE,
            display_state="success",
            evidence_handles=["/tmp/evidence.txt"],
            reasons=[],
            current_canonical_status=OBSIDIAN_NON_AUTHORITATIVE,
            requested_target=OBSIDIAN_CANDIDATE,
            origin_kind="mainbrain",
        )

        self.assertEqual(result["decision"], "promotion_blocked")
        self.assertFalse(result["promotion_allowed"])

    def test_blocks_promotion_when_display_state_not_success(self):
        result = evaluate_promotion_request(
            verification_status=VERIFICATION_PASSED,
            completion_claim_allowed=True,
            commit_status=MONITOR_STATUS_VERIFIED_COMPLETE,
            display_state="warning",
            evidence_handles=["/tmp/evidence.txt"],
            reasons=[],
            current_canonical_status=OBSIDIAN_NON_AUTHORITATIVE,
            requested_target=OBSIDIAN_CANDIDATE,
            origin_kind="mainbrain",
        )

        self.assertEqual(result["decision"], "promotion_blocked")
        self.assertIn("display_state_not_success", result["reasons"])

    def test_blocks_promotion_when_evidence_is_missing(self):
        result = evaluate_promotion_request(
            verification_status=VERIFICATION_PASSED,
            completion_claim_allowed=True,
            commit_status=MONITOR_STATUS_VERIFIED_COMPLETE,
            display_state="success",
            evidence_handles=[],
            reasons=[],
            current_canonical_status=OBSIDIAN_NON_AUTHORITATIVE,
            requested_target=OBSIDIAN_CANDIDATE,
            origin_kind="mainbrain",
        )

        self.assertEqual(result["decision"], "promotion_blocked")
        self.assertIn("missing_evidence_handles", result["reasons"])

    def test_allows_candidate_when_all_v0_1_conditions_pass(self):
        result = evaluate_promotion_request(
            verification_status=VERIFICATION_PASSED,
            completion_claim_allowed=True,
            commit_status=MONITOR_STATUS_VERIFIED_COMPLETE,
            display_state="success",
            evidence_handles=["/tmp/evidence.txt"],
            reasons=[],
            current_canonical_status=OBSIDIAN_NON_AUTHORITATIVE,
            requested_target=OBSIDIAN_CANDIDATE,
            origin_kind="mainbrain",
        )

        self.assertEqual(result["decision"], "allow_candidate")
        self.assertTrue(result["promotion_allowed"])
        self.assertEqual(result["target_status"], OBSIDIAN_CANDIDATE)

    def test_mainbrain_canonical_reference_request_returns_needs_approval(self):
        result = evaluate_promotion_request(
            verification_status=VERIFICATION_PASSED,
            completion_claim_allowed=True,
            commit_status=MONITOR_STATUS_VERIFIED_COMPLETE,
            display_state="success",
            evidence_handles=["/tmp/evidence.txt"],
            reasons=[],
            current_canonical_status=OBSIDIAN_NON_AUTHORITATIVE,
            requested_target=OBSIDIAN_CANONICAL_REFERENCE,
            origin_kind="mainbrain",
        )

        self.assertEqual(result["decision"], "needs_approval")
        self.assertFalse(result["promotion_allowed"])
        self.assertEqual(result["target_status"], OBSIDIAN_NON_AUTHORITATIVE)

    def test_delegate_origin_canonical_reference_request_is_blocked(self):
        result = evaluate_promotion_request(
            verification_status=VERIFICATION_PASSED,
            completion_claim_allowed=True,
            commit_status=MONITOR_STATUS_VERIFIED_COMPLETE,
            display_state="success",
            evidence_handles=["/tmp/evidence.txt"],
            reasons=[],
            current_canonical_status=OBSIDIAN_NON_AUTHORITATIVE,
            requested_target=OBSIDIAN_CANONICAL_REFERENCE,
            origin_kind="delegate",
        )

        self.assertEqual(result["decision"], "promotion_blocked")
        self.assertFalse(result["promotion_allowed"])
        self.assertIn("delegate_origin_cannot_promote", result["reasons"])

    def test_worker_origin_canonical_reference_request_is_blocked(self):
        result = evaluate_promotion_request(
            verification_status=VERIFICATION_PASSED,
            completion_claim_allowed=True,
            commit_status=MONITOR_STATUS_VERIFIED_COMPLETE,
            display_state="success",
            evidence_handles=["/tmp/evidence.txt"],
            reasons=[],
            current_canonical_status=OBSIDIAN_NON_AUTHORITATIVE,
            requested_target=OBSIDIAN_CANONICAL_REFERENCE,
            origin_kind="worker",
        )

        self.assertEqual(result["decision"], "promotion_blocked")
        self.assertFalse(result["promotion_allowed"])
        self.assertIn("worker_origin_cannot_promote", result["reasons"])

    def test_delegate_origin_cannot_direct_promote(self):
        result = evaluate_promotion_request(
            verification_status=VERIFICATION_PASSED,
            completion_claim_allowed=True,
            commit_status=MONITOR_STATUS_VERIFIED_COMPLETE,
            display_state="success",
            evidence_handles=["/tmp/evidence.txt"],
            reasons=[],
            current_canonical_status=OBSIDIAN_NON_AUTHORITATIVE,
            requested_target=OBSIDIAN_CANDIDATE,
            origin_kind="delegate",
        )

        self.assertEqual(result["decision"], "promotion_blocked")
        self.assertFalse(result["promotion_allowed"])
        self.assertIn("delegate_origin_cannot_promote", result["reasons"])

    def test_worker_origin_cannot_direct_promote(self):
        result = evaluate_promotion_request(
            verification_status=VERIFICATION_PASSED,
            completion_claim_allowed=True,
            commit_status=MONITOR_STATUS_VERIFIED_COMPLETE,
            display_state="success",
            evidence_handles=["/tmp/evidence.txt"],
            reasons=[],
            current_canonical_status=OBSIDIAN_NON_AUTHORITATIVE,
            requested_target=OBSIDIAN_CANDIDATE,
            origin_kind="worker",
        )

        self.assertEqual(result["decision"], "promotion_blocked")
        self.assertFalse(result["promotion_allowed"])
        self.assertIn("worker_origin_cannot_promote", result["reasons"])

    def test_existing_non_authoritative_default_law_still_holds(self):
        note = build_obsidian_vault_write(
            vault_path="ExampleAgent/Specs/test.md",
            note_type="spec",
            title="Test Spec",
            tags=["local-agent", "spec"],
            summary="Spec summary",
            body_markdown="# Test",
            source_session_id="session-1",
            verification_status=VERIFICATION_PASSED,
        )

        self.assertEqual(note["canonical_status"], OBSIDIAN_NON_AUTHORITATIVE)

    def test_existing_veto_reason_blocks_candidate(self):
        result = evaluate_promotion_request(
            verification_status=VERIFICATION_PASSED,
            completion_claim_allowed=True,
            commit_status=MONITOR_STATUS_VERIFIED_COMPLETE,
            display_state="success",
            evidence_handles=["/tmp/evidence.txt"],
            reasons=["worker_output_unverified_by_mainbrain"],
            current_canonical_status=OBSIDIAN_NON_AUTHORITATIVE,
            requested_target=OBSIDIAN_CANDIDATE,
            origin_kind="mainbrain",
        )

        self.assertEqual(result["decision"], "promotion_blocked")
        self.assertFalse(result["promotion_allowed"])

    def test_non_verified_commit_status_blocks_candidate(self):
        result = evaluate_promotion_request(
            verification_status=VERIFICATION_PASSED,
            completion_claim_allowed=True,
            commit_status=MONITOR_STATUS_CLAIM_BLOCKED,
            display_state="success",
            evidence_handles=["/tmp/evidence.txt"],
            reasons=[],
            current_canonical_status=OBSIDIAN_NON_AUTHORITATIVE,
            requested_target=OBSIDIAN_CANDIDATE,
            origin_kind="mainbrain",
        )

        self.assertEqual(result["decision"], "promotion_blocked")
        self.assertIn("commit_status_not_verified_complete", result["reasons"])


if __name__ == "__main__":
    unittest.main()
