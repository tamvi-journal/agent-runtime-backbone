from __future__ import annotations

from copy import deepcopy
from unittest.mock import Mock, patch
import unittest

from runtime.workers import worker_bridge_observability as observability_module


class WorkerBridgeObservabilityTest(unittest.TestCase):
    def test_disabled_result_produces_policy_disabled_stage(self) -> None:
        bridge_result = {
            "task_id": "task_048_disabled",
            "mode": "disabled",
            "decision": "disabled",
            "routing_decision": None,
            "builder_result": None,
            "invocation_result": None,
            "worker_output": None,
            "candidate_status": "not_applicable",
            "side_effect_request": None,
            "verification_needed": False,
            "governance_needed": False,
            "limitations": ["read-only"],
            "generated_at": "2024-01-01T00:00:00Z",
        }
        result = observability_module.build_worker_bridge_audit_record(bridge_result, event_id="evt-1", generated_at="2024-02-01T00:00:00Z")
        self.assertEqual(result["path_stage"], "policy_disabled")
        self.assertFalse(result["worker_execution_attempted"])
        self.assertFalse(result["worker_output_present"])
        self.assertEqual(result["authority_claims"], {
            "claims_truth": False,
            "claims_completion": False,
            "claims_approval": False,
            "claims_governance": False,
            "claims_side_effect_permission": False,
        })
        self.assertEqual(result["event_id"], "evt-1")
        self.assertEqual(result["generated_at"], "2024-02-01T00:00:00Z")

    def test_invalid_mode_result_produces_policy_invalid_mode_stage(self) -> None:
        result = observability_module.build_worker_bridge_audit_record({"mode": "unsupported", "decision": "invalid_mode"})
        self.assertEqual(result["path_stage"], "policy_invalid_mode")
        self.assertFalse(result["worker_execution_attempted"])

    def test_dry_run_ready_result_produces_dry_run_envelope_preview_stage(self) -> None:
        bridge_result = {
            "task_id": "task_048_dry_run_ready",
            "mode": "dry_run",
            "decision": "dry_run_ready",
            "routing_decision": {"decision": "route_repo_research_worker"},
            "builder_result": {"decision": "built_envelope"},
            "candidate_status": "preview_only",
            "side_effect_request": None,
            "verification_needed": False,
            "governance_needed": False,
            "limitations": ["read-only"],
            "generated_at": "2024-01-01T00:00:00Z",
        }
        result = observability_module.build_worker_bridge_audit_record(bridge_result)
        self.assertEqual(result["path_stage"], "dry_run_envelope_preview")
        self.assertFalse(result["worker_execution_attempted"])
        self.assertFalse(result["worker_output_present"])
        self.assertEqual(result["routing_decision"], "route_repo_research_worker")
        self.assertEqual(result["builder_decision"], "built_envelope")

    def test_dry_run_blocked_result_produces_dry_run_routing_stage(self) -> None:
        result = observability_module.build_worker_bridge_audit_record(
            {"mode": "dry_run", "decision": "dry_run_blocked", "routing_decision": {"decision": "blocked"}}
        )
        self.assertEqual(result["path_stage"], "dry_run_routing")

    def test_no_worker_needed_result_produces_routing_stopped_stage(self) -> None:
        result = observability_module.build_worker_bridge_audit_record({"mode": "enabled_read_only", "decision": "no_worker_needed", "routing_decision": {"decision": "no_worker_needed"}})
        self.assertEqual(result["path_stage"], "routing_stopped")

    def test_builder_blocked_result_produces_builder_stopped_stage(self) -> None:
        result = observability_module.build_worker_bridge_audit_record({"mode": "enabled_read_only", "decision": "builder_blocked", "builder_result": {"decision": "blocked"}})
        self.assertEqual(result["path_stage"], "builder_stopped")

    def test_invocation_blocked_result_produces_invocation_stopped_stage(self) -> None:
        result = observability_module.build_worker_bridge_audit_record({"mode": "enabled_read_only", "decision": "invocation_blocked", "invocation_result": {"decision": "blocked", "preflight": {"decision": "block"}}})
        self.assertEqual(result["path_stage"], "invocation_stopped")

    def test_completed_candidate_with_worker_output_produces_worker_candidate_returned_stage(self) -> None:
        bridge_result = {
            "task_id": "task_048_completed",
            "mode": "enabled_read_only",
            "decision": "completed_candidate",
            "routing_decision": {"decision": "route_repo_research_worker"},
            "builder_result": {"decision": "built_envelope"},
            "invocation_result": {"decision": "completed_candidate", "preflight": {"decision": "allow"}},
            "worker_output": {
                "worker_id": "repo_research_worker",
                "worker_type": "read_only_repo_research",
                "candidate_status": "candidate",
                "security_profile": "read_only",
                "execution_surface": "direct_tool",
            },
            "candidate_status": "candidate",
            "side_effect_request": None,
            "verification_needed": False,
            "governance_needed": False,
            "evidence_status": "claimed_only",
            "release_eligibility": "not_eligible_pending_verification",
            "release_gate": {"eligible_for_release": False, "release_eligibility": "not_eligible_pending_verification", "reason": "claimed_only"},
            "claimed_evidence_count": 1,
            "verified_evidence_count": 0,
            "limitations": ["read-only"],
            "generated_at": "2024-01-01T00:00:00Z",
        }
        result = observability_module.build_worker_bridge_audit_record(bridge_result)
        self.assertEqual(result["path_stage"], "worker_candidate_returned")
        self.assertTrue(result["worker_execution_attempted"])
        self.assertTrue(result["worker_output_present"])
        self.assertEqual(result["worker_id"], "repo_research_worker")
        self.assertEqual(result["worker_type"], "read_only_repo_research")
        self.assertEqual(result["candidate_status"], "candidate")
        self.assertEqual(result["security_profile"], "read_only")
        self.assertEqual(result["execution_surface"], "direct_tool")
        self.assertEqual(result["preflight_decision"], "allow")
        self.assertEqual(result["evidence_status"], "claimed_only")
        self.assertEqual(result["release_eligibility"], "not_eligible_pending_verification")
        self.assertFalse(result["release_gate"]["eligible_for_release"])
        self.assertEqual(result["claimed_evidence_count"], 1)
        self.assertEqual(result["verified_evidence_count"], 0)

    def test_worker_execution_attempted_is_false_for_disabled_and_dry_run(self) -> None:
        disabled = observability_module.build_worker_bridge_audit_record({"mode": "disabled", "decision": "disabled"})
        dry_run = observability_module.build_worker_bridge_audit_record({"mode": "dry_run", "decision": "dry_run_ready", "builder_result": {"decision": "built_envelope"}})
        self.assertFalse(disabled["worker_execution_attempted"])
        self.assertFalse(dry_run["worker_execution_attempted"])

    def test_worker_execution_attempted_is_true_when_invocation_result_is_present(self) -> None:
        result = observability_module.build_worker_bridge_audit_record({"mode": "enabled_read_only", "decision": "invocation_blocked", "invocation_result": {"decision": "blocked", "preflight": {"decision": "block"}}})
        self.assertTrue(result["worker_execution_attempted"])

    def test_worker_output_present_only_when_worker_output_exists(self) -> None:
        absent = observability_module.build_worker_bridge_audit_record({"mode": "dry_run", "decision": "dry_run_ready", "builder_result": {"decision": "built_envelope"}})
        present = observability_module.build_worker_bridge_audit_record({"mode": "enabled_read_only", "decision": "completed_candidate", "worker_output": {"candidate_status": "candidate"}})
        self.assertFalse(absent["worker_output_present"])
        self.assertTrue(present["worker_output_present"])

    def test_extracts_worker_identity_and_candidate_status_from_worker_output(self) -> None:
        result = observability_module.build_worker_bridge_audit_record({"mode": "enabled_read_only", "decision": "completed_candidate", "worker_output": {"worker_id": "repo_research_worker", "worker_type": "read_only_repo_research", "candidate_status": "candidate"}})
        self.assertEqual(result["worker_id"], "repo_research_worker")
        self.assertEqual(result["worker_type"], "read_only_repo_research")
        self.assertEqual(result["candidate_status"], "candidate")

    def test_extracts_security_profile_and_execution_surface_when_present(self) -> None:
        result = observability_module.build_worker_bridge_audit_record({"mode": "enabled_read_only", "decision": "completed_candidate", "worker_output": {"candidate_status": "candidate", "security_profile": "read_only", "execution_surface": "direct_tool"}})
        self.assertEqual(result["security_profile"], "read_only")
        self.assertEqual(result["execution_surface"], "direct_tool")

    def test_records_side_effect_request_without_approving_it(self) -> None:
        result = observability_module.build_worker_bridge_audit_record({"mode": "enabled_read_only", "decision": "completed_candidate", "side_effect_request": {"kind": "none"}})
        self.assertEqual(result["side_effect_request"], {"kind": "none"})
        self.assertEqual(result["authority_claims"]["claims_side_effect_permission"], False)

    def test_authority_claims_are_all_false(self) -> None:
        result = observability_module.build_worker_bridge_audit_record({"mode": "enabled_read_only", "decision": "completed_candidate"})
        self.assertEqual(result["authority_claims"], {
            "claims_truth": False,
            "claims_completion": False,
            "claims_approval": False,
            "claims_governance": False,
            "claims_side_effect_permission": False,
        })

    def test_does_not_include_verified_approved_complete_as_authority_decisions(self) -> None:
        result = observability_module.build_worker_bridge_audit_record({"mode": "enabled_read_only", "decision": "completed_candidate", "candidate_status": "candidate"})
        decision_blob = " ".join(str(result.get(key, "")) for key in ("decision", "path_stage", "candidate_status")).lower()
        self.assertNotIn("verified", decision_blob)
        self.assertNotIn("approved", decision_blob)
        self.assertNotEqual(result["decision"], "complete")
        self.assertNotEqual(result["path_stage"], "complete")
        self.assertFalse(result["authority_claims"]["claims_completion"])


    def test_observability_records_verified_evidence_release_eligibility(self) -> None:
        result = observability_module.build_worker_bridge_audit_record(
            {
                "mode": "enabled_read_only",
                "decision": "completed_candidate",
                "candidate_status": "candidate",
                "evidence_status": "externally_verified",
                "release_eligibility": "eligible_for_mainbrain_review",
                "release_gate": {"eligible_for_release": True, "release_eligibility": "eligible_for_mainbrain_review", "reason": "externally_verified"},
                "claimed_evidence_count": 1,
                "verified_evidence_count": 1,
                "verified_by": "MainBrain",
            }
        )

        self.assertEqual(result["evidence_status"], "externally_verified")
        self.assertEqual(result["release_eligibility"], "eligible_for_mainbrain_review")
        self.assertTrue(result["release_gate"]["eligible_for_release"])
        self.assertEqual(result["claimed_evidence_count"], 1)
        self.assertEqual(result["verified_evidence_count"], 1)
        self.assertEqual(result["verified_by"], "MainBrain")
        decision_blob = " ".join(str(result.get(key, "")) for key in ("decision", "path_stage", "candidate_status")).lower()
        self.assertNotIn("approved", decision_blob)
        self.assertNotIn("verified", decision_blob)

    def test_handles_missing_nested_fields_gracefully(self) -> None:
        result = observability_module.build_worker_bridge_audit_record({"decision": "unknown"})
        self.assertEqual(result["path_stage"], "unknown")
        self.assertIsNone(result["routing_decision"])
        self.assertIsNone(result["builder_decision"])
        self.assertIsNone(result["invocation_decision"])
        self.assertIsNone(result["preflight_decision"])

    def test_does_not_mutate_input_bridge_result(self) -> None:
        bridge_result = {"mode": "enabled_read_only", "decision": "completed_candidate", "worker_output": {"candidate_status": "candidate"}}
        bridge_before = deepcopy(bridge_result)
        _ = observability_module.build_worker_bridge_audit_record(bridge_result)
        self.assertEqual(bridge_result, bridge_before)

    def test_does_not_call_bridge_routing_builder_or_invocation_helpers(self) -> None:
        bridge_result = {"mode": "enabled_read_only", "decision": "completed_candidate", "worker_output": {"candidate_status": "candidate"}}
        with patch.object(observability_module, "run_worker_bridge_with_policy", side_effect=AssertionError("policy must not run"), create=True), \
             patch.object(observability_module, "run_mainbrain_worker_execution_bridge", side_effect=AssertionError("bridge must not run"), create=True), \
             patch.object(observability_module, "route_mainbrain_worker_request", side_effect=AssertionError("routing must not run"), create=True), \
             patch.object(observability_module, "build_worker_invocation_envelope_from_routing_decision", side_effect=AssertionError("builder must not run"), create=True), \
             patch.object(observability_module, "invoke_worker_with_envelope", side_effect=AssertionError("invocation must not run"), create=True):
            result = observability_module.build_worker_bridge_audit_record(bridge_result)
        self.assertEqual(result["decision"], "completed_candidate")


if __name__ == "__main__":
    unittest.main()
