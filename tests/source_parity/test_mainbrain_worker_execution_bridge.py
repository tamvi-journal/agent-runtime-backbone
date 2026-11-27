from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

import runtime.workers.mainbrain_worker_execution_bridge as bridge_module
from runtime.workers.mainbrain_worker_routing import route_mainbrain_worker_request
from runtime.workers.routing_decision_to_envelope import build_worker_invocation_envelope_from_routing_decision
from runtime.workers.controlled_invocation import invoke_worker_with_envelope


class MainBrainWorkerExecutionBridgeTest(unittest.TestCase):
    def _make_temp_repo(self) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        repo_root = Path(temp_dir.name)
        target_file = repo_root / "docs" / "bridge_target.md"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(
            "BRIDGE_SMOKE_MARKER: evidence from routing to builder to controlled invocation.\n",
            encoding="utf-8",
        )
        return temp_dir, repo_root, target_file

    def _base_request(self, candidate_path: str) -> dict[str, object]:
        return {
            "task_id": "task_046_bridge_smoke",
            "user_request": "Find the bridge smoke marker.",
            "mainbrain_intent": "candidate_repo_evidence",
            "requested_evidence": "repo/local-file evidence",
            "candidate_paths": [candidate_path],
            "forbidden_paths": [],
            "side_effect_intent": False,
            "network_intent": False,
            "money_touching_intent": False,
            "memory_mutation_intent": False,
            "model_provider_intent": "none",
            "runtime_surface_intent": "direct_tool",
        }

    def _run_direct_chain(self, request: dict[str, object], repo_root: Path):
        routing_decision = route_mainbrain_worker_request(request)
        if routing_decision["decision"] != "route_repo_research_worker":
            return routing_decision, None, None, None

        builder_result = build_worker_invocation_envelope_from_routing_decision(
            routing_decision,
            requested_by="MainBrain",
            invocation_id="task_046_invocation",
            created_at="task_046_static_timestamp",
        )
        if builder_result["decision"] != "built_envelope":
            return routing_decision, builder_result, None, None

        invocation_result = invoke_worker_with_envelope(builder_result["envelope"], repo_root)
        return routing_decision, builder_result, invocation_result, invocation_result.get("worker_output")

    def test_valid_repo_evidence_request_runs_full_bridge_and_returns_completed_candidate(self) -> None:
        temp_dir, repo_root, target_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/bridge_target.md")
        request_before = deepcopy(request)

        bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(
            request,
            repo_root,
            requested_by="MainBrain",
            invocation_id="task_046_invocation",
            created_at="task_046_static_timestamp",
        )

        direct_routing, direct_builder, direct_invocation, direct_worker_output = self._run_direct_chain(request_before, repo_root)

        self.assertEqual(bridge_result["decision"], "completed_candidate")
        self.assertEqual(bridge_result["routing_decision"]["decision"], direct_routing["decision"])
        self.assertIsNotNone(bridge_result["builder_result"])
        self.assertIsNotNone(bridge_result["invocation_result"])
        self.assertIsNotNone(bridge_result["worker_output"])
        self.assertEqual(bridge_result["worker_output"]["candidate_status"], "candidate")
        self.assertIsNone(bridge_result["side_effect_request"])
        self.assertEqual(bridge_result["verification_needed"], direct_invocation["verification_needed"])
        self.assertEqual(bridge_result["governance_needed"], direct_invocation["governance_needed"])
        self.assertEqual(bridge_result["worker_output"]["content"]["findings"][0]["path"], target_file.relative_to(repo_root).as_posix())
        self.assertEqual(target_file.read_text(encoding="utf-8"), "BRIDGE_SMOKE_MARKER: evidence from routing to builder to controlled invocation.\n")
        self.assertEqual(request, request_before)
        self.assertEqual(bridge_result["builder_result"]["decision"], direct_builder["decision"])
        self.assertEqual(bridge_result["invocation_result"]["decision"], direct_invocation["decision"])
        self.assertEqual(bridge_result["worker_output"]["candidate_status"], direct_worker_output["candidate_status"])
        self.assertEqual(bridge_result["worker_output"]["content"]["findings"][0]["path"], direct_worker_output["content"]["findings"][0]["path"])
        self.assertEqual(bridge_result["worker_output"]["content"]["findings"][0]["status"], direct_worker_output["content"]["findings"][0]["status"])
        self.assertEqual(bridge_result["worker_output"]["content"]["findings"][0]["snippets"][0]["snippet"], direct_worker_output["content"]["findings"][0]["snippets"][0]["snippet"])
        self.assertEqual(bridge_result["evidence_status"], direct_invocation["evidence_status"])
        self.assertEqual(bridge_result["release_eligibility"], direct_invocation["release_eligibility"])
        self.assertFalse(bridge_result["release_gate"]["eligible_for_release"])
        self.assertEqual(bridge_result["claimed_evidence_count"], direct_invocation["claimed_evidence_count"])
        self.assertEqual(bridge_result["verified_evidence_count"], 0)

    def test_routing_decision_is_present(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(self._base_request("docs/bridge_target.md"), repo_root)
        self.assertIn("routing_decision", bridge_result)
        self.assertEqual(bridge_result["routing_decision"]["decision"], "route_repo_research_worker")

    def test_builder_result_is_present_on_positive_path(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(self._base_request("docs/bridge_target.md"), repo_root)
        self.assertIn("builder_result", bridge_result)
        self.assertEqual(bridge_result["builder_result"]["decision"], "built_envelope")

    def test_invocation_result_is_present_on_positive_path(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(self._base_request("docs/bridge_target.md"), repo_root)
        self.assertIn("invocation_result", bridge_result)
        self.assertEqual(bridge_result["invocation_result"]["decision"], "completed_candidate")

    def test_worker_output_is_present_on_completed_candidate(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(self._base_request("docs/bridge_target.md"), repo_root)
        self.assertIn("worker_output", bridge_result)
        self.assertEqual(bridge_result["worker_output"]["candidate_status"], "candidate")

    def test_side_effect_request_is_none(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(self._base_request("docs/bridge_target.md"), repo_root)
        self.assertIsNone(bridge_result["side_effect_request"])

    def test_scoped_file_remains_unchanged(self) -> None:
        temp_dir, repo_root, target_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        original = target_file.read_text(encoding="utf-8")
        _ = bridge_module.run_mainbrain_worker_execution_bridge(self._base_request("docs/bridge_target.md"), repo_root)
        self.assertEqual(target_file.read_text(encoding="utf-8"), original)

    def test_no_worker_needed_stops_before_builder_and_invocation(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/bridge_target.md")
        request["mainbrain_intent"] = "planning_only"
        request["requested_evidence"] = ""
        builder = Mock(side_effect=AssertionError("builder must not run"))
        invocation = Mock(side_effect=AssertionError("invocation must not run"))
        with (
            patch.object(bridge_module, "build_worker_invocation_envelope_from_routing_decision", builder),
            patch.object(bridge_module, "invoke_worker_with_envelope", invocation),
        ):
            bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(request, repo_root)
        self.assertEqual(bridge_result["decision"], "no_worker_needed")
        builder.assert_not_called()
        invocation.assert_not_called()

    def test_money_touching_request_stops_before_builder_and_invocation(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/bridge_target.md")
        request["money_touching_intent"] = True
        builder = Mock(side_effect=AssertionError("builder must not run"))
        invocation = Mock(side_effect=AssertionError("invocation must not run"))
        with (
            patch.object(bridge_module, "build_worker_invocation_envelope_from_routing_decision", builder),
            patch.object(bridge_module, "invoke_worker_with_envelope", invocation),
        ):
            bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(request, repo_root)
        self.assertEqual(bridge_result["decision"], "blocked")
        builder.assert_not_called()
        invocation.assert_not_called()

    def test_network_intent_request_stops_before_builder_and_invocation(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/bridge_target.md")
        request["network_intent"] = True
        builder = Mock(side_effect=AssertionError("builder must not run"))
        invocation = Mock(side_effect=AssertionError("invocation must not run"))
        with (
            patch.object(bridge_module, "build_worker_invocation_envelope_from_routing_decision", builder),
            patch.object(bridge_module, "invoke_worker_with_envelope", invocation),
        ):
            bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(request, repo_root)
        self.assertIn(bridge_result["decision"], {"needs_approval", "blocked"})
        builder.assert_not_called()
        invocation.assert_not_called()

    def test_empty_candidate_paths_stops_before_builder_and_invocation(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/bridge_target.md")
        request["candidate_paths"] = []
        builder = Mock(side_effect=AssertionError("builder must not run"))
        invocation = Mock(side_effect=AssertionError("invocation must not run"))
        with (
            patch.object(bridge_module, "build_worker_invocation_envelope_from_routing_decision", builder),
            patch.object(bridge_module, "invoke_worker_with_envelope", invocation),
        ):
            bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(request, repo_root)
        self.assertEqual(bridge_result["decision"], "invalid_request")
        builder.assert_not_called()
        invocation.assert_not_called()

    def test_builder_invalid_result_maps_to_invalid_routing_decision(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/bridge_target.md")
        builder_result = {
            "task_id": "task_046_bridge_smoke",
            "decision": "invalid_routing_decision",
            "invocation_id": None,
            "envelope": None,
            "reasons": ["routing_decision_must_be_mapping"],
            "limitations": ["Workflow network ≠ runtime network."],
            "generated_at": "1970-01-01T00:00:00Z",
        }
        builder = Mock(return_value=builder_result)
        invocation = Mock(side_effect=AssertionError("invocation must not run"))
        with (
            patch.object(bridge_module, "build_worker_invocation_envelope_from_routing_decision", builder),
            patch.object(bridge_module, "invoke_worker_with_envelope", invocation),
        ):
            bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(request, repo_root)
        self.assertEqual(bridge_result["decision"], "invalid_routing_decision")
        self.assertEqual(bridge_result["builder_result"], builder_result)
        invocation.assert_not_called()

    def test_builder_blocked_result_maps_to_builder_blocked(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/bridge_target.md")
        builder_result = {
            "task_id": "task_046_bridge_smoke",
            "decision": "blocked",
            "invocation_id": None,
            "envelope": None,
            "reasons": ["unknown_or_unsupported_worker"],
            "limitations": ["Workflow network ≠ runtime network."],
            "generated_at": "1970-01-01T00:00:00Z",
        }
        builder = Mock(return_value=builder_result)
        invocation = Mock(side_effect=AssertionError("invocation must not run"))
        with (
            patch.object(bridge_module, "build_worker_invocation_envelope_from_routing_decision", builder),
            patch.object(bridge_module, "invoke_worker_with_envelope", invocation),
        ):
            bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(request, repo_root)
        self.assertEqual(bridge_result["decision"], "builder_blocked")
        self.assertEqual(bridge_result["builder_result"], builder_result)
        invocation.assert_not_called()

    def test_invocation_block_maps_to_invocation_blocked(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/bridge_target.md")
        invocation_result = {
            "invocation_id": "task_046_invocation",
            "task_id": "task_046_bridge_smoke",
            "worker_id": "repo_research_worker",
            "worker_type": "read_only_repo_research",
            "decision": "blocked",
            "preflight": {"decision": "blocked"},
            "worker_output": None,
            "return_path": {"target": "MainBrain", "mode": "candidate_contribution"},
            "candidate_status": "blocked",
            "side_effect_request": None,
            "verification_needed": False,
            "governance_needed": False,
            "limitations": ["Workflow network ≠ runtime network."],
            "generated_at": "2026-01-01T00:00:00Z",
        }
        invocation = Mock(return_value=invocation_result)
        with (
            patch.object(bridge_module, "invoke_worker_with_envelope", invocation),
        ):
            bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(request, repo_root)
        self.assertEqual(bridge_result["decision"], "invocation_blocked")
        self.assertEqual(bridge_result["invocation_result"], invocation_result)
        self.assertNotIn("worker_output", bridge_result)

    def test_invocation_needs_approval_maps_to_invocation_needs_approval(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/bridge_target.md")
        invocation_result = {
            "invocation_id": "task_046_invocation",
            "task_id": "task_046_bridge_smoke",
            "worker_id": "repo_research_worker",
            "worker_type": "read_only_repo_research",
            "decision": "needs_approval",
            "preflight": {"decision": "needs_approval"},
            "worker_output": None,
            "return_path": {"target": "MainBrain", "mode": "candidate_contribution"},
            "candidate_status": "blocked",
            "side_effect_request": None,
            "verification_needed": True,
            "governance_needed": True,
            "limitations": ["Workflow network ≠ runtime network."],
            "generated_at": "2026-01-01T00:00:00Z",
        }
        invocation = Mock(return_value=invocation_result)
        with patch.object(bridge_module, "invoke_worker_with_envelope", invocation):
            bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(request, repo_root)
        self.assertEqual(bridge_result["decision"], "invocation_needs_approval")
        self.assertEqual(bridge_result["invocation_result"], invocation_result)
        self.assertNotIn("worker_output", bridge_result)

    def test_invocation_invalid_envelope_maps_to_invocation_invalid_envelope(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/bridge_target.md")
        invocation_result = {
            "invocation_id": "task_046_invocation",
            "task_id": "task_046_bridge_smoke",
            "worker_id": "repo_research_worker",
            "worker_type": "read_only_repo_research",
            "decision": "invalid_envelope",
            "preflight": {"decision": "invalid_envelope"},
            "worker_output": None,
            "return_path": {"target": "MainBrain", "mode": "candidate_contribution"},
            "candidate_status": "blocked",
            "side_effect_request": None,
            "verification_needed": False,
            "governance_needed": False,
            "limitations": ["Workflow network ≠ runtime network."],
            "generated_at": "2026-01-01T00:00:00Z",
        }
        invocation = Mock(return_value=invocation_result)
        with patch.object(bridge_module, "invoke_worker_with_envelope", invocation):
            bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(request, repo_root)
        self.assertEqual(bridge_result["decision"], "invocation_invalid_envelope")
        self.assertEqual(bridge_result["invocation_result"], invocation_result)
        self.assertNotIn("worker_output", bridge_result)


    def test_bridge_propagates_verified_evidence_release_eligibility_without_approval_language(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/bridge_target.md")
        invocation_result = {
            "invocation_id": "task_046_invocation",
            "task_id": "task_046_bridge_smoke",
            "worker_id": "repo_research_worker",
            "worker_type": "read_only_repo_research",
            "decision": "completed_candidate",
            "preflight": {"decision": "allow"},
            "worker_output": {"candidate_status": "candidate"},
            "return_path": {"target": "MainBrain", "mode": "candidate_contribution"},
            "candidate_status": "candidate",
            "side_effect_request": None,
            "verification_needed": False,
            "governance_needed": True,
            "evidence_status": "externally_verified",
            "release_eligibility": "eligible_for_mainbrain_review",
            "release_gate": {"eligible_for_release": True, "release_eligibility": "eligible_for_mainbrain_review", "reason": "externally_verified"},
            "claimed_evidence_count": 1,
            "verified_evidence_count": 1,
            "verified_by": "MainBrain",
            "limitations": [],
            "generated_at": "2026-01-01T00:00:00Z",
        }
        with patch.object(bridge_module, "invoke_worker_with_envelope", Mock(return_value=invocation_result)):
            bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(request, repo_root)

        self.assertEqual(bridge_result["decision"], "completed_candidate")
        self.assertEqual(bridge_result["evidence_status"], "externally_verified")
        self.assertEqual(bridge_result["release_eligibility"], "eligible_for_mainbrain_review")
        self.assertTrue(bridge_result["release_gate"]["eligible_for_release"])
        self.assertEqual(bridge_result["verified_by"], "MainBrain")
        decision_blob = " ".join([bridge_result["decision"], bridge_result["candidate_status"]]).lower()
        self.assertNotIn("approved", decision_blob)
        self.assertNotIn("verified", decision_blob)

    def test_bridge_output_does_not_claim_verification_governance_or_gate_approval(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(self._base_request("docs/bridge_target.md"), repo_root)
        decision_blob = " ".join(
            [
                bridge_result["decision"],
                bridge_result["routing_decision"]["decision"],
                bridge_result["builder_result"]["decision"],
                bridge_result["invocation_result"]["decision"],
                bridge_result["candidate_status"],
            ]
        ).lower()
        self.assertNotIn("verified", decision_blob)
        self.assertNotIn("approved", decision_blob)

    def test_bridge_does_not_include_authority_wording_in_decision_fields(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        bridge_result = bridge_module.run_mainbrain_worker_execution_bridge(self._base_request("docs/bridge_target.md"), repo_root)
        decision_blob = " ".join(
            str(bridge_result.get(key, ""))
            for key in ("decision", "routing_decision", "candidate_status")
        ).lower()
        self.assertNotIn("verified", decision_blob)
        self.assertNotIn("approved", decision_blob)
        self.assertIn("completed_candidate", decision_blob)

    def test_bridge_does_not_mutate_input_request(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/bridge_target.md")
        request_before = deepcopy(request)
        _ = bridge_module.run_mainbrain_worker_execution_bridge(request, repo_root)
        self.assertEqual(request, request_before)


if __name__ == "__main__":
    unittest.main()
