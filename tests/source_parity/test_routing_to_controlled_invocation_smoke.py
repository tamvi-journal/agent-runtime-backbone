from __future__ import annotations

from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from runtime.workers import controlled_invocation
from runtime.workers.mainbrain_worker_routing import route_mainbrain_worker_request


class RoutingToControlledInvocationSmokeTest(unittest.TestCase):
    def _make_temp_repo(self) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        repo_root = Path(temp_dir.name)
        smoke_file = repo_root / "docs" / "smoke_target.md"
        smoke_file.parent.mkdir(parents=True, exist_ok=True)
        smoke_file.write_text(
            "ROUTING_TO_INVOCATION_MARKER: candidate evidence from scoped local file.\n",
            encoding="utf-8",
        )
        return temp_dir, repo_root, smoke_file

    def _routing_request(self, candidate_path: str) -> dict[str, object]:
        return {
            "task_id": "task_042_smoke",
            "user_request": "Find the routing smoke marker.",
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

    def _build_test_envelope_from_routing_decision(self, routing_decision: dict[str, object], repo_root: Path) -> dict[str, object]:
        self.assertEqual(routing_decision["decision"], "route_repo_research_worker")
        self.assertEqual(routing_decision["selected_worker"], {"worker_id": "repo_research_worker", "worker_type": "read_only_repo_research"})
        scope = routing_decision["proposed_input_scope"]
        self.assertIsInstance(scope, dict)
        return {
            "invocation_id": "inv-042-smoke",
            "task_id": routing_decision["task_id"],
            "requested_by": "MainBrain",
            "worker_id": routing_decision["selected_worker"]["worker_id"],
            "worker_type": routing_decision["selected_worker"]["worker_type"],
            "invocation_purpose": routing_decision["invocation_purpose"],
            "input_scope": {
                "paths_allowed": scope["paths_allowed"],
                "paths_excluded": scope["paths_excluded"],
                "research_question": routing_decision["invocation_purpose"],
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
            "output_contract": "WorkerOutputPacket / candidate contribution",
            "return_path": "MainBrain/Agent routing",
            "escalation_policy": {"gate": "none"},
            "abort_conditions": [],
            "created_at": "2026-05-08T00:00:00Z",
        }

    def _route_then_maybe_invoke(self, request: dict[str, object], repo_root: Path):
        routing_decision = route_mainbrain_worker_request(request)
        if routing_decision["decision"] != "route_repo_research_worker":
            return routing_decision, None
        envelope = self._build_test_envelope_from_routing_decision(routing_decision, repo_root)
        return routing_decision, controlled_invocation.invoke_worker_with_envelope(envelope, repo_root)

    def test_positive_route_to_controlled_invocation_smoke(self) -> None:
        temp_dir, repo_root, smoke_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._routing_request("docs/smoke_target.md")

        opened_paths: list[Path] = []
        original_open = os.open

        def recording_open(path, *args, **kwargs):
            opened_paths.append(Path(path))
            return original_open(path, *args, **kwargs)

        with patch("os.open", new=recording_open), patch("pathlib.Path.write_text", side_effect=AssertionError("smoke invocation must not write files")), patch("pathlib.Path.touch", side_effect=AssertionError("smoke invocation must not touch files")), patch("pathlib.Path.mkdir", side_effect=AssertionError("smoke invocation must not create directories")):
            routing_decision, invocation_result = self._route_then_maybe_invoke(request, repo_root)

        self.assertEqual(routing_decision["decision"], "route_repo_research_worker")
        self.assertEqual(routing_decision["selected_worker"], {"worker_id": "repo_research_worker", "worker_type": "read_only_repo_research"})
        self.assertEqual(routing_decision["proposed_input_scope"]["paths_allowed"], ["docs/smoke_target.md"])
        self.assertNotIn("worker_output", routing_decision)
        self.assertNotIn("verified", routing_decision["decision"].lower())
        self.assertNotIn("approved", routing_decision["reasons"][0].lower() if routing_decision["reasons"] else "")
        self.assertEqual(invocation_result["decision"], "completed_candidate")
        self.assertEqual(invocation_result["preflight"]["decision"], "allow")
        self.assertIsNotNone(invocation_result["worker_output"])
        self.assertEqual(invocation_result["worker_output"]["candidate_status"], "candidate")
        self.assertEqual(invocation_result["worker_output"]["worker_id"], "repo_research_worker")
        self.assertTrue(invocation_result["worker_output"]["evidence_handles"])
        self.assertIsNone(invocation_result["side_effect_request"])
        self.assertIsNone(invocation_result["worker_output"]["side_effect_request"])
        self.assertEqual(invocation_result["return_path"], "MainBrain/Agent routing")
        finding = invocation_result["worker_output"]["content"]["findings"][0]
        self.assertEqual(invocation_result["worker_output"]["content"]["findings"][0]["path"], smoke_file.relative_to(repo_root).as_posix())
        self.assertIn(finding["status"], {"matched", "sampled"})
        if finding["status"] == "matched":
            self.assertIn("ROUTING_TO_INVOCATION_MARKER", finding["snippets"][0]["snippet"])
        else:
            self.assertEqual(finding["snippets"], [])
        self.assertNotIn("verified", invocation_result["worker_output"]["content"]["summary"].lower())
        self.assertNotIn("approved", invocation_result["worker_output"]["content"]["summary"].lower())
        self.assertTrue(opened_paths)
        self.assertTrue(all(path == smoke_file for path in opened_paths))
        self.assertEqual(smoke_file.read_text(encoding="utf-8"), "ROUTING_TO_INVOCATION_MARKER: candidate evidence from scoped local file.\n")

    def test_money_touching_intent_blocks_without_invocation(self) -> None:
        temp_dir, repo_root, smoke_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._routing_request("docs/smoke_target.md")
        request["money_touching_intent"] = True
        invocation = Mock(side_effect=AssertionError("controlled invocation must not run"))

        with patch("runtime.workers.controlled_invocation.invoke_worker_with_envelope", invocation):
            routing_decision, invocation_result = self._route_then_maybe_invoke(request, repo_root)

        self.assertEqual(routing_decision["decision"], "blocked")
        self.assertIsNone(invocation_result)
        invocation.assert_not_called()
        self.assertEqual(smoke_file.read_text(encoding="utf-8"), "ROUTING_TO_INVOCATION_MARKER: candidate evidence from scoped local file.\n")

    def test_network_intent_needs_approval_without_invocation(self) -> None:
        temp_dir, repo_root, smoke_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._routing_request("docs/smoke_target.md")
        request["network_intent"] = True
        invocation = Mock(side_effect=AssertionError("controlled invocation must not run"))

        with patch("runtime.workers.controlled_invocation.invoke_worker_with_envelope", invocation):
            routing_decision, invocation_result = self._route_then_maybe_invoke(request, repo_root)

        self.assertIn(routing_decision["decision"], {"needs_approval", "blocked"})
        self.assertIsNone(invocation_result)
        invocation.assert_not_called()
        self.assertEqual(smoke_file.read_text(encoding="utf-8"), "ROUTING_TO_INVOCATION_MARKER: candidate evidence from scoped local file.\n")

    def test_empty_candidate_paths_invalid_request_without_invocation(self) -> None:
        temp_dir, repo_root, smoke_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._routing_request("docs/smoke_target.md")
        request["candidate_paths"] = []
        invocation = Mock(side_effect=AssertionError("controlled invocation must not run"))

        with patch("runtime.workers.controlled_invocation.invoke_worker_with_envelope", invocation):
            routing_decision, invocation_result = self._route_then_maybe_invoke(request, repo_root)

        self.assertEqual(routing_decision["decision"], "invalid_request")
        self.assertIsNone(invocation_result)
        invocation.assert_not_called()
        self.assertEqual(smoke_file.read_text(encoding="utf-8"), "ROUTING_TO_INVOCATION_MARKER: candidate evidence from scoped local file.\n")

    def test_worker_self_invocation_or_open_worker_request_blocks_without_invocation(self) -> None:
        temp_dir, repo_root, smoke_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._routing_request("docs/smoke_target.md")
        request["user_request"] = "Use an open worker registry and worker self invocation."
        invocation = Mock(side_effect=AssertionError("controlled invocation must not run"))

        with patch("runtime.workers.controlled_invocation.invoke_worker_with_envelope", invocation):
            routing_decision, invocation_result = self._route_then_maybe_invoke(request, repo_root)

        self.assertEqual(routing_decision["decision"], "blocked")
        self.assertIsNone(invocation_result)
        invocation.assert_not_called()
        self.assertEqual(smoke_file.read_text(encoding="utf-8"), "ROUTING_TO_INVOCATION_MARKER: candidate evidence from scoped local file.\n")


if __name__ == "__main__":
    unittest.main()
