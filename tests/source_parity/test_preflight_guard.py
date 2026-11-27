from __future__ import annotations

import copy
import unittest
from collections.abc import Mapping

from runtime.workers.preflight_guard import validate_worker_invocation_envelope


class PreflightGuardTest(unittest.TestCase):
    def base_envelope(self) -> dict[str, object]:
        return {
            "invocation_id": "inv-001",
            "task_id": "task-036",
            "requested_by": "MainBrain",
            "worker_id": "worker-research-1",
            "worker_type": "repo_research_worker",
            "invocation_purpose": "validate worker preflight boundaries",
            "input_scope": {
                "paths_allowed": ["Specs/canonical/worker_invocation_preflight_guard_design_v0.1.md"],
                "paths_excluded": [],
                "research_question": "validate worker preflight boundaries",
                "max_files": 5,
                "max_bytes_per_file": 20_000,
            },
            "permission_class": "read_only",
            "security_profile": "repo_read_only_no_network",
            "execution_surface": "direct_tool",
            "allowed_tools": ["read_file"],
            "forbidden_tools": [],
            "auto_allowed_actions": ["read_file"],
            "approval_required_actions": [],
            "blocked_actions": [],
            "side_effect_class": "none",
            "money_touching": False,
            "external_mutation": False,
            "network_access": False,
            "shell_access": False,
            "model_provider_policy": {"visibility": "not_visible_to_runtime"},
            "memory_context_policy": {"mode": "candidate_context_only"},
            "verification_expectation": {"mode": "verify_before_completion"},
            "governance_expectation": {"mode": "mainbrain_routing"},
            "output_contract": "WorkerOutputPacket",
            "return_path": "MainBrain/Agent routing",
            "escalation_policy": {"gate": "none"},
            "abort_conditions": [],
            "created_at": "2026-05-08T00:00:00Z",
        }

    def test_valid_read_only_repo_envelope_returns_allow(self):
        result = validate_worker_invocation_envelope(self.base_envelope())

        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["validated_permission_class"], "read_only")
        self.assertEqual(result["validated_security_profile"], "repo_read_only_no_network")
        self.assertEqual(result["validated_execution_surface"], "direct_tool")
        self.assertFalse(result["money_touching_detected"])
        self.assertFalse(result["external_mutation_detected"])
        self.assertFalse(result["network_detected"])
        self.assertFalse(result["shell_detected"])

    def test_bare_list_input_scope_returns_invalid_envelope(self):
        envelope = self.base_envelope()
        envelope["input_scope"] = ["Specs/canonical/worker_invocation_preflight_guard_design_v0.1.md"]

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "invalid_envelope")
        self.assertIn("invalid_input_scope", result["reasons"])

    def test_missing_envelope_returns_invalid_envelope(self):
        result = validate_worker_invocation_envelope(None)

        self.assertEqual(result["decision"], "invalid_envelope")
        self.assertIn("missing_or_non_mapping_envelope", result["reasons"])

    def test_missing_required_field_returns_invalid_envelope(self):
        envelope = self.base_envelope()
        envelope.pop("output_contract")

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "invalid_envelope")
        self.assertIn("missing_required_field:output_contract", result["reasons"])

    def test_unknown_permission_returns_invalid_envelope_or_block(self):
        envelope = self.base_envelope()
        envelope["permission_class"] = "mystery"

        result = validate_worker_invocation_envelope(envelope)

        self.assertIn(result["decision"], {"invalid_envelope", "block"})

    def test_unknown_security_returns_invalid_envelope_or_block(self):
        envelope = self.base_envelope()
        envelope["security_profile"] = "mystery"

        result = validate_worker_invocation_envelope(envelope)

        self.assertIn(result["decision"], {"invalid_envelope", "block"})

    def test_unknown_execution_surface_returns_invalid_envelope_or_block(self):
        envelope = self.base_envelope()
        envelope["execution_surface"] = "mystery"

        result = validate_worker_invocation_envelope(envelope)

        self.assertIn(result["decision"], {"invalid_envelope", "block"})

    def test_blocked_action_returns_block(self):
        envelope = self.base_envelope()
        envelope["requested_actions"] = ["delete_repo"]
        envelope["blocked_actions"] = ["delete_repo"]

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "block")
        self.assertIn("blocked_action:delete_repo", result["reasons"])

    def test_forbidden_tool_returns_block(self):
        envelope = self.base_envelope()
        envelope["requested_tools"] = ["shell"]
        envelope["forbidden_tools"] = ["shell"]

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "block")
        self.assertIn("forbidden_tool:shell", result["reasons"])

    def test_secret_path_in_input_scope_returns_block(self):
        envelope = self.base_envelope()
        envelope["input_scope"] = {
            "paths_allowed": [".env.local"],
            "paths_excluded": [],
            "research_question": "read env",
            "max_files": 1,
            "max_bytes_per_file": 100,
        }

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "block")
        self.assertIn("secret_path_in_worker_scope", result["reasons"])

    def test_approval_required_action_returns_needs_approval(self):
        envelope = self.base_envelope()
        envelope["requested_actions"] = ["repo_mutation"]
        envelope["approval_required_actions"] = ["repo_mutation"]
        envelope["side_effect_class"] = "repo_write_candidate"

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "needs_approval")
        self.assertIn("approval_required_action:repo_mutation", result["reasons"])

    def test_money_touching_true_without_risk_policy_returns_block(self):
        envelope = self.base_envelope()
        envelope["money_touching"] = True
        envelope["side_effect_class"] = "money_touching"
        envelope["escalation_policy"] = {"gate": "none"}

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "block")
        self.assertIn("money_touching_without_risk_policy", result["reasons"])

    def test_money_touching_true_with_risk_policy_returns_needs_approval(self):
        envelope = self.base_envelope()
        envelope["money_touching"] = True
        envelope["side_effect_class"] = "money_touching"
        envelope["escalation_policy"] = {"gate": "future_risk_policy"}

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "needs_approval")
        self.assertIn("money_touching_requires_approval", result["reasons"])

    def test_network_and_shell_combined_without_review_boundary_returns_block(self):
        envelope = self.base_envelope()
        envelope["network_access"] = True
        envelope["shell_access"] = True
        envelope["escalation_policy"] = {"gate": "none"}

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "block")
        self.assertIn("network_and_shell_without_review_boundary", result["reasons"])

    def test_delegated_subagent_requires_approval_unless_explicitly_allowed(self):
        envelope = self.base_envelope()
        envelope["execution_surface"] = "delegated_subagent"
        envelope["escalation_policy"] = {"gate": "required"}

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "needs_approval")
        self.assertIn("delegated_subagent_requires_approval", result["reasons"])

    def test_hermes_subprocess_blocks_or_needs_approval_by_default(self):
        envelope = self.base_envelope()
        envelope["execution_surface"] = "hermes_subprocess"
        envelope["escalation_policy"] = {"gate": "none"}

        result = validate_worker_invocation_envelope(envelope)

        self.assertIn(result["decision"], {"block", "needs_approval"})
        self.assertIn("hermes_subprocess_requires_approval", result["reasons"])

    def test_missing_output_contract_returns_invalid_envelope(self):
        envelope = self.base_envelope()
        envelope.pop("output_contract")

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "invalid_envelope")
        self.assertIn("missing_required_field:output_contract", result["reasons"])

    def test_missing_return_path_returns_invalid_envelope(self):
        envelope = self.base_envelope()
        envelope.pop("return_path")

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "invalid_envelope")
        self.assertIn("missing_required_field:return_path", result["reasons"])

    def test_model_provider_not_visible_reports_not_visible_to_runtime(self):
        envelope = self.base_envelope()
        envelope["model_provider_policy"] = {"visibility": "not_visible_to_runtime"}

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["model_provider_visibility_status"], "not_visible_to_runtime")

    def test_model_provider_change_request_returns_needs_approval_or_block(self):
        envelope = self.base_envelope()
        envelope["model_provider_policy"] = {"visibility": "visible", "change_requested": True}

        result = validate_worker_invocation_envelope(envelope)

        self.assertIn(result["decision"], {"needs_approval", "block"})

    def test_memory_write_request_returns_needs_approval_or_block(self):
        envelope = self.base_envelope()
        envelope["memory_context_policy"] = {"mode": "candidate_context_only", "write_requested": True}

        result = validate_worker_invocation_envelope(envelope)

        self.assertIn(result["decision"], {"needs_approval", "block"})

    def test_repo_read_side_effect_can_allow_under_read_only_envelope(self):
        envelope = self.base_envelope()
        envelope["side_effect_class"] = "repo_read"
        envelope["requested_actions"] = ["read_file"]

        result = validate_worker_invocation_envelope(envelope)

        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["side_effect_detected"], True)

    def test_repo_mutation_side_effect_returns_needs_approval_or_block(self):
        envelope = self.base_envelope()
        envelope["side_effect_class"] = "repo_mutation"
        envelope["requested_actions"] = ["repo_mutation"]
        envelope["approval_required_actions"] = ["repo_mutation"]

        result = validate_worker_invocation_envelope(envelope)

        self.assertIn(result["decision"], {"needs_approval", "block"})

    def test_helper_does_not_mutate_input_envelope(self):
        envelope = self.base_envelope()
        original = copy.deepcopy(envelope)

        validate_worker_invocation_envelope(envelope)

        self.assertEqual(envelope, original)


if __name__ == "__main__":
    unittest.main()
