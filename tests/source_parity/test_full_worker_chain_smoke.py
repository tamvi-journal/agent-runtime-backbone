from __future__ import annotations

from pathlib import Path
import os
import json
import tempfile
import unittest
from unittest.mock import Mock

from runtime.workers import controlled_invocation
from runtime.workers.mainbrain_worker_routing import route_mainbrain_worker_request
from runtime.workers.routing_decision_to_envelope import build_worker_invocation_envelope_from_routing_decision


class FullWorkerChainSmokeTest(unittest.TestCase):
    def _make_temp_repo(self) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        repo_root = Path(temp_dir.name)
        smoke_file = repo_root / "docs" / "full_chain_target.md"
        smoke_file.parent.mkdir(parents=True, exist_ok=True)
        smoke_file.write_text(
            "FULL_CHAIN_SMOKE_MARKER: evidence from routing to builder to controlled invocation.\n",
            encoding="utf-8",
        )
        return temp_dir, repo_root, smoke_file

    def _routing_request(self, candidate_path: str) -> dict[str, object]:
        return {
            "task_id": "task_045_full_chain_smoke",
            "user_request": "Find the full chain smoke marker.",
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

    def _route_build_invoke(self, request: dict[str, object], repo_root: Path):
        routing_decision = route_mainbrain_worker_request(request)
        if routing_decision["decision"] != "route_repo_research_worker":
            return routing_decision, None, None

        envelope_result = build_worker_invocation_envelope_from_routing_decision(
            routing_decision,
            requested_by="MainBrain",
            invocation_id="task_045_invocation",
            created_at="task_045_static_timestamp",
        )
        if envelope_result["decision"] != "built_envelope":
            return routing_decision, envelope_result, None

        invocation_result = controlled_invocation.invoke_worker_with_envelope(
            envelope_result["envelope"],
            repo_root,
        )
        return routing_decision, envelope_result, invocation_result

    def test_full_chain_positive_smoke(self) -> None:
        temp_dir, repo_root, smoke_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._routing_request("docs/full_chain_target.md")

        opened_paths: list[Path] = []
        original_open = os.open

        def recording_open(path, *args, **kwargs):
            opened_paths.append(Path(path))
            return original_open(path, *args, **kwargs)

        with (
            unittest.mock.patch("os.open", new=recording_open),
            unittest.mock.patch("pathlib.Path.write_text", side_effect=AssertionError("smoke invocation must not write files")),
            unittest.mock.patch("pathlib.Path.touch", side_effect=AssertionError("smoke invocation must not touch files")),
            unittest.mock.patch("pathlib.Path.mkdir", side_effect=AssertionError("smoke invocation must not create directories")),
        ):
            routing_decision, envelope_result, invocation_result = self._route_build_invoke(request, repo_root)

        self.assertEqual(routing_decision["decision"], "route_repo_research_worker")
        self.assertEqual(routing_decision["selected_worker"], {"worker_id": "repo_research_worker", "worker_type": "read_only_repo_research"})
        self.assertEqual(routing_decision["proposed_input_scope"]["paths_allowed"], ["docs/full_chain_target.md"])
        self.assertNotIn("worker_output", routing_decision)
        routing_blob = " ".join(
            [str(routing_decision.get(key, "")) for key in ("decision", "next_step")]
            + [str(item) for item in routing_decision.get("reasons", [])]
            + [str(item) for item in routing_decision.get("limitations", [])]
        ).lower()
        self.assertNotIn("verified", routing_blob)
        self.assertNotIn("approved", routing_blob)
        self.assertNotIn("complete", routing_blob)

        self.assertEqual(envelope_result["decision"], "built_envelope")
        self.assertIsNotNone(envelope_result["envelope"])
        envelope = envelope_result["envelope"]
        self.assertEqual(envelope["worker_id"], "repo_research_worker")
        self.assertEqual(envelope["worker_type"], "read_only_repo_research")
        self.assertEqual(envelope["permission_class"], "read_only")
        self.assertEqual(envelope["security_profile"], "repo_read_only_no_network")
        self.assertEqual(envelope["execution_surface"], "direct_tool")
        self.assertEqual(envelope["side_effect_class"], "repo_read")
        self.assertFalse(envelope["money_touching"])
        self.assertFalse(envelope["network_access"])
        self.assertFalse(envelope["shell_access"])
        self.assertEqual(envelope["input_scope"]["paths_allowed"], ["docs/full_chain_target.md"])
        self.assertNotIn("worker_output", envelope_result)
        self.assertNotIn("approved", json.dumps(envelope_result).lower())
        self.assertNotIn("execution_result", envelope_result)
        self.assertNotIn("verification_result", envelope_result)
        self.assertNotIn("governance_result", envelope_result)

        self.assertEqual(invocation_result["decision"], "completed_candidate")
        self.assertEqual(invocation_result["preflight"]["decision"], "allow")
        self.assertIsNotNone(invocation_result["worker_output"])
        self.assertEqual(invocation_result["worker_output"]["candidate_status"], "candidate")
        self.assertEqual(invocation_result["worker_output"]["worker_id"], "repo_research_worker")
        self.assertTrue(invocation_result["worker_output"]["evidence_handles"])
        self.assertIsNone(invocation_result["side_effect_request"])
        self.assertIsNone(invocation_result["worker_output"]["side_effect_request"])
        self.assertEqual(invocation_result["return_path"], envelope["return_path"])
        self.assertEqual(
            invocation_result["worker_output"]["content"]["findings"][0]["path"],
            smoke_file.relative_to(repo_root).as_posix(),
        )
        self.assertEqual(invocation_result["worker_output"]["content"]["findings"][0]["status"], "matched")
        self.assertIn(
            "FULL_CHAIN_SMOKE_MARKER",
            invocation_result["worker_output"]["content"]["findings"][0]["snippets"][0]["snippet"],
        )
        self.assertNotIn("verified", invocation_result["worker_output"]["content"]["summary"].lower())
        self.assertNotIn("approved", invocation_result["worker_output"]["content"]["summary"].lower())
        self.assertTrue(opened_paths)
        self.assertTrue(all(path == smoke_file for path in opened_paths))
        self.assertEqual(
            smoke_file.read_text(encoding="utf-8"),
            "FULL_CHAIN_SMOKE_MARKER: evidence from routing to builder to controlled invocation.\n",
        )

    def test_money_touching_route_blocks_before_builder_or_invocation(self) -> None:
        temp_dir, repo_root, smoke_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._routing_request("docs/full_chain_target.md")
        request["money_touching_intent"] = True
        builder = Mock(side_effect=AssertionError("builder must not run"))
        invocation = Mock(side_effect=AssertionError("controlled invocation must not run"))

        routing_decision = route_mainbrain_worker_request(request)
        if routing_decision["decision"] == "route_repo_research_worker":
            builder(routing_decision, requested_by="MainBrain")
            invocation({}, repo_root)

        self.assertEqual(routing_decision["decision"], "blocked")
        builder.assert_not_called()
        invocation.assert_not_called()
        self.assertEqual(smoke_file.read_text(encoding="utf-8"), "FULL_CHAIN_SMOKE_MARKER: evidence from routing to builder to controlled invocation.\n")

    def test_network_intent_route_stops_before_builder_or_invocation(self) -> None:
        temp_dir, repo_root, smoke_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._routing_request("docs/full_chain_target.md")
        request["network_intent"] = True
        builder = Mock(side_effect=AssertionError("builder must not run"))
        invocation = Mock(side_effect=AssertionError("controlled invocation must not run"))

        routing_decision = route_mainbrain_worker_request(request)
        if routing_decision["decision"] == "route_repo_research_worker":
            builder(routing_decision, requested_by="MainBrain")
            invocation({}, repo_root)

        self.assertIn(routing_decision["decision"], {"needs_approval", "blocked"})
        builder.assert_not_called()
        invocation.assert_not_called()
        self.assertEqual(smoke_file.read_text(encoding="utf-8"), "FULL_CHAIN_SMOKE_MARKER: evidence from routing to builder to controlled invocation.\n")

    def test_empty_candidate_paths_invalid_request_before_builder_or_invocation(self) -> None:
        temp_dir, repo_root, smoke_file = self._make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        request = self._routing_request("docs/full_chain_target.md")
        request["candidate_paths"] = []
        builder = Mock(side_effect=AssertionError("builder must not run"))
        invocation = Mock(side_effect=AssertionError("controlled invocation must not run"))

        routing_decision = route_mainbrain_worker_request(request)
        if routing_decision["decision"] == "route_repo_research_worker":
            builder(routing_decision, requested_by="MainBrain")
            invocation({}, repo_root)

        self.assertEqual(routing_decision["decision"], "invalid_request")
        builder.assert_not_called()
        invocation.assert_not_called()
        self.assertEqual(smoke_file.read_text(encoding="utf-8"), "FULL_CHAIN_SMOKE_MARKER: evidence from routing to builder to controlled invocation.\n")

    def test_malformed_routing_decision_sent_directly_to_builder(self) -> None:
        malformed = {"task_id": "task_045", "decision": "route_repo_research_worker"}
        invocation = Mock(side_effect=AssertionError("controlled invocation must not run"))

        builder_result = build_worker_invocation_envelope_from_routing_decision(malformed, requested_by="MainBrain")
        if builder_result["decision"] == "built_envelope":
            invocation(builder_result["envelope"], Path("/tmp/unused"))

        self.assertEqual(builder_result["decision"], "invalid_routing_decision")
        self.assertIsNone(builder_result["envelope"])
        invocation.assert_not_called()

    def test_builder_blocked_result_does_not_reach_invocation(self) -> None:
        unsupported_worker_decision = {
            "task_id": "task_045",
            "decision": "route_repo_research_worker",
            "reasons": ["candidate_repo_evidence"],
            "selected_worker": {
                "worker_id": "unknown_worker",
                "worker_type": "read_only_repo_research",
            },
            "invocation_purpose": "candidate_repo_evidence",
            "proposed_input_scope": {
                "paths_allowed": ["docs/full_chain_target.md"],
                "paths_excluded": [],
                "research_question": "Find the full chain smoke marker.",
                "max_files": 5,
                "max_bytes_per_file": 20_000,
            },
            "required_envelope_fields": ["invocation_id", "task_id", "requested_by"],
            "approval_required": False,
            "blocked_reasons": [],
            "limitations": ["Workflow network ≠ runtime network."],
            "next_step": "Build a WorkerInvocationEnvelope.",
            "generated_at": "1970-01-01T00:00:00Z",
        }
        invocation = Mock(side_effect=AssertionError("controlled invocation must not run"))

        builder_result = build_worker_invocation_envelope_from_routing_decision(
            unsupported_worker_decision,
            requested_by="MainBrain",
            invocation_id="task_045_invocation",
            created_at="task_045_static_timestamp",
        )
        if builder_result["decision"] == "built_envelope":
            invocation(builder_result["envelope"], Path("/tmp/unused"))

        self.assertEqual(builder_result["decision"], "blocked")
        self.assertIsNone(builder_result["envelope"])
        invocation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
