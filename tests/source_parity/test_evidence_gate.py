from __future__ import annotations

import unittest

from runtime.workers.evidence_gate import (
    EVIDENCE_STATUS_CLAIMED_ONLY,
    EVIDENCE_STATUS_EXTERNALLY_VERIFIED,
    EVIDENCE_STATUS_MISSING,
    RELEASE_ELIGIBLE_FOR_MAINBRAIN_REVIEW,
    RELEASE_NOT_ELIGIBLE_PENDING_VERIFICATION,
    build_worker_evidence_gate,
)


class WorkerEvidenceGateTest(unittest.TestCase):
    def test_claimed_worker_evidence_alone_is_not_release_eligible(self) -> None:
        worker_output = {
            "evidence_handles": [
                {
                    "path": "runtime/workers/repo_research_worker.py",
                    "locator": "content match",
                    "claim_supported": "candidate evidence",
                }
            ]
        }

        result = build_worker_evidence_gate(worker_output, {})

        self.assertEqual(result["evidence_status"], EVIDENCE_STATUS_CLAIMED_ONLY)
        self.assertEqual(result["release_eligibility"], RELEASE_NOT_ELIGIBLE_PENDING_VERIFICATION)
        self.assertTrue(result["verification_needed"])
        self.assertFalse(result["release_gate"]["eligible_for_release"])
        self.assertEqual(result["claimed_evidence_count"], 1)
        self.assertEqual(result["verified_evidence_count"], 0)

    def test_valid_external_verified_evidence_makes_candidate_eligible_for_mainbrain_review(self) -> None:
        worker_output = {"evidence_handles": [{"path": "docs/spec.md", "locator": "readback"}]}
        envelope = {
            "verified_evidence": {
                "verified_by": "MainBrain",
                "evidence_handles": [{"path": "docs/spec.md", "locator": "external readback"}],
                "checks_run": ["external_file_readback"],
            }
        }

        result = build_worker_evidence_gate(worker_output, envelope)

        self.assertEqual(result["evidence_status"], EVIDENCE_STATUS_EXTERNALLY_VERIFIED)
        self.assertEqual(result["release_eligibility"], RELEASE_ELIGIBLE_FOR_MAINBRAIN_REVIEW)
        self.assertFalse(result["verification_needed"])
        self.assertTrue(result["release_gate"]["eligible_for_release"])
        self.assertEqual(result["verified_by"], "MainBrain")
        self.assertEqual(result["verified_evidence_count"], 1)
        self.assertEqual(result["verified_checks_run"], ["external_file_readback"])

    def test_verified_evidence_without_verifier_is_still_claimed_only(self) -> None:
        worker_output = {"evidence_handles": [{"path": "docs/spec.md"}]}
        envelope = {"verified_evidence": {"evidence_handles": [{"path": "docs/spec.md"}]}}

        result = build_worker_evidence_gate(worker_output, envelope)

        self.assertEqual(result["evidence_status"], EVIDENCE_STATUS_CLAIMED_ONLY)
        self.assertEqual(result["release_eligibility"], RELEASE_NOT_ELIGIBLE_PENDING_VERIFICATION)
        self.assertTrue(result["verification_needed"])

    def test_verified_evidence_without_artifact_is_not_release_eligible(self) -> None:
        worker_output = {"evidence_handles": [{"path": "docs/spec.md"}]}
        envelope = {
            "verified_evidence": {
                "verified_by": "MainBrain",
                "checks_run": ["external_file_readback"],
            }
        }

        result = build_worker_evidence_gate(worker_output, envelope)

        self.assertEqual(result["evidence_status"], EVIDENCE_STATUS_CLAIMED_ONLY)
        self.assertEqual(result["release_eligibility"], RELEASE_NOT_ELIGIBLE_PENDING_VERIFICATION)
        self.assertTrue(result["verification_needed"])
        self.assertTrue(any(item["kind"] == "verifier_artifact_missing" for item in result["evidence_findings"]))

    def test_worker_identity_cannot_self_verify(self) -> None:
        worker_output = {"evidence_handles": [{"path": "docs/spec.md"}]}
        envelope = {
            "worker_id": "repo_research_worker",
            "verified_evidence": {
                "verified_by": "repo_research_worker",
                "evidence_handles": [{"path": "docs/spec.md", "locator": "external readback"}],
                "checks_run": ["external_file_readback"],
            },
        }

        result = build_worker_evidence_gate(worker_output, envelope)

        self.assertEqual(result["evidence_status"], EVIDENCE_STATUS_CLAIMED_ONLY)
        self.assertEqual(result["release_eligibility"], RELEASE_NOT_ELIGIBLE_PENDING_VERIFICATION)
        self.assertTrue(any(item["kind"] == "self_verification" for item in result["evidence_findings"]))

    def test_missing_claimed_evidence_is_not_release_eligible(self) -> None:
        result = build_worker_evidence_gate({}, {})

        self.assertEqual(result["evidence_status"], EVIDENCE_STATUS_MISSING)
        self.assertEqual(result["release_eligibility"], RELEASE_NOT_ELIGIBLE_PENDING_VERIFICATION)
        self.assertTrue(result["verification_needed"])
        self.assertFalse(result["release_gate"]["eligible_for_release"])

    def test_does_not_mutate_worker_output_or_envelope(self) -> None:
        worker_output = {"evidence_handles": [{"path": "docs/spec.md"}]}
        envelope = {
            "verified_evidence": {
                "verified_by": "MainBrain",
                "evidence_handles": [{"path": "docs/spec.md"}],
                "checks_run": ["readback"],
            }
        }
        before_worker = {"evidence_handles": [{"path": "docs/spec.md"}]}
        before_envelope = {
            "verified_evidence": {
                "verified_by": "MainBrain",
                "evidence_handles": [{"path": "docs/spec.md"}],
                "checks_run": ["readback"],
            }
        }

        _ = build_worker_evidence_gate(worker_output, envelope)

        self.assertEqual(worker_output, before_worker)
        self.assertEqual(envelope, before_envelope)


if __name__ == "__main__":
    unittest.main()
