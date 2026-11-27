from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.workers import repo_research_worker as worker_mod
from runtime.workers.repo_research_worker import run_repo_research_worker


class RepoResearchWorkerTest(unittest.TestCase):
    def base_envelope(self, input_scope: dict[str, object] | None = None) -> dict[str, object]:
        scope = input_scope or {
            "paths_allowed": ["Specs/workers/repo_research_worker_spec_v0.1.md"],
            "paths_excluded": [],
            "research_question": "Find the Repo Research Worker core line.",
            "max_files": 5,
            "max_bytes_per_file": 20_000,
        }
        return {
            "invocation_id": "inv-037",
            "task_id": "task-037",
            "requested_by": "MainBrain",
            "worker_id": "repo_research_worker",
            "worker_type": "read_only_repo_research",
            "invocation_purpose": "repo research runtime prototype",
            "input_scope": scope,
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

    def make_repo(self) -> tuple[tempfile.TemporaryDirectory, Path, Path, Path]:
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        allowed = root / "allowed"
        allowed.mkdir()
        file_path = allowed / "research.txt"
        file_path.write_text(
            "Repo Research Worker may run only after Preflight Guard returns allow.\n"
            "Repo Research Worker reads scoped repo files and returns candidate evidence.\n",
            encoding="utf-8",
        )
        return td, root, allowed, file_path

    def test_valid_envelope_plus_scoped_file_returns_candidate_packet(self):
        td, root, allowed, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope({
            "paths_allowed": [str(file_path)],
            "paths_excluded": [],
            "research_question": "Repo Research Worker core line",
            "max_files": 5,
            "max_bytes_per_file": 20_000,
        })

        packet = run_repo_research_worker(envelope, root)

        self.assertEqual(packet["candidate_status"], "candidate")
        self.assertEqual(packet["output_type"], "candidate_repo_findings")
        self.assertEqual(packet["worker_id"], "repo_research_worker")
        self.assertGreaterEqual(len(packet["content"]["findings"]), 1)
        self.assertTrue(any(h["evidence_type"] == "file_content" for h in packet["evidence_handles"]))
        self.assertEqual(packet["side_effect_request"], None)
        self.assertIn(packet["confidence"], {"low", "medium", "high"})
        self.assertNotIn("complete", packet["content"]["summary"].lower())
        self.assertNotIn("verified", packet["content"]["summary"].lower())

    def test_worker_calls_preflight_and_blocks_when_invalid_envelope(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope({"paths_allowed": [str(file_path)]})

        with patch.object(worker_mod, "validate_worker_invocation_envelope", return_value={"decision": "invalid_envelope", "reasons": ["test"]}), patch.object(worker_mod, "_collect_scoped_evidence", side_effect=AssertionError("should not read")):
            packet = run_repo_research_worker(envelope, root)

        self.assertEqual(packet["candidate_status"], "blocked")
        self.assertEqual(packet["preflight"]["decision"], "invalid_envelope")

    def test_worker_blocks_when_preflight_needs_approval(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope({"paths_allowed": [str(file_path)]})

        with patch.object(worker_mod, "validate_worker_invocation_envelope", return_value={"decision": "needs_approval", "reasons": ["approval_required"]}), patch.object(worker_mod, "_collect_scoped_evidence", side_effect=AssertionError("should not read")):
            packet = run_repo_research_worker(envelope, root)

        self.assertEqual(packet["candidate_status"], "blocked")
        self.assertEqual(packet["preflight"]["decision"], "needs_approval")

    def test_worker_blocks_when_preflight_blocks(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope({"paths_allowed": [str(file_path)]})

        with patch.object(worker_mod, "validate_worker_invocation_envelope", return_value={"decision": "block", "reasons": ["blocked"]}), patch.object(worker_mod, "_collect_scoped_evidence", side_effect=AssertionError("should not read")):
            packet = run_repo_research_worker(envelope, root)

        self.assertEqual(packet["candidate_status"], "blocked")
        self.assertEqual(packet["preflight"]["decision"], "block")

    def test_missing_input_scope_returns_blocked(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope()
        envelope.pop("input_scope")

        packet = run_repo_research_worker(envelope, root)

        self.assertEqual(packet["candidate_status"], "blocked")

    def test_empty_paths_allowed_returns_blocked(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope({"paths_allowed": [], "paths_excluded": [], "research_question": "x", "max_files": 5, "max_bytes_per_file": 100})

        packet = run_repo_research_worker(envelope, root)

        self.assertEqual(packet["candidate_status"], "blocked")

    def test_path_traversal_outside_repo_root_returns_blocked(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        outside = root.parent / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        envelope = self.base_envelope({"paths_allowed": [str(Path("..").joinpath(outside.name))], "paths_excluded": [], "research_question": "outside", "max_files": 5, "max_bytes_per_file": 100})

        packet = run_repo_research_worker(envelope, root)

        self.assertEqual(packet["candidate_status"], "blocked")
        self.assertTrue(any(isinstance(item, dict) and item.get("reason") == "path_escapes_repo_root" for item in packet["blocked_items"]))

    def test_excluded_path_is_not_read_and_is_reported(self):
        td, root, allowed, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        excluded = allowed / "excluded.txt"
        excluded.write_text("Repo Research Worker hidden excluded evidence", encoding="utf-8")
        allowed_file = allowed / "allowed.txt"
        allowed_file.write_text("Repo Research Worker visible evidence", encoding="utf-8")
        envelope = self.base_envelope({
            "paths_allowed": [str(allowed)],
            "paths_excluded": [str(excluded)],
            "research_question": "Repo Research Worker",
            "max_files": 5,
            "max_bytes_per_file": 20_000,
        })

        packet = run_repo_research_worker(envelope, root)

        paths = [finding["path"] for finding in packet["content"]["findings"]]
        self.assertIn(str(allowed_file.relative_to(root)), paths)
        self.assertNotIn(str(excluded.relative_to(root)), paths)
        self.assertTrue(any(item.get("status") == "skipped" for item in packet["blocked_items"]))

    def test_secret_path_scope_is_blocked_before_read(self):
        td, root, _, _ = self.make_repo()
        self.addCleanup(td.cleanup)
        key = "sk-proj-" + "abcdefghijklmnopqrstuvwxyz1234567890"
        env_file = root / ".env.local"
        # The path alone must be denied; no credential-like file is created.
        envelope = self.base_envelope({
            "paths_allowed": [str(env_file)],
            "paths_excluded": [],
            "research_question": "OPENAI_API_KEY",
            "max_files": 1,
            "max_bytes_per_file": 200,
        })

        with patch.object(worker_mod, "_read_text_file", side_effect=AssertionError("secret path must not be read")):
            packet = run_repo_research_worker(envelope, root)

        self.assertEqual(packet["candidate_status"], "blocked")
        self.assertNotIn(key, repr(packet))

    def test_secret_like_content_is_redacted_from_snippets(self):
        td, root, allowed, _ = self.make_repo()
        self.addCleanup(td.cleanup)
        key = "sk-proj-" + "abcdefghijklmnopqrstuvwxyz1234567890"
        file_path = allowed / "safe_name.txt"
        file_path.write_text(
            "The deployment note says OPENAI_API_KEY=" + key + " for testing.",
            encoding="utf-8",
        )
        envelope = self.base_envelope({
            "paths_allowed": [str(file_path)],
            "paths_excluded": [],
            "research_question": "OPENAI_API_KEY deployment",
            "max_files": 5,
            "max_bytes_per_file": 20_000,
        })

        packet = run_repo_research_worker(envelope, root)

        rendered = repr(packet)
        self.assertEqual(packet["candidate_status"], "candidate")
        self.assertNotIn(key, rendered)
        self.assertIn("[REDACTED_OPENAI_API_KEY]", rendered)
        self.assertTrue(any(limit.startswith("secret_like_content_redacted:") for limit in packet["limitations"]))
        self.assertTrue(any(handle["evidence_type"] == "secret_redaction" for handle in packet["evidence_handles"]))

    def test_directory_scope_rejects_private_children_and_links(self):
        td, root, allowed, _ = self.make_repo()
        self.addCleanup(td.cleanup)
        private = allowed / "runtime_state"
        private.mkdir()
        target = private / "state.txt"
        target.write_text("PRIVATE_FIXTURE_NOT_FOR_OUTPUT", encoding="utf-8")
        alias = allowed / "alias.txt"
        alias.symlink_to(target)
        envelope = self.base_envelope({
            "paths_allowed": [str(allowed)], "paths_excluded": [],
            "research_question": "PRIVATE_FIXTURE_NOT_FOR_OUTPUT",
            "max_files": 5, "max_bytes_per_file": 20000,
        })
        original = worker_mod._read_text_file
        def guarded_read(path, size):
            self.assertNotIn(path, {target, alias})
            return original(path, size)
        with patch.object(worker_mod, "_read_text_file", side_effect=guarded_read):
            packet = run_repo_research_worker(envelope, root)
        self.assertNotIn("PRIVATE_FIXTURE_NOT_FOR_OUTPUT", repr(packet["content"]))
        self.assertTrue(any(item.get("reason") == "private_or_linked_path_blocked" for item in packet["blocked_items"]))

    def test_truncated_text_does_not_emit_partial_credentials(self):
        td, root, _, _ = self.make_repo()
        self.addCleanup(td.cleanup)
        target = root / "fragment.txt"
        target.write_text("marker " + "sk-proj-" + "a"*70, encoding="utf-8")
        envelope = self.base_envelope({
            "paths_allowed": [str(target)], "paths_excluded": [],
            "research_question": "marker", "max_files": 1,
            "max_bytes_per_file": 20,
        })
        packet = run_repo_research_worker(envelope, root)
        finding = packet["content"]["findings"][0]
        self.assertTrue(finding["truncated"])
        self.assertEqual(finding["snippets"], [])

    def test_max_files_is_enforced(self):
        td, root, _, _ = self.make_repo()
        self.addCleanup(td.cleanup)
        folder = root / "bulk"
        folder.mkdir()
        for index in range(6):
            (folder / f"file_{index}.txt").write_text(f"Repo Research Worker file {index}", encoding="utf-8")
        envelope = self.base_envelope({
            "paths_allowed": [str(folder)],
            "paths_excluded": [],
            "research_question": "Repo Research Worker",
            "max_files": 3,
            "max_bytes_per_file": 20_000,
        })

        packet = run_repo_research_worker(envelope, root)

        self.assertLessEqual(len(packet["content"]["findings"]), 3)
        self.assertTrue(any(limit == "max_files_reached" for limit in packet["limitations"]))

    def test_max_bytes_per_file_is_enforced(self):
        td, root, _, _ = self.make_repo()
        self.addCleanup(td.cleanup)
        big_file = root / "big.txt"
        big_file.write_text("A" * 5000 + " Repo Research Worker marker", encoding="utf-8")
        envelope = self.base_envelope({
            "paths_allowed": [str(big_file)],
            "paths_excluded": [],
            "research_question": "Repo Research Worker marker",
            "max_files": 5,
            "max_bytes_per_file": 100,
        })

        packet = run_repo_research_worker(envelope, root)

        finding = packet["content"]["findings"][0]
        self.assertLessEqual(finding["bytes_read"], 100)
        self.assertTrue(finding["truncated"])
        self.assertTrue(any(limit.startswith("truncated:") for limit in packet["limitations"]))

    def test_evidence_handles_include_file_existence_and_content(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope({"paths_allowed": [str(file_path)], "paths_excluded": [], "research_question": "Repo Research Worker", "max_files": 5, "max_bytes_per_file": 20_000})

        packet = run_repo_research_worker(envelope, root)

        evidence_types = {handle["evidence_type"] for handle in packet["evidence_handles"]}
        self.assertIn("file_existence", evidence_types)
        self.assertIn("file_content", evidence_types)

    def test_candidate_status_is_candidate_only_on_allowed_read(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope({"paths_allowed": [str(file_path)], "paths_excluded": [], "research_question": "Repo Research Worker", "max_files": 5, "max_bytes_per_file": 20_000})

        packet = run_repo_research_worker(envelope, root)

        self.assertEqual(packet["candidate_status"], "candidate")
        self.assertGreater(len(packet["content"]["findings"]), 0)

    def test_side_effect_request_is_always_none(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope({"paths_allowed": [str(file_path)], "paths_excluded": [], "research_question": "Repo Research Worker", "max_files": 5, "max_bytes_per_file": 20_000})

        packet = run_repo_research_worker(envelope, root)

        self.assertIsNone(packet["side_effect_request"])

    def test_worker_does_not_mutate_scoped_files(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        before = file_path.read_text(encoding="utf-8")
        envelope = self.base_envelope({"paths_allowed": [str(file_path)], "paths_excluded": [], "research_question": "Repo Research Worker", "max_files": 5, "max_bytes_per_file": 20_000})

        _ = run_repo_research_worker(envelope, root)
        after = file_path.read_text(encoding="utf-8")

        self.assertEqual(before, after)

    def test_worker_does_not_read_outside_paths_allowed(self):
        td, root, allowed, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        outside = root / "outside.txt"
        outside.write_text("Repo Research Worker outside secret", encoding="utf-8")
        envelope = self.base_envelope({
            "paths_allowed": [str(file_path)],
            "paths_excluded": [],
            "research_question": "outside secret",
            "max_files": 5,
            "max_bytes_per_file": 20_000,
        })

        packet = run_repo_research_worker(envelope, root)

        joined = repr(packet["content"]["findings"]).lower()
        self.assertNotIn("outside secret", joined)
        self.assertNotIn(str(outside), joined)

    def test_confidence_enum_is_low_medium_high_only(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope({"paths_allowed": [str(file_path)], "paths_excluded": [], "research_question": "Repo Research Worker", "max_files": 5, "max_bytes_per_file": 20_000})

        packet = run_repo_research_worker(envelope, root)

        self.assertIn(packet["confidence"], {"low", "medium", "high"})

    def test_no_task_complete_or_verified_language_appears_in_summary(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope({"paths_allowed": [str(file_path)], "paths_excluded": [], "research_question": "Repo Research Worker", "max_files": 5, "max_bytes_per_file": 20_000})

        packet = run_repo_research_worker(envelope, root)
        summary = packet["content"]["summary"].lower()

        self.assertNotIn("task complete", summary)
        self.assertNotIn("verified", summary)
        self.assertNotIn("final", summary)

    def test_money_touching_true_envelope_does_not_run_and_returns_blocked(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope({"paths_allowed": [str(file_path)], "paths_excluded": [], "research_question": "Repo Research Worker", "max_files": 5, "max_bytes_per_file": 20_000})
        envelope["money_touching"] = True

        packet = run_repo_research_worker(envelope, root)

        self.assertEqual(packet["candidate_status"], "blocked")
        self.assertEqual(packet["preflight"]["decision"], "block")

    def test_network_access_true_envelope_does_not_run(self):
        td, root, _, file_path = self.make_repo()
        self.addCleanup(td.cleanup)
        envelope = self.base_envelope({"paths_allowed": [str(file_path)], "paths_excluded": [], "research_question": "Repo Research Worker", "max_files": 5, "max_bytes_per_file": 20_000})
        envelope["network_access"] = True

        packet = run_repo_research_worker(envelope, root)

        self.assertEqual(packet["candidate_status"], "blocked")
        self.assertIn(packet["preflight"]["decision"], {"block", "needs_approval"})

    def test_symlink_escape_is_blocked_or_not_followed(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink not supported")
        td, root, _, _ = self.make_repo()
        self.addCleanup(td.cleanup)
        outside = root.parent / "outside_target.txt"
        outside.write_text("Repo Research Worker outside target", encoding="utf-8")
        inner = root / "linked.txt"
        os.symlink(outside, inner)
        envelope = self.base_envelope({"paths_allowed": [str(inner)], "paths_excluded": [], "research_question": "outside target", "max_files": 5, "max_bytes_per_file": 20_000})

        packet = run_repo_research_worker(envelope, root)

        self.assertEqual(packet["candidate_status"], "blocked")
        self.assertTrue(any(isinstance(item, dict) and item.get("reason") == "path_escapes_repo_root" for item in packet["blocked_items"]))


if __name__ == "__main__":
    unittest.main()
