from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from runtime.workers import worker_bridge_enable_policy as policy_module


class WorkerBridgeEnablePolicyTest(unittest.TestCase):
    def _make_temp_repo(self) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        repo_root = Path(temp_dir.name)
        target_file = repo_root / "docs" / "policy_bridge_target.md"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(
            "POLICY_BRIDGE_SMOKE_MARKER: evidence from policy to bridge to worker.\n",
            encoding="utf-8",
        )
        return temp_dir, repo_root, target_file

    def _base_request(self, candidate_path: str) -> dict[str, object]:
        return {
            "task_id": "task_047_policy_bridge_smoke",
            "user_request": "Find the policy bridge smoke marker.",
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

    def test_default_mode_is_disabled(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        with patch.object(policy_module, "run_mainbrain_worker_execution_bridge", side_effect=AssertionError("bridge must not run")):
            result = policy_module.run_worker_bridge_with_policy(self._base_request("docs/policy_bridge_target.md"), repo_root)
        self.assertEqual(result["mode"], "disabled")
        self.assertEqual(result["decision"], "disabled")

    def test_disabled_mode_does_not_call_execution_bridge(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        bridge = Mock(side_effect=AssertionError("bridge must not run"))
        with patch.object(policy_module, "run_mainbrain_worker_execution_bridge", bridge):
            result = policy_module.run_worker_bridge_with_policy(
                self._base_request("docs/policy_bridge_target.md"),
                repo_root,
                mode="disabled",
            )
        self.assertEqual(result["decision"], "disabled")
        bridge.assert_not_called()
        self.assertNotIn("worker_output", result)

    def test_invalid_mode_returns_invalid_mode(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        bridge = Mock(side_effect=AssertionError("bridge must not run"))
        with patch.object(policy_module, "run_mainbrain_worker_execution_bridge", bridge):
            result = policy_module.run_worker_bridge_with_policy(
                self._base_request("docs/policy_bridge_target.md"),
                repo_root,
                mode="unsupported",
            )
        self.assertEqual(result["decision"], "invalid_mode")
        self.assertIsNone(result["side_effect_request"])
        bridge.assert_not_called()
        self.assertNotIn("worker_output", result)

    def test_dry_run_valid_request_returns_dry_run_ready(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = policy_module.run_worker_bridge_with_policy(
            self._base_request("docs/policy_bridge_target.md"),
            repo_root,
            mode="dry_run",
        )
        self.assertEqual(result["decision"], "dry_run_ready")
        self.assertEqual(result["mode"], "dry_run")
        self.assertIn("routing_decision", result)
        self.assertIn("builder_result", result)
        self.assertIsNone(result["bridge_result"])
        self.assertNotIn("worker_output", result)
        self.assertIsNone(result["side_effect_request"])

    def test_dry_run_does_not_invoke_controlled_invocation_or_worker_output(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = policy_module.run_worker_bridge_with_policy(
            self._base_request("docs/policy_bridge_target.md"),
            repo_root,
            mode="dry_run",
        )
        self.assertEqual(result["decision"], "dry_run_ready")
        self.assertNotIn("worker_output", result)
        self.assertIsNone(result.get("invocation_result"))
        self.assertIsNone(result["bridge_result"])

    def test_dry_run_includes_routing_decision(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = policy_module.run_worker_bridge_with_policy(
            self._base_request("docs/policy_bridge_target.md"),
            repo_root,
            mode="dry_run",
        )
        self.assertEqual(result["routing_decision"]["decision"], "route_repo_research_worker")

    def test_dry_run_includes_builder_result_for_routeable_request(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = policy_module.run_worker_bridge_with_policy(
            self._base_request("docs/policy_bridge_target.md"),
            repo_root,
            mode="dry_run",
        )
        self.assertEqual(result["builder_result"]["decision"], "built_envelope")

    def test_dry_run_money_touching_stops_before_builder_or_invocation(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/policy_bridge_target.md")
        request["money_touching_intent"] = True
        result = policy_module.run_worker_bridge_with_policy(request, repo_root, mode="dry_run")
        self.assertEqual(result["decision"], "dry_run_blocked")
        self.assertEqual(result["routing_decision"]["decision"], "blocked")
        self.assertIsNone(result.get("builder_result"))
        self.assertNotIn("worker_output", result)

    def test_dry_run_network_intent_stops_before_invocation(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/policy_bridge_target.md")
        request["network_intent"] = True
        result = policy_module.run_worker_bridge_with_policy(request, repo_root, mode="dry_run")
        self.assertIn(result["decision"], {"dry_run_needs_approval", "dry_run_blocked"})
        self.assertNotIn("worker_output", result)
        self.assertIsNone(result.get("invocation_result"))

    def test_enabled_read_only_valid_request_calls_bridge_and_returns_completed_candidate(self) -> None:
        temp_dir, repo_root, target_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/policy_bridge_target.md")
        request_before = deepcopy(request)
        result = policy_module.run_worker_bridge_with_policy(request, repo_root, mode="enabled_read_only")
        self.assertEqual(result["decision"], "completed_candidate")
        self.assertEqual(result["bridge_result"]["decision"], "completed_candidate")
        self.assertEqual(result["worker_output"]["candidate_status"], "candidate")
        self.assertEqual(target_file.read_text(encoding="utf-8"), "POLICY_BRIDGE_SMOKE_MARKER: evidence from policy to bridge to worker.\n")
        self.assertEqual(request, request_before)

    def test_enabled_read_only_returns_candidate_only_worker_output(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = policy_module.run_worker_bridge_with_policy(
            self._base_request("docs/policy_bridge_target.md"),
            repo_root,
            mode="enabled_read_only",
        )
        self.assertEqual(result["worker_output"]["candidate_status"], "candidate")
        self.assertEqual(result["decision"], "completed_candidate")
        self.assertEqual(result["bridge_result"]["decision"], "completed_candidate")
        self.assertEqual(result["candidate_status"], "candidate")

    def test_enabled_read_only_preserves_scoped_file_unchanged(self) -> None:
        temp_dir, repo_root, target_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        original = target_file.read_text(encoding="utf-8")
        _ = policy_module.run_worker_bridge_with_policy(
            self._base_request("docs/policy_bridge_target.md"),
            repo_root,
            mode="enabled_read_only",
        )
        self.assertEqual(target_file.read_text(encoding="utf-8"), original)

    def test_enabled_read_only_money_touching_stops_with_no_worker_output(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/policy_bridge_target.md")
        request["money_touching_intent"] = True
        result = policy_module.run_worker_bridge_with_policy(request, repo_root, mode="enabled_read_only")
        self.assertEqual(result["decision"], "blocked")
        self.assertNotIn("worker_output", result)
        self.assertEqual(result["bridge_result"]["decision"], "blocked")

    def test_enabled_read_only_invalid_request_returns_invalid_request_with_no_worker_output(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/policy_bridge_target.md")
        request["candidate_paths"] = []
        result = policy_module.run_worker_bridge_with_policy(request, repo_root, mode="enabled_read_only")
        self.assertEqual(result["decision"], "invalid_request")
        self.assertNotIn("worker_output", result)
        self.assertEqual(result["bridge_result"]["decision"], "invalid_request")

    def test_policy_output_does_not_claim_verification_governance_or_gate_approval(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = policy_module.run_worker_bridge_with_policy(
            self._base_request("docs/policy_bridge_target.md"),
            repo_root,
            mode="enabled_read_only",
        )
        decision_fields = " ".join(
            [
                str(result["decision"]),
                str(result["mode"]),
                str(result["candidate_status"]),
                str(result["bridge_result"]["decision"]),
                str(result["bridge_result"]["routing_decision"]["decision"]),
                str(result["bridge_result"]["builder_result"]["decision"]),
                str(result["bridge_result"]["invocation_result"]["decision"]),
            ]
        ).lower()
        self.assertNotIn("verified", decision_fields)
        self.assertNotIn("approved", decision_fields)
        self.assertNotIn("gate approval", decision_fields)

    def test_policy_output_does_not_include_approved_verified_complete_decision_wording(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = policy_module.run_worker_bridge_with_policy(
            self._base_request("docs/policy_bridge_target.md"),
            repo_root,
            mode="dry_run",
        )
        decision_blob = " ".join(str(result.get(key, "")) for key in ("decision", "mode", "candidate_status", "bridge_result")).lower()
        self.assertNotIn("approved", decision_blob)
        self.assertNotIn("verified", decision_blob)
        self.assertNotIn("complete", decision_blob)

    def test_side_effect_request_is_always_none(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        for mode in ("disabled", "dry_run", "enabled_read_only", "invalid"):
            result = policy_module.run_worker_bridge_with_policy(
                self._base_request("docs/policy_bridge_target.md"),
                repo_root,
                mode=mode,
            )
            self.assertIsNone(result["side_effect_request"])

    def test_helper_does_not_mutate_input_request(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/policy_bridge_target.md")
        request_before = deepcopy(request)
        _ = policy_module.run_worker_bridge_with_policy(request, repo_root, mode="dry_run")
        self.assertEqual(request, request_before)


if __name__ == "__main__":
    unittest.main()
