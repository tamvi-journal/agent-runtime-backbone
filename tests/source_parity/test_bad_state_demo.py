import unittest

from runtime.contracts.enums import GATE_ALLOW, VERIFICATION_FAILED, VERIFICATION_PARTIAL
from runtime.mainbrain.bad_state_demo import run_bad_state_demo


class BadStateDemoTest(unittest.TestCase):
    def test_blocks_completion_claim_when_delegate_output_lacks_evidence(self):
        result = run_bad_state_demo(
            intended_action="finalize repo fix",
            executed_action="delegate reported completion",
            observed_outcome="worker says task is done",
            evidence_handles=[],
            verification_status=VERIFICATION_FAILED,
            completion_claim_requested=True,
            worker_claim_present=True,
            work_artifact_present=False,
            gate_decision=GATE_ALLOW,
        )

        self.assertEqual(result["commit_status"], "completion_claim_blocked")
        self.assertFalse(result["completion_claim_allowed"])
        self.assertEqual(result["display_state"], "failure")
        self.assertIn("completion not allowed", result["message"].lower())
        self.assertNotIn("completed", result["message"].lower())
        self.assertNotIn("done", result["message"].lower())

    def test_partial_completion_when_work_artifact_exists_but_verification_is_partial(self):
        result = run_bad_state_demo(
            intended_action="implement monitor demo",
            executed_action="files written locally",
            observed_outcome="artifact exists but readback incomplete",
            evidence_handles=["/tmp/demo.py"],
            verification_status=VERIFICATION_PARTIAL,
            completion_claim_requested=False,
            worker_claim_present=False,
            work_artifact_present=True,
            gate_decision=GATE_ALLOW,
        )

        self.assertEqual(result["commit_status"], "partial_completion")
        self.assertFalse(result["completion_claim_allowed"])
        self.assertEqual(result["display_state"], "warning")
        self.assertIn("completion not allowed", result["message"].lower())

    def test_implemented_but_unverified_when_evidence_exists_without_passed_verification(self):
        result = run_bad_state_demo(
            intended_action="update local report",
            executed_action="report edited",
            observed_outcome="changes present but not fully verified",
            evidence_handles=["/tmp/report.md"],
            verification_status=VERIFICATION_PARTIAL,
            completion_claim_requested=False,
            worker_claim_present=False,
            work_artifact_present=False,
            gate_decision=GATE_ALLOW,
        )

        self.assertEqual(result["commit_status"], "implemented_but_unverified")
        self.assertFalse(result["completion_claim_allowed"])
        self.assertEqual(result["display_state"], "warning")
        self.assertIn("verification_not_passed", result["reasons"])

    def test_claim_requested_with_partial_verification_stays_blocked(self):
        result = run_bad_state_demo(
            intended_action="ship result",
            executed_action="artifact produced",
            observed_outcome="work exists but verification is partial",
            evidence_handles=["/tmp/result.json"],
            verification_status=VERIFICATION_PARTIAL,
            completion_claim_requested=True,
            worker_claim_present=False,
            work_artifact_present=True,
            gate_decision=GATE_ALLOW,
        )

        self.assertEqual(result["commit_status"], "completion_claim_blocked")
        self.assertFalse(result["completion_claim_allowed"])
        self.assertEqual(result["display_state"], "failure")
        self.assertIn("completion_claim_without_verification", result["reasons"])


if __name__ == "__main__":
    unittest.main()
