from __future__ import annotations

import copy
import unittest

from runtime.workers.routing_decision_to_envelope import (
    DEFAULT_GENERATED_AT,
    build_worker_invocation_envelope_from_routing_decision,
)


class RoutingDecisionToEnvelopeBuilderTests(unittest.TestCase):
    def base_routing_decision(self) -> dict[str, object]:
        return {
            "task_id": "task_044",
            "decision": "route_repo_research_worker",
            "reasons": ["candidate_repo_evidence", "Workflow network ≠ runtime network."],
            "selected_worker": {
                "worker_id": "repo_research_worker",
                "worker_type": "read_only_repo_research",
            },
            "invocation_purpose": "candidate_repo_evidence",
            "proposed_input_scope": {
                "paths_allowed": ["runtime/workers/mainbrain_worker_routing.py"],
                "paths_excluded": ["runtime/task_runs"],
                "research_question": "Inspect routing helper behavior.",
                "max_files": 5,
                "max_bytes_per_file": 20_000,
            },
            "required_envelope_fields": ["invocation_id", "task_id", "requested_by"],
            "approval_required": False,
            "blocked_reasons": [],
            "limitations": ["Workflow network ≠ runtime network."],
            "next_step": "Build a WorkerInvocationEnvelope.",
            "generated_at": DEFAULT_GENERATED_AT,
        }

    def test_valid_repo_research_decision_builds_envelope(self) -> None:
        result = build_worker_invocation_envelope_from_routing_decision(
            self.base_routing_decision(),
            requested_by="MainBrain",
            invocation_id="inv-044",
            created_at="2026-05-08T00:00:00Z",
        )

        self.assertEqual(result["decision"], "built_envelope")
        self.assertEqual(result["task_id"], "task_044")
        self.assertEqual(result["invocation_id"], "inv-044")
        self.assertIsNotNone(result["envelope"])

    def test_envelope_worker_identity_is_repo_research_worker(self) -> None:
        result = build_worker_invocation_envelope_from_routing_decision(
            self.base_routing_decision(),
            requested_by="MainBrain",
        )

        self.assertEqual(result["envelope"]["worker_id"], "repo_research_worker")
        self.assertEqual(result["envelope"]["worker_type"], "read_only_repo_research")

    def test_envelope_permission_security_and_execution_surface_are_read_only_direct_tool(self) -> None:
        result = build_worker_invocation_envelope_from_routing_decision(
            self.base_routing_decision(),
            requested_by="MainBrain",
        )
        envelope = result["envelope"]

        self.assertEqual(envelope["permission_class"], "read_only")
        self.assertEqual(envelope["security_profile"], "repo_read_only_no_network")
        self.assertEqual(envelope["execution_surface"], "direct_tool")

    def test_envelope_side_effect_class_is_repo_read(self) -> None:
        result = build_worker_invocation_envelope_from_routing_decision(
            self.base_routing_decision(),
            requested_by="MainBrain",
        )

        self.assertEqual(result["envelope"]["side_effect_class"], "repo_read")

    def test_envelope_runtime_flags_are_false(self) -> None:
        result = build_worker_invocation_envelope_from_routing_decision(
            self.base_routing_decision(),
            requested_by="MainBrain",
        )
        envelope = result["envelope"]

        self.assertFalse(envelope["money_touching"])
        self.assertFalse(envelope["external_mutation"])
        self.assertFalse(envelope["network_access"])
        self.assertFalse(envelope["shell_access"])

    def test_input_scope_preserves_paths_allowed(self) -> None:
        decision = self.base_routing_decision()
        result = build_worker_invocation_envelope_from_routing_decision(
            decision,
            requested_by="MainBrain",
        )

        self.assertEqual(
            result["envelope"]["input_scope"]["paths_allowed"],
            decision["proposed_input_scope"]["paths_allowed"],
        )

    def test_input_scope_preserves_paths_excluded(self) -> None:
        decision = self.base_routing_decision()
        result = build_worker_invocation_envelope_from_routing_decision(
            decision,
            requested_by="MainBrain",
        )

        self.assertEqual(
            result["envelope"]["input_scope"]["paths_excluded"],
            decision["proposed_input_scope"]["paths_excluded"],
        )

    def test_builder_does_not_add_paths(self) -> None:
        decision = self.base_routing_decision()
        result = build_worker_invocation_envelope_from_routing_decision(
            decision,
            requested_by="MainBrain",
        )

        self.assertEqual(result["envelope"]["input_scope"]["paths_allowed"], ["runtime/workers/mainbrain_worker_routing.py"])
        self.assertEqual(result["envelope"]["input_scope"]["paths_allowed"], decision["proposed_input_scope"]["paths_allowed"])

    def test_builder_copies_mutable_input_and_does_not_mutate_routing_decision(self) -> None:
        decision = self.base_routing_decision()
        before = copy.deepcopy(decision)
        result = build_worker_invocation_envelope_from_routing_decision(
            decision,
            requested_by="MainBrain",
        )

        result["envelope"]["input_scope"]["paths_allowed"].append("runtime/workers/extra.py")
        result["envelope"]["input_scope"]["paths_excluded"].append("runtime/secret")
        self.assertEqual(decision, before)

    def test_missing_requested_by_returns_invalid_routing_decision(self) -> None:
        result = build_worker_invocation_envelope_from_routing_decision(self.base_routing_decision(), requested_by="")

        self.assertEqual(result["decision"], "invalid_routing_decision")
        self.assertIsNone(result["envelope"])

    def test_missing_task_id_returns_invalid_routing_decision(self) -> None:
        decision = self.base_routing_decision()
        decision.pop("task_id")

        result = build_worker_invocation_envelope_from_routing_decision(decision, requested_by="MainBrain")

        self.assertEqual(result["decision"], "invalid_routing_decision")
        self.assertIsNone(result["envelope"])

    def test_non_route_decision_is_invalid_or_blocked(self) -> None:
        decision = self.base_routing_decision()
        decision["decision"] = "route_other_worker"

        result = build_worker_invocation_envelope_from_routing_decision(decision, requested_by="MainBrain")

        self.assertIn(result["decision"], {"invalid_routing_decision", "blocked"})
        self.assertIsNone(result["envelope"])

    def test_unknown_worker_returns_blocked(self) -> None:
        decision = self.base_routing_decision()
        decision["selected_worker"] = {"worker_id": "unknown_worker", "worker_type": "read_only_repo_research"}

        result = build_worker_invocation_envelope_from_routing_decision(decision, requested_by="MainBrain")

        self.assertEqual(result["decision"], "blocked")
        self.assertIsNone(result["envelope"])

    def test_missing_proposed_input_scope_returns_invalid_routing_decision(self) -> None:
        decision = self.base_routing_decision()
        decision.pop("proposed_input_scope")

        result = build_worker_invocation_envelope_from_routing_decision(decision, requested_by="MainBrain")

        self.assertEqual(result["decision"], "invalid_routing_decision")
        self.assertIsNone(result["envelope"])

    def test_empty_paths_allowed_returns_invalid_routing_decision(self) -> None:
        decision = self.base_routing_decision()
        decision["proposed_input_scope"]["paths_allowed"] = []

        result = build_worker_invocation_envelope_from_routing_decision(decision, requested_by="MainBrain")

        self.assertEqual(result["decision"], "invalid_routing_decision")
        self.assertIsNone(result["envelope"])

    def test_approval_required_true_refuses_envelope(self) -> None:
        decision = self.base_routing_decision()
        decision["approval_required"] = True

        result = build_worker_invocation_envelope_from_routing_decision(decision, requested_by="MainBrain")

        self.assertEqual(result["decision"], "invalid_routing_decision")
        self.assertIsNone(result["envelope"])

    def test_blocked_reasons_present_refuses_envelope(self) -> None:
        decision = self.base_routing_decision()
        decision["blocked_reasons"] = ["unsafe_route"]

        result = build_worker_invocation_envelope_from_routing_decision(decision, requested_by="MainBrain")

        self.assertEqual(result["decision"], "blocked")
        self.assertIsNone(result["envelope"])

    def test_network_intent_marker_blocks(self) -> None:
        decision = self.base_routing_decision()
        decision["reasons"] = ["runtime network requested"]

        result = build_worker_invocation_envelope_from_routing_decision(decision, requested_by="MainBrain")

        self.assertEqual(result["decision"], "blocked")
        self.assertIsNone(result["envelope"])

    def test_money_touching_marker_blocks(self) -> None:
        decision = self.base_routing_decision()
        decision["invocation_purpose"] = "money-touching research"

        result = build_worker_invocation_envelope_from_routing_decision(decision, requested_by="MainBrain")

        self.assertEqual(result["decision"], "blocked")
        self.assertIsNone(result["envelope"])

    def test_subagent_or_hermes_marker_blocks(self) -> None:
        decision = self.base_routing_decision()
        decision["next_step"] = "spawn subagent via hermes_subprocess"

        result = build_worker_invocation_envelope_from_routing_decision(decision, requested_by="MainBrain")

        self.assertEqual(result["decision"], "blocked")
        self.assertIsNone(result["envelope"])

    def test_builder_output_does_not_contain_worker_output(self) -> None:
        result = build_worker_invocation_envelope_from_routing_decision(
            self.base_routing_decision(),
            requested_by="MainBrain",
        )

        self.assertNotIn("worker_output", result)
        self.assertNotIn("worker_output", result["envelope"])

    def test_built_envelope_does_not_claim_approval_execution_verification_or_governance(self) -> None:
        result = build_worker_invocation_envelope_from_routing_decision(
            self.base_routing_decision(),
            requested_by="MainBrain",
        )

        self.assertEqual(result["decision"], "built_envelope")
        self.assertNotIn("approved", result)
        self.assertNotIn("execution_result", result)
        self.assertNotIn("verification_result", result)
        self.assertNotIn("governance_result", result)
        self.assertEqual(result["envelope"]["verification_expectation"]["completion_authority"], "verification_only")
        self.assertEqual(result["envelope"]["governance_expectation"]["governance_authority"], "governance_only")

    def test_workflow_network_vs_runtime_network_is_preserved(self) -> None:
        result = build_worker_invocation_envelope_from_routing_decision(
            self.base_routing_decision(),
            requested_by="MainBrain",
        )

        self.assertIn("Workflow network ≠ runtime network.", result["reasons"])
        self.assertIn("Workflow network ≠ runtime network.", result["limitations"])
        self.assertFalse(result["envelope"]["network_access"])

    def test_path_traversal_marker_in_paths_allowed_is_blocked(self) -> None:
        decision = self.base_routing_decision()
        decision["proposed_input_scope"]["paths_allowed"] = ["../secrets.txt"]

        result = build_worker_invocation_envelope_from_routing_decision(decision, requested_by="MainBrain")

        self.assertEqual(result["decision"], "blocked")
        self.assertIsNone(result["envelope"])

    def test_default_invocation_purpose_falls_back_to_candidate_repo_evidence(self) -> None:
        decision = self.base_routing_decision()
        decision.pop("invocation_purpose")

        result = build_worker_invocation_envelope_from_routing_decision(decision, requested_by="MainBrain")

        self.assertEqual(result["decision"], "built_envelope")
        self.assertEqual(result["envelope"]["invocation_purpose"], "candidate_repo_evidence")


if __name__ == "__main__":
    unittest.main()
