from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from runtime.workers import worker_bridge_enable_policy as policy_module
from runtime.workers import worker_bridge_observability as observability_module
from runtime.workers.mainbrain_worker_routing import route_mainbrain_worker_request
from runtime.workers.routing_decision_to_envelope import build_worker_invocation_envelope_from_routing_decision


class RepoResearchWorkerOperationalReadinessTest(unittest.TestCase):
    def _make_temp_repo(self) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        repo_root = Path(temp_dir.name)
        scoped_file = repo_root / "docs" / "ready_read_only_scope.md"
        scoped_file.parent.mkdir(parents=True, exist_ok=True)
        scoped_file.write_text(
            "Repo Research Worker may run only inside enabled_read_only.\n"
            "Repo Research Worker returns candidate-only evidence.\n",
            encoding="utf-8",
        )
        return temp_dir, repo_root, scoped_file

    def _base_request(self, candidate_path: str) -> dict[str, object]:
        return {
            "task_id": "task_049_readiness",
            "user_request": "Find the Repo Research Worker readiness marker.",
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

    def _enabled_read_only_result(self, repo_root: Path, candidate_path: str) -> dict[str, object]:
        request = self._base_request(candidate_path)
        return policy_module.run_worker_bridge_with_policy(request, repo_root, mode="enabled_read_only")

    def _ready_state(self, *checks: bool) -> str:
        return "ready_read_only" if all(checks) else "not_ready"

    def test_disabled_mode_does_not_execute_worker(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/ready_read_only_scope.md")
        result = policy_module.run_worker_bridge_with_policy(request, repo_root, mode="disabled")
        self.assertEqual(result["decision"], "disabled")
        self.assertNotIn("worker_output", result)
        self.assertIsNone(result["bridge_result"])

    def test_dry_run_mode_returns_preview_and_no_worker_output(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/ready_read_only_scope.md")
        result = policy_module.run_worker_bridge_with_policy(request, repo_root, mode="dry_run")
        self.assertEqual(result["decision"], "dry_run_ready")
        self.assertIn("routing_decision", result)
        self.assertIn("builder_result", result)
        self.assertIsNone(result["bridge_result"])
        self.assertNotIn("worker_output", result)
        self.assertEqual(result["candidate_status"], "preview_only")

    def test_enabled_read_only_mode_returns_completed_candidate_for_scoped_repo_file(self) -> None:
        temp_dir, repo_root, scoped_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = self._enabled_read_only_result(repo_root, "docs/ready_read_only_scope.md")
        self.assertEqual(result["decision"], "completed_candidate")
        self.assertEqual(result["worker_output"]["candidate_status"], "candidate")
        self.assertEqual(result["worker_output"]["output_type"], "candidate_repo_findings")
        self.assertEqual(result["worker_output"]["evidence_handles"][0]["path"], scoped_file.as_posix())

    def test_enabled_read_only_returns_candidate_only_worker_output(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = self._enabled_read_only_result(repo_root, "docs/ready_read_only_scope.md")
        worker_output = result["worker_output"]
        self.assertEqual(worker_output["candidate_status"], "candidate")
        self.assertEqual(worker_output["side_effect_request"], None)
        self.assertNotIn("verified", worker_output["content"]["summary"].lower())
        self.assertNotIn("approved", worker_output["content"]["summary"].lower())
        self.assertNotIn("complete", worker_output["content"]["summary"].lower())

    def test_observability_audit_record_from_completed_result_has_worker_candidate_returned_stage(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = self._enabled_read_only_result(repo_root, "docs/ready_read_only_scope.md")
        audit_record = observability_module.build_worker_bridge_audit_record(result)
        self.assertEqual(audit_record["path_stage"], "worker_candidate_returned")
        self.assertEqual(audit_record["decision"], "completed_candidate")
        self.assertTrue(audit_record["worker_execution_attempted"])
        self.assertTrue(audit_record["worker_output_present"])

    def test_audit_record_authority_claims_are_all_false(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = self._enabled_read_only_result(repo_root, "docs/ready_read_only_scope.md")
        audit_record = observability_module.build_worker_bridge_audit_record(result)
        self.assertEqual(audit_record["authority_claims"], {
            "claims_truth": False,
            "claims_completion": False,
            "claims_approval": False,
            "claims_governance": False,
            "claims_side_effect_permission": False,
        })

    def test_money_touching_request_is_blocked_before_worker_output(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/ready_read_only_scope.md")
        request["money_touching_intent"] = True
        result = policy_module.run_worker_bridge_with_policy(request, repo_root, mode="enabled_read_only")
        self.assertEqual(result["decision"], "blocked")
        self.assertNotIn("worker_output", result)
        self.assertEqual(result["bridge_result"]["decision"], "blocked")

    def test_network_intent_request_does_not_produce_worker_output(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/ready_read_only_scope.md")
        request["network_intent"] = True
        result = policy_module.run_worker_bridge_with_policy(request, repo_root, mode="enabled_read_only")
        self.assertIn(result["decision"], {"needs_approval", "blocked"})
        self.assertNotIn("worker_output", result)
        self.assertIn(result["bridge_result"]["decision"], {"needs_approval", "blocked"})

    def test_invalid_mode_does_not_produce_worker_output(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/ready_read_only_scope.md")
        result = policy_module.run_worker_bridge_with_policy(request, repo_root, mode="unsupported")
        self.assertEqual(result["decision"], "invalid_mode")
        self.assertNotIn("worker_output", result)
        self.assertIsNone(result["bridge_result"])

    def test_mapping_shaped_input_scope_preserved_through_builder_envelope_path(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/ready_read_only_scope.md")
        routing_decision = route_mainbrain_worker_request(request)
        self.assertEqual(routing_decision["decision"], "route_repo_research_worker")
        builder_result = build_worker_invocation_envelope_from_routing_decision(
            routing_decision,
            requested_by="MainBrain",
            invocation_id="task_049_invocation",
            created_at="task_049_timestamp",
        )
        self.assertEqual(builder_result["decision"], "built_envelope")
        envelope = builder_result["envelope"]
        self.assertIsInstance(envelope["input_scope"], dict)
        self.assertEqual(envelope["input_scope"]["paths_allowed"], ["docs/ready_read_only_scope.md"])
        self.assertEqual(envelope["input_scope"]["paths_excluded"], [])
        self.assertEqual(envelope["security_profile"], "repo_read_only_no_network")
        self.assertEqual(envelope["execution_surface"], "direct_tool")
        self.assertFalse(envelope["network_access"])
        self.assertFalse(envelope["shell_access"])
        self.assertFalse(envelope["money_touching"])
        self.assertFalse(envelope["external_mutation"])

    def test_side_effect_request_remains_none(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = self._enabled_read_only_result(repo_root, "docs/ready_read_only_scope.md")
        self.assertIsNone(result["side_effect_request"])
        audit_record = observability_module.build_worker_bridge_audit_record(result)
        self.assertIsNone(audit_record["side_effect_request"])

    def test_scoped_file_remains_unchanged(self) -> None:
        temp_dir, repo_root, scoped_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        original = scoped_file.read_text(encoding="utf-8")
        _ = self._enabled_read_only_result(repo_root, "docs/ready_read_only_scope.md")
        self.assertEqual(scoped_file.read_text(encoding="utf-8"), original)

    def test_no_decision_field_contains_verified_approved_complete_authority_wording(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        result = self._enabled_read_only_result(repo_root, "docs/ready_read_only_scope.md")
        audit_record = observability_module.build_worker_bridge_audit_record(result)
        decision_fields = [
            result["decision"],
            result["mode"],
            result["bridge_result"]["decision"],
            result["routing_decision"]["decision"],
            result["builder_result"]["decision"],
            result["invocation_result"]["decision"],
            result["worker_output"]["candidate_status"],
            audit_record["decision"],
            audit_record["path_stage"],
            audit_record["candidate_status"],
        ]
        self.assertFalse(any(field in {"verified", "approved", "complete"} for field in decision_fields))

    def test_synthetic_readiness_state_is_ready_read_only_only_when_all_checks_pass(self) -> None:
        temp_dir, repo_root, _ = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._base_request("docs/ready_read_only_scope.md")
        policy_result = policy_module.run_worker_bridge_with_policy(request, repo_root, mode="enabled_read_only")
        audit_record = observability_module.build_worker_bridge_audit_record(policy_result)
        readiness_state = self._ready_state(
            policy_result["decision"] == "completed_candidate",
            policy_result["worker_output"]["candidate_status"] == "candidate",
            policy_result["side_effect_request"] is None,
            policy_result["worker_output"]["side_effect_request"] is None,
            audit_record["path_stage"] == "worker_candidate_returned",
            all(value is False for value in audit_record["authority_claims"].values()),
            policy_result["worker_output"]["output_type"] == "candidate_repo_findings",
            policy_result["worker_output"]["evidence_handles"],
            policy_result["worker_output"]["content"]["findings"],
            policy_result["worker_output"]["content"]["summary"],
        )
        self.assertEqual(readiness_state, "ready_read_only")


if __name__ == "__main__":
    unittest.main()
