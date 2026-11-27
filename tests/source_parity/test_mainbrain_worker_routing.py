from __future__ import annotations

from copy import deepcopy
import unittest

from runtime.workers.mainbrain_worker_routing import (
    DEFAULT_GENERATED_AT,
    REQUIRED_ENVELOPE_FIELDS,
    WORKER_ID,
    WORKER_TYPE,
    WORKFLOW_NETWORK_VS_RUNTIME_NETWORK,
    route_mainbrain_worker_request,
)


class MainBrainWorkerRoutingTests(unittest.TestCase):
    def _base_request(self) -> dict[str, object]:
        return {
            "task_id": "task_041",
            "user_request": "Please inspect the repo for the requested file.",
            "mainbrain_intent": "candidate_repo_evidence",
            "requested_evidence": "repo/local file evidence for spec readback",
            "candidate_paths": ["runtime/workers/repo_research_worker.py"],
            "forbidden_paths": ["runtime/task_runs"],
            "side_effect_intent": False,
            "network_intent": False,
            "money_touching_intent": False,
            "memory_mutation_intent": False,
            "model_provider_intent": "",
            "runtime_surface_intent": "direct_tool",
        }

    def test_valid_repo_evidence_routes_to_repo_research_worker(self) -> None:
        result = route_mainbrain_worker_request(self._base_request())
        self.assertEqual(result["decision"], "route_repo_research_worker")
        self.assertEqual(result["task_id"], "task_041")
        self.assertEqual(result["generated_at"], DEFAULT_GENERATED_AT)
        self.assertEqual(result["selected_worker"], {"worker_id": WORKER_ID, "worker_type": WORKER_TYPE})
        self.assertIsNotNone(result["proposed_input_scope"])
        self.assertIn(WORKFLOW_NETWORK_VS_RUNTIME_NETWORK, result["limitations"])

    def test_selected_worker_shape_is_repo_research_worker(self) -> None:
        result = route_mainbrain_worker_request(self._base_request())
        self.assertEqual(result["selected_worker"]["worker_id"], WORKER_ID)
        self.assertEqual(result["selected_worker"]["worker_type"], WORKER_TYPE)

    def test_proposed_input_scope_carries_candidate_paths(self) -> None:
        request = self._base_request()
        result = route_mainbrain_worker_request(request)
        scope = result["proposed_input_scope"]
        self.assertEqual(scope["paths_allowed"], request["candidate_paths"])
        self.assertEqual(scope["paths_excluded"], request["forbidden_paths"])
        self.assertEqual(scope["max_files"], 5)
        self.assertEqual(scope["max_bytes_per_file"], 20_000)

    def test_no_worker_needed_for_planning_without_repo_evidence(self) -> None:
        request = self._base_request()
        request["mainbrain_intent"] = "planning_discussion"
        request["requested_evidence"] = ""
        request["candidate_paths"] = []
        result = route_mainbrain_worker_request(request)
        self.assertEqual(result["decision"], "no_worker_needed")
        self.assertIsNone(result["selected_worker"])
        self.assertIsNone(result["proposed_input_scope"])

    def test_missing_required_field_returns_invalid_request(self) -> None:
        request = self._base_request()
        del request["task_id"]
        result = route_mainbrain_worker_request(request)
        self.assertEqual(result["decision"], "invalid_request")
        self.assertIn("missing_required_field:task_id", result["reasons"])

    def test_empty_candidate_paths_with_repo_evidence_returns_invalid_request(self) -> None:
        request = self._base_request()
        request["candidate_paths"] = []
        result = route_mainbrain_worker_request(request)
        self.assertEqual(result["decision"], "invalid_request")
        self.assertIn("candidate_paths_empty_for_repo_evidence", result["reasons"])

    def test_side_effect_intent_returns_needs_approval(self) -> None:
        request = self._base_request()
        request["side_effect_intent"] = True
        result = route_mainbrain_worker_request(request)
        self.assertEqual(result["decision"], "needs_approval")
        self.assertTrue(result["approval_required"])

    def test_network_intent_returns_needs_approval(self) -> None:
        request = self._base_request()
        request["network_intent"] = True
        result = route_mainbrain_worker_request(request)
        self.assertEqual(result["decision"], "needs_approval")
        self.assertTrue(result["approval_required"])

    def test_money_touching_intent_returns_blocked(self) -> None:
        request = self._base_request()
        request["money_touching_intent"] = True
        result = route_mainbrain_worker_request(request)
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("money_touching_route_forbidden", result["blocked_reasons"])

    def test_memory_mutation_intent_returns_needs_approval(self) -> None:
        request = self._base_request()
        request["memory_mutation_intent"] = True
        result = route_mainbrain_worker_request(request)
        self.assertEqual(result["decision"], "needs_approval")
        self.assertTrue(result["approval_required"])

    def test_delegated_subagent_runtime_intent_requires_review_or_block(self) -> None:
        request = self._base_request()
        request["runtime_surface_intent"] = "delegated_subagent"
        result = route_mainbrain_worker_request(request)
        self.assertIn(result["decision"], {"needs_approval", "blocked"})
        self.assertIsNone(result["selected_worker"])

    def test_hermes_subprocess_runtime_intent_requires_review_or_block(self) -> None:
        request = self._base_request()
        request["runtime_surface_intent"] = "hermes_subprocess"
        result = route_mainbrain_worker_request(request)
        self.assertIn(result["decision"], {"needs_approval", "blocked"})
        self.assertIsNone(result["selected_worker"])

    def test_dynamic_open_worker_request_returns_blocked(self) -> None:
        request = self._base_request()
        request["user_request"] = "Use the open worker registry and dynamic worker loading."
        result = route_mainbrain_worker_request(request)
        self.assertEqual(result["decision"], "blocked")
        self.assertTrue(result["blocked_reasons"])

    def test_unknown_worker_request_returns_blocked(self) -> None:
        request = self._base_request()
        request["user_request"] = "Invoke an unknown worker."
        result = route_mainbrain_worker_request(request)
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("unknown_worker_execution", result["blocked_reasons"])

    def test_worker_self_invocation_returns_blocked(self) -> None:
        request = self._base_request()
        request["user_request"] = "Let the worker self invocation route itself."
        result = route_mainbrain_worker_request(request)
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("worker_self_invocation", result["blocked_reasons"])

    def test_repo_mutation_through_repo_research_worker_returns_blocked(self) -> None:
        request = self._base_request()
        request["user_request"] = "Use repo mutation through repo research worker."
        result = route_mainbrain_worker_request(request)
        self.assertEqual(result["decision"], "blocked")
        self.assertIn("repo_mutation_via_repo_research_worker", result["blocked_reasons"])

    def test_model_provider_change_request_returns_needs_approval(self) -> None:
        request = self._base_request()
        request["model_provider_intent"] = "change model provider"
        result = route_mainbrain_worker_request(request)
        self.assertEqual(result["decision"], "needs_approval")
        self.assertTrue(result["approval_required"])

    def test_routing_result_does_not_include_worker_output(self) -> None:
        result = route_mainbrain_worker_request(self._base_request())
        self.assertNotIn("worker_output", result)
        self.assertNotEqual(result["decision"], "completed")
        self.assertNotEqual(result["decision"], "verified")
        self.assertNotEqual(result["decision"], "governed")

    def test_workflow_network_vs_runtime_network_distinction_is_preserved(self) -> None:
        result = route_mainbrain_worker_request(self._base_request())
        self.assertIn(WORKFLOW_NETWORK_VS_RUNTIME_NETWORK, result["limitations"])
        self.assertIn(WORKFLOW_NETWORK_VS_RUNTIME_NETWORK, result["reasons"])

    def test_helper_does_not_mutate_input_request(self) -> None:
        request = self._base_request()
        before = deepcopy(request)
        route_mainbrain_worker_request(request)
        self.assertEqual(request, before)

    def test_output_shape_contains_required_fields(self) -> None:
        result = route_mainbrain_worker_request(self._base_request())
        for field in (
            "task_id",
            "decision",
            "reasons",
            "selected_worker",
            "invocation_purpose",
            "proposed_input_scope",
            "required_envelope_fields",
            "approval_required",
            "blocked_reasons",
            "limitations",
            "next_step",
            "generated_at",
        ):
            self.assertIn(field, result)
        self.assertEqual(result["required_envelope_fields"], REQUIRED_ENVELOPE_FIELDS)
        self.assertFalse(result["approval_required"])


if __name__ == "__main__":
    unittest.main()
