from __future__ import annotations

import copy
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from runtime.workers.controlled_invocation import invoke_worker_with_envelope


class ControlledWorkerInvocationTest(unittest.TestCase):
    def base_envelope(self, *, worker_id: str = "repo_research_worker", worker_type: str = "read_only_repo_research") -> dict[str, object]:
        return {
            "invocation_id": "inv-038",
            "task_id": "task-038",
            "requested_by": "MainBrain",
            "worker_id": worker_id,
            "worker_type": worker_type,
            "invocation_purpose": "controlled worker invocation path v0.1",
            "input_scope": {
                "paths_allowed": ["runtime/workers/repo_research_worker.py"],
                "paths_excluded": [],
                "research_question": "controlled worker invocation path v0.1",
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
            "side_effect_class": "repo_read",
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

    def valid_worker_output(self) -> dict[str, object]:
        return {
            "worker_id": "repo_research_worker",
            "worker_type": "read_only_repo_research",
            "task_id": "task-038",
            "input_scope": {
                "paths_allowed": ["runtime/workers/repo_research_worker.py"],
                "paths_excluded": [],
                "research_question": "Repo Research Worker",
                "max_files": 5,
                "max_bytes_per_file": 20_000,
            },
            "output_type": "candidate_repo_findings",
            "content": {"summary": "Read scoped repo files and gathered candidate evidence.", "findings": [{"path": "runtime/workers/repo_research_worker.py", "status": "matched"}]},
            "evidence_handles": [{"path": "runtime/workers/repo_research_worker.py", "locator": "content match", "claim_supported": "candidate evidence", "evidence_type": "file_content", "confidence": "high"}],
            "assumptions": ["Scoped repo read only."],
            "confidence": "high",
            "limitations": [],
            "blocked_items": [],
            "side_effect_request": None,
            "verification_needed": True,
            "memory_context_used": False,
            "candidate_status": "candidate",
            "generated_at": "2026-05-08T00:00:00Z",
            "execution_surface": {"mode": "direct_tool", "tools_used": ["filesystem_read"], "agent_id": "repo_research_worker", "model_visible": False, "provider_visible": False, "max_iterations": 0, "context_boundary": "paths_allowed within repo_root"},
            "security_profile": {"name": "repo_read_only_no_network", "network": False, "browser": False, "shell": False, "downloads": False, "package_install": False},
            "preflight": {"decision": "allow", "reasons": []},
        }

    def make_repo(self) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        file_path = root / "notes.txt"
        file_path.write_text("Repo Research Worker may run only after Preflight Guard returns allow.\n", encoding="utf-8")
        return td, root, file_path

    def test_valid_repo_research_envelope_invokes_repo_worker_and_returns_completed_candidate(self):
        td, root, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope()
        envelope["input_scope"] = {"paths_allowed": [str(file_path)], "paths_excluded": [], "research_question": "Repo Research Worker", "max_files": 5, "max_bytes_per_file": 20_000}

        result = invoke_worker_with_envelope(envelope, root)

        self.assertEqual(result["decision"], "completed_candidate")
        self.assertIsNotNone(result["worker_output"])
        self.assertEqual(result["worker_output"]["candidate_status"], "candidate")
        self.assertEqual(result["candidate_status"], "candidate")
        self.assertEqual(result["side_effect_request"], None)

    def test_invocation_calls_preflight_before_worker(self):
        envelope = self.base_envelope()
        call_order: list[str] = []

        def fake_preflight(value):
            call_order.append("preflight")
            return {"decision": "allow", "reasons": [], "limitations": []}

        def fake_worker(*args, **kwargs):
            call_order.append("worker")
            return self.valid_worker_output()

        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", side_effect=fake_preflight), patch("runtime.workers.controlled_invocation.run_repo_research_worker", side_effect=fake_worker):
            invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(call_order, ["preflight", "worker"])

    def test_preflight_invalid_envelope_returns_invalid_envelope_and_does_not_run_worker(self):
        envelope = self.base_envelope()
        worker = Mock(side_effect=AssertionError("worker must not run"))

        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "invalid_envelope", "reasons": ["bad"], "limitations": ["bad"]}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", worker):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(result["decision"], "invalid_envelope")
        self.assertIsNone(result["worker_output"])
        worker.assert_not_called()

    def test_preflight_block_returns_blocked_and_does_not_run_worker(self):
        envelope = self.base_envelope()
        worker = Mock(side_effect=AssertionError("worker must not run"))

        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "block", "reasons": ["blocked"], "limitations": ["blocked"]}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", worker):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(result["decision"], "blocked")
        self.assertIsNone(result["worker_output"])
        worker.assert_not_called()

    def test_preflight_needs_approval_returns_needs_approval_and_does_not_run_worker(self):
        envelope = self.base_envelope()
        worker = Mock(side_effect=AssertionError("worker must not run"))

        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "needs_approval", "reasons": ["review"], "limitations": ["review"]}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", worker):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(result["decision"], "needs_approval")
        self.assertIsNone(result["worker_output"])
        worker.assert_not_called()

    def test_unknown_worker_id_blocks(self):
        envelope = self.base_envelope(worker_id="unknown_worker")
        worker = Mock(side_effect=AssertionError("worker must not run"))

        with patch("runtime.workers.controlled_invocation.run_repo_research_worker", worker):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(result["decision"], "blocked")
        worker.assert_not_called()

    def test_unknown_worker_type_blocks(self):
        envelope = self.base_envelope(worker_type="unknown_type")
        worker = Mock(side_effect=AssertionError("worker must not run"))

        with patch("runtime.workers.controlled_invocation.run_repo_research_worker", worker):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(result["decision"], "blocked")
        worker.assert_not_called()

    def test_mismatched_worker_id_and_worker_type_blocks(self):
        envelope = self.base_envelope(worker_id="repo_research_worker", worker_type="unknown_type")
        worker = Mock(side_effect=AssertionError("worker must not run"))

        with patch("runtime.workers.controlled_invocation.run_repo_research_worker", worker):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(result["decision"], "blocked")
        worker.assert_not_called()

    def test_worker_output_is_present_only_when_worker_ran(self):
        envelope = self.base_envelope()
        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "allow", "reasons": [], "limitations": []}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", return_value=self.valid_worker_output()):
            allowed = invoke_worker_with_envelope(envelope, "/tmp/repo")

        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "block", "reasons": ["blocked"], "limitations": ["blocked"]}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", side_effect=AssertionError("worker must not run")):
            blocked = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertIsNotNone(allowed["worker_output"])
        self.assertIsNone(blocked["worker_output"])

    def test_worker_output_remains_candidate_only(self):
        envelope = self.base_envelope()
        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "allow", "reasons": [], "limitations": []}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", return_value=self.valid_worker_output()):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(result["decision"], "completed_candidate")
        self.assertNotIn("complete", result["worker_output"]["content"]["summary"].lower())
        self.assertNotIn("verified", result["worker_output"]["content"]["summary"].lower())

    def test_side_effect_request_is_always_none(self):
        envelope = self.base_envelope()
        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "allow", "reasons": [], "limitations": []}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", return_value=self.valid_worker_output()):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertIsNone(result["side_effect_request"])
        self.assertIsNone(result["worker_output"]["side_effect_request"])

    def test_return_path_is_preserved(self):
        envelope = self.base_envelope()
        envelope["return_path"] = "MainBrain/Agent routing preserved"
        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "allow", "reasons": [], "limitations": []}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", return_value=self.valid_worker_output()):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(result["return_path"], "MainBrain/Agent routing preserved")

    def test_verification_needed_is_reported_but_not_satisfied(self):
        envelope = self.base_envelope()
        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "allow", "reasons": [], "limitations": []}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", return_value=self.valid_worker_output()):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertTrue(result["verification_needed"])
        self.assertTrue(result["worker_output"]["verification_needed"])
        self.assertEqual(result["decision"], "completed_candidate")


    def test_claimed_evidence_only_is_not_release_eligible(self):
        envelope = self.base_envelope()
        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "allow", "reasons": [], "limitations": []}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", return_value=self.valid_worker_output()):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(result["decision"], "completed_candidate")
        self.assertEqual(result["evidence_status"], "claimed_only")
        self.assertEqual(result["release_eligibility"], "not_eligible_pending_verification")
        self.assertFalse(result["release_gate"]["eligible_for_release"])
        self.assertEqual(result["claimed_evidence_count"], 1)
        self.assertEqual(result["verified_evidence_count"], 0)
        self.assertIn("worker-reported evidence is claimed", " ".join(result["limitations"]))
        self.assertEqual(result["worker_output"]["release_eligibility"], "not_eligible_pending_verification")

    def test_external_verified_evidence_makes_candidate_eligible_for_mainbrain_review(self):
        envelope = self.base_envelope()
        envelope["verified_evidence"] = {
            "verified_by": "MainBrain",
            "evidence_handles": [{"path": "runtime/workers/repo_research_worker.py", "locator": "external readback"}],
            "checks_run": ["external_file_readback"],
        }
        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "allow", "reasons": [], "limitations": []}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", return_value=self.valid_worker_output()):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(result["decision"], "completed_candidate")
        self.assertEqual(result["candidate_status"], "candidate")
        self.assertEqual(result["evidence_status"], "externally_verified")
        self.assertEqual(result["release_eligibility"], "eligible_for_mainbrain_review")
        self.assertTrue(result["release_gate"]["eligible_for_release"])
        self.assertFalse(result["verification_needed"])
        self.assertEqual(result["verified_by"], "MainBrain")
        self.assertEqual(result["verified_evidence_count"], 1)
        self.assertEqual(result["worker_output"]["evidence_status"], "externally_verified")

    def test_missing_verified_evidence_does_not_auto_release(self):
        envelope = self.base_envelope()
        worker_output = self.valid_worker_output()
        worker_output["evidence_handles"] = []
        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "allow", "reasons": [], "limitations": []}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", return_value=worker_output):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(result["evidence_status"], "missing_claimed_evidence")
        self.assertEqual(result["release_eligibility"], "not_eligible_pending_verification")
        self.assertTrue(result["verification_needed"])
        self.assertFalse(result["release_gate"]["eligible_for_release"])

    def test_governance_needed_is_reported_but_not_satisfied(self):
        envelope = self.base_envelope()
        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "allow", "reasons": [], "limitations": []}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", return_value=self.valid_worker_output()):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertTrue(result["governance_needed"])
        self.assertEqual(result["decision"], "completed_candidate")

    def test_no_completion_or_verified_language_in_invocation_decision(self):
        envelope = self.base_envelope()
        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "allow", "reasons": [], "limitations": []}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", return_value=self.valid_worker_output()):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertEqual(result["decision"], "completed_candidate")
        self.assertNotIn(result["decision"], {"complete", "verified"})

    def test_money_touching_envelope_does_not_run_worker(self):
        envelope = self.base_envelope()
        envelope["money_touching"] = True
        envelope["side_effect_class"] = "money_touching"
        worker = Mock(side_effect=AssertionError("worker must not run"))

        with patch("runtime.workers.controlled_invocation.run_repo_research_worker", worker):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertNotEqual(result["decision"], "completed_candidate")
        worker.assert_not_called()

    def test_network_access_envelope_does_not_run_worker_unless_preflight_allow_says_allow(self):
        envelope = self.base_envelope()
        envelope["network_access"] = True
        worker = Mock(side_effect=AssertionError("worker must not run"))

        with patch("runtime.workers.controlled_invocation.run_repo_research_worker", worker):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertNotEqual(result["decision"], "completed_candidate")
        worker.assert_not_called()

    def test_repo_mutation_side_effect_envelope_does_not_run_worker(self):
        envelope = self.base_envelope()
        envelope["side_effect_class"] = "repo_mutation"
        envelope["approval_required_actions"] = ["repo_mutation"]
        envelope["requested_actions"] = ["repo_mutation"]
        worker = Mock(side_effect=AssertionError("worker must not run"))

        with patch("runtime.workers.controlled_invocation.run_repo_research_worker", worker):
            result = invoke_worker_with_envelope(envelope, "/tmp/repo")

        self.assertNotEqual(result["decision"], "completed_candidate")
        worker.assert_not_called()

    def test_invocation_does_not_mutate_scoped_files(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        scoped = root / "scoped.txt"
        scoped.write_text("safe scoped content", encoding="utf-8")
        envelope = self.base_envelope()
        envelope["input_scope"] = [{"paths_allowed": [str(scoped)], "paths_excluded": [], "research_question": "Repo Research Worker", "max_files": 5, "max_bytes_per_file": 20_000}]
        before = scoped.read_text(encoding="utf-8")
        with patch("runtime.workers.controlled_invocation.validate_worker_invocation_envelope", return_value={"decision": "allow", "reasons": [], "limitations": []}), patch("runtime.workers.controlled_invocation.run_repo_research_worker", return_value=self.valid_worker_output()):
            _ = invoke_worker_with_envelope(copy.deepcopy(envelope), root)
        after = scoped.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_no_dynamic_unknown_worker_execution_path_exists(self):
        source = inspect.getsource(invoke_worker_with_envelope)
        self.assertNotIn("importlib", source)
        self.assertNotIn("getattr(", source)
        self.assertNotIn("eval(", source)
        self.assertNotIn("exec(", source)


if __name__ == "__main__":
    unittest.main()
