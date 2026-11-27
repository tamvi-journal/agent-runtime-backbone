from __future__ import annotations

from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from runtime.workers.controlled_invocation import invoke_worker_with_envelope


class ControlledInvocationSmokeTest(unittest.TestCase):
    def build_envelope(self, scope_path: str, *, money_touching: bool = False, input_scope: object | None = None) -> dict[str, object]:
        scope = input_scope
        if scope is None:
            scope = {
                "paths_allowed": [scope_path],
                "paths_excluded": [],
                "research_question": "worker smoke marker evidence",
                "max_files": 1,
                "max_bytes_per_file": 5000,
            }

        return {
            "invocation_id": "inv-039-smoke",
            "task_id": "task-039",
            "requested_by": "MainBrain",
            "worker_id": "repo_research_worker",
            "worker_type": "read_only_repo_research",
            "invocation_purpose": "Task 039 controlled repo research smoke test",
            "input_scope": scope,
            "permission_class": "read_only",
            "security_profile": "repo_read_only_no_network",
            "execution_surface": "direct_tool",
            "allowed_tools": ["read_file"],
            "forbidden_tools": [],
            "auto_allowed_actions": ["read_file"],
            "approval_required_actions": [],
            "blocked_actions": [],
            "side_effect_class": "money_touching" if money_touching else "repo_read",
            "money_touching": money_touching,
            "external_mutation": False,
            "network_access": False,
            "shell_access": False,
            "model_provider_policy": {"visibility": "not_visible_to_runtime"},
            "memory_context_policy": {"mode": "candidate_context_only"},
            "verification_expectation": {"mode": "verify_before_completion"},
            "governance_expectation": {"mode": "mainbrain_routing"},
            "output_contract": "WorkerOutputPacket candidate contribution only",
            "return_path": "MainBrain/Agent routing",
            "escalation_policy": {"gate": "none"},
            "abort_conditions": [],
            "created_at": "2026-05-08T00:00:00Z",
        }

    def make_temp_repo(self) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        repo_root = Path(temp_dir.name)
        scoped_file = repo_root / "scoped.md"
        scoped_file.write_text(
            "WORKER_SMOKE_MARKER: repo research worker smoke test evidence.\n",
            encoding="utf-8",
        )
        return temp_dir, repo_root, scoped_file

    def test_controlled_invocation_smoke_end_to_end(self) -> None:
        temp_dir, repo_root, scoped_file = self.make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        envelope = self.build_envelope(str(scoped_file))

        opened_paths: list[Path] = []
        created_writes: list[Path] = []
        created_touches: list[Path] = []
        created_mkdirs: list[Path] = []
        original_open = os.open

        def recording_open(path, *args, **kwargs):
            opened_paths.append(Path(path))
            return original_open(path, *args, **kwargs)

        def record_write(self: Path, *args, **kwargs):
            created_writes.append(self)
            raise AssertionError("smoke invocation must not write files")

        def record_touch(self: Path, *args, **kwargs):
            created_touches.append(self)
            raise AssertionError("smoke invocation must not touch files")

        def record_mkdir(self: Path, *args, **kwargs):
            created_mkdirs.append(self)
            raise AssertionError("smoke invocation must not create directories")

        with patch("os.open", new=recording_open), patch("pathlib.Path.write_text", new=record_write), patch("pathlib.Path.touch", new=record_touch), patch("pathlib.Path.mkdir", new=record_mkdir):
            result = invoke_worker_with_envelope(envelope, repo_root)

        self.assertEqual(result["decision"], "completed_candidate")
        self.assertEqual(result["preflight"]["decision"], "allow")
        self.assertIsNotNone(result["worker_output"])
        self.assertEqual(result["worker_output"]["candidate_status"], "candidate")
        self.assertEqual(result["worker_output"]["worker_id"], "repo_research_worker")
        self.assertTrue(result["worker_output"]["evidence_handles"])
        self.assertIsNone(result["side_effect_request"])
        self.assertIsNone(result["worker_output"]["side_effect_request"])
        self.assertEqual(result["return_path"], "MainBrain/Agent routing")
        self.assertEqual(result["worker_output"]["content"]["findings"][0]["path"], scoped_file.name)
        self.assertEqual(result["worker_output"]["content"]["findings"][0]["status"], "matched")
        self.assertIn("WORKER_SMOKE_MARKER", result["worker_output"]["content"]["findings"][0]["snippets"][0]["snippet"])
        self.assertNotIn("verified", result["worker_output"]["content"]["summary"].lower())
        self.assertNotIn("approved", result["worker_output"]["content"]["summary"].lower())
        self.assertFalse(created_writes)
        self.assertFalse(created_touches)
        self.assertFalse(created_mkdirs)
        self.assertTrue(opened_paths)
        self.assertTrue(all(path == scoped_file for path in opened_paths))
        before = scoped_file.read_text(encoding="utf-8")
        after = scoped_file.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_money_touching_blocks_without_running_worker(self) -> None:
        temp_dir, repo_root, scoped_file = self.make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        envelope = self.build_envelope(str(scoped_file), money_touching=True)
        worker = Mock(side_effect=AssertionError("worker must not run"))

        with patch("runtime.workers.controlled_invocation.run_repo_research_worker", worker):
            result = invoke_worker_with_envelope(envelope, repo_root)

        self.assertNotEqual(result["decision"], "completed_candidate")
        self.assertIsNone(result["worker_output"])
        worker.assert_not_called()

    def test_path_traversal_scope_blocks_and_does_not_read_outside_repo(self) -> None:
        temp_dir, repo_root, scoped_file = self.make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        envelope = self.build_envelope("../outside.md", input_scope={
            "paths_allowed": ["../outside.md"],
            "paths_excluded": [],
            "research_question": "worker smoke marker evidence",
            "max_files": 1,
            "max_bytes_per_file": 5000,
        })

        opened_paths: list[Path] = []
        original_open = os.open

        def recording_open(path, *args, **kwargs):
            opened_paths.append(Path(path))
            return original_open(path, *args, **kwargs)

        with patch("os.open", new=recording_open):
            result = invoke_worker_with_envelope(envelope, repo_root)

        self.assertEqual(result["preflight"]["decision"], "allow")
        self.assertNotEqual(result["decision"], "completed_candidate")
        self.assertIsNotNone(result["worker_output"])
        self.assertEqual(result["worker_output"]["candidate_status"], "blocked")
        self.assertFalse(opened_paths)
        self.assertEqual(scoped_file.read_text(encoding="utf-8"), "WORKER_SMOKE_MARKER: repo research worker smoke test evidence.\n")

    def test_missing_input_scope_blocks_before_worker_runs(self) -> None:
        temp_dir, repo_root, scoped_file = self.make_temp_repo()
        self.addCleanup(temp_dir.cleanup)
        envelope = self.build_envelope(str(scoped_file), input_scope=None)
        del envelope["input_scope"]
        worker = Mock(side_effect=AssertionError("worker must not run"))

        with patch("runtime.workers.controlled_invocation.run_repo_research_worker", worker):
            result = invoke_worker_with_envelope(envelope, repo_root)

        self.assertEqual(result["decision"], "invalid_envelope")
        self.assertEqual(result["preflight"]["decision"], "invalid_envelope")
        self.assertIsNone(result["worker_output"])
        worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
