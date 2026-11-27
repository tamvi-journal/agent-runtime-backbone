from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from runtime.skill_evolution import (
    HermesSkillProjection,
    IdempotencyConflict,
    ImmutableHistoryError,
    SkillEvolutionStore,
)
from runtime import create_agent_skill_evolution_store


NOW = "2026-08-31T12:00:00+00:00"
RECEIPT = {
    "receipt_id": "authority:owner:skill-review-1",
    "authority": "owner-controller",
    "status": "verified",
    "scope": "agent-skill-promotion",
}


def proposer() -> dict:
    return {
        "actor": "agent-mainbrain",
        "surface": "agent-hermes",
        "model": "openai/gpt-5.6-sol",
    }


class SkillEvolutionStoreTest(unittest.TestCase):
    def test_runtime_export_creates_a_separate_ignored_state_store(self):
        with tempfile.TemporaryDirectory() as root:
            store = create_agent_skill_evolution_store(root)
            self.assertIsInstance(store, SkillEvolutionStore)
            self.assertEqual(
                store.db_path,
                Path(root) / "runtime_state" / "skill_evolution" / "agent-skill-evolution.sqlite3",
            )
            self.assertTrue(store.db_path.exists())

    def make_store(self, root: str) -> SkillEvolutionStore:
        return SkillEvolutionStore(
            Path(root) / "agent-skill-evolution.sqlite3",
            clock=lambda: NOW,
            authority_resolver=lambda receipt_id: RECEIPT
            if receipt_id == RECEIPT["receipt_id"]
            else None,
        )

    def add_evidence(self, store: SkillEvolutionStore) -> dict:
        return store.record_evidence_reference(
            operation_id="operation:evidence:1",
            evidence_id="evidence:trace:1",
            source_ref="agent:test:trace-1",
            source_sha256=hashlib.sha256(b"immutable trace one").hexdigest(),
            evidence_type="execution_trace",
            observed_at=NOW,
            provenance=proposer(),
        )

    def propose(self, store: SkillEvolutionStore, *, version="version:route:v1", parent=None, operation="operation:proposal:1", content="# Route\n\nUse the verified route.\n") -> dict:
        return store.propose_skill_version(
            operation_id=operation,
            skill_id="skill:route",
            version_id=version,
            parent_version_id=parent,
            content=content,
            semantic_diff={"summary": "require verified route", "breaking": False},
            unified_diff="+Use the verified route.",
            motivating_incident_ids=["incident:route:1"],
            evidence_ids=["evidence:trace:1"],
            proposer=proposer(),
            validation_plan={"command": "python -m unittest", "success": "all pass"},
        )

    def validate(self, store: SkillEvolutionStore, *, version="version:route:v1", decision="decision:route:v1", outcome="accepted", operation="operation:validation:1") -> dict:
        return store.record_validation_decision(
            operation_id=operation,
            decision_id=decision,
            skill_id="skill:route",
            version_id=version,
            outcome=outcome,
            scores={"baseline": 0.5, "candidate": 0.9},
            outputs=[{"ref": "test:route-suite", "sha256": hashlib.sha256(b"pass").hexdigest()}],
            reason=f"candidate {outcome}",
            validator={"actor": "agent-validator", "model": "openai/gpt-5.6-sol"},
            authority_receipt=RECEIPT,
        )

    def test_raw_evidence_pattern_revisions_and_evolution_log_are_append_only(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            evidence = self.add_evidence(store)
            first = store.record_pattern_revision(
                operation_id="operation:pattern:1", pattern_id="pattern:route", revision_id="pattern-revision:route:1",
                previous_revision_id=None, title="Wrong route", summary="An inferred route displaced verified input.",
                evidence_ids=[evidence["evidence_id"]], proposer=proposer(),
            )
            second = store.record_pattern_revision(
                operation_id="operation:pattern:2", pattern_id="pattern:route", revision_id="pattern-revision:route:2",
                previous_revision_id=first["revision_id"], title="Wrong route", summary="Current instructions must outrank stale inferred routes.",
                evidence_ids=[evidence["evidence_id"]], proposer=proposer(),
            )
            store.append_evolution_event(operation_id="operation:evolution:1", event_id="evolution:1", event_type="pattern_refined", refs=[second["revision_id"]], summary="Refined without rewriting r1.", provenance=proposer())
            self.assertEqual([row["revision_id"] for row in store.pattern_history("pattern:route")], [first["revision_id"], second["revision_id"]])
            with self.assertRaises(ImmutableHistoryError):
                store.unsafe_update_for_test("evidence_references", "evidence_id", evidence["evidence_id"])
            self.assertEqual(len(store.evolution_log()), 1)

    def test_versions_are_immutable_hashed_and_exactly_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            self.add_evidence(store)
            version = self.propose(store)
            self.assertEqual(version["content_sha256"], hashlib.sha256(version["content"].encode()).hexdigest())
            self.assertEqual(self.propose(store)["version_id"], version["version_id"])
            with self.assertRaises(IdempotencyConflict):
                self.propose(store, content="# changed")
            with self.assertRaises(ImmutableHistoryError):
                store.unsafe_update_for_test("skill_versions", "version_id", version["version_id"])

    def test_rejected_operation_id_is_reserved_and_mismatched_retry_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            self.add_evidence(store)
            with self.assertRaises(ValueError):
                store.promote(
                    operation_id="operation:promote:reserved",
                    skill_id="skill:missing",
                    version_id="version:missing",
                    expected_active_version_id=None,
                    decision_id="decision:missing",
                    authority_receipt_id=RECEIPT["receipt_id"],
                )
            with self.assertRaises(ImmutableHistoryError):
                store.unsafe_update_for_test(
                    "operation_outcomes",
                    "operation_id",
                    "operation:promote:reserved",
                )
            with self.assertRaises(IdempotencyConflict):
                store.promote(
                    operation_id="operation:promote:reserved",
                    skill_id="skill:different",
                    version_id="version:different",
                    expected_active_version_id=None,
                    decision_id="decision:different",
                    authority_receipt_id=RECEIPT["receipt_id"],
                )
            with self.assertRaises(ValueError):
                store.promote(
                    operation_id="operation:promote:reserved",
                    skill_id="skill:missing",
                    version_id="version:missing",
                    expected_active_version_id=None,
                    decision_id="decision:missing",
                    authority_receipt_id=RECEIPT["receipt_id"],
                )

    def test_all_validation_outcomes_are_retained_and_only_accepted_can_promote(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            self.add_evidence(store)
            self.propose(store)
            for index, outcome in enumerate(("rejected", "blocked", "expired"), 1):
                self.validate(store, decision=f"decision:{outcome}", outcome=outcome, operation=f"operation:validation:{index}")
            with self.assertRaises(ValueError):
                store.promote(
                    operation_id="operation:promote:bad", skill_id="skill:route", version_id="version:route:v1",
                    expected_active_version_id=None, decision_id="decision:rejected", authority_receipt_id=RECEIPT["receipt_id"],
                )
            accepted = self.validate(store, decision="decision:accepted", operation="operation:validation:accepted")
            pointer = store.promote(
                operation_id="operation:promote:1", skill_id="skill:route", version_id="version:route:v1",
                expected_active_version_id=None, decision_id=accepted["decision_id"], authority_receipt_id=RECEIPT["receipt_id"],
            )
            self.assertEqual(pointer["active_version_id"], "version:route:v1")
            self.assertEqual({row["outcome"] for row in store.validation_history("skill:route")}, {"accepted", "rejected", "blocked", "expired"})

    def test_rollback_moves_only_pointer_and_current_instruction_supersedes_stale_context(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            self.add_evidence(store)
            self.propose(store)
            accepted1 = self.validate(store, decision="decision:v1", operation="operation:validation:v1")
            store.promote(operation_id="operation:promote:v1", skill_id="skill:route", version_id="version:route:v1", expected_active_version_id=None, decision_id=accepted1["decision_id"], authority_receipt_id=RECEIPT["receipt_id"])
            self.propose(store, version="version:route:v2", parent="version:route:v1", operation="operation:proposal:v2", content="# Route v2\n")
            accepted2 = self.validate(store, version="version:route:v2", decision="decision:v2", operation="operation:validation:v2")
            store.promote(operation_id="operation:promote:v2", skill_id="skill:route", version_id="version:route:v2", expected_active_version_id="version:route:v1", decision_id=accepted2["decision_id"], authority_receipt_id=RECEIPT["receipt_id"])
            store.rollback(operation_id="operation:rollback:1", skill_id="skill:route", from_version_id="version:route:v2", to_version_id="version:route:v1", reason="regression", evidence_ids=["evidence:trace:1"], authority_receipt_id=RECEIPT["receipt_id"])
            packet = store.retrieve("route", mode="normal", budget_chars=3000, current_instruction="Use the owner's exact current route.")
            self.assertEqual(packet["active_version"]["version_id"], "version:route:v1")
            self.assertEqual(packet["instruction_precedence"], "current_instruction_supersedes_active_context")
            self.assertEqual(len(store.skill_history("skill:route")), 2)
            self.assertEqual([e["event_type"] for e in store.pointer_history("skill:route")], ["promote", "promote", "rollback"])

    def test_bounded_retrieval_modes_and_projection_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            self.add_evidence(store)
            self.propose(store)
            accepted = self.validate(store)
            store.promote(operation_id="operation:promote:1", skill_id="skill:route", version_id="version:route:v1", expected_active_version_id=None, decision_id=accepted["decision_id"], authority_receipt_id=RECEIPT["receipt_id"])
            normal = store.retrieve("route", mode="normal", budget_chars=3000)
            debug = store.retrieve("route", mode="debug", budget_chars=6000)
            audit = store.retrieve("route", mode="audit", budget_chars=12000)
            self.assertNotIn("validation_history", normal)
            self.assertIn("candidate_summaries", debug)
            self.assertIn("validation_history", audit)
            with self.assertRaises(ValueError):
                store.retrieve("route", mode="audit", budget_chars=10)

            live = Path(root) / "live-skills"
            live.mkdir()
            existing = live / "route" / "SKILL.md"
            existing.parent.mkdir()
            existing.write_text("existing-history", encoding="utf-8")
            projection = HermesSkillProjection(store, live)
            disabled = projection.project(skill_id="skill:route", enabled=False)
            self.assertEqual(disabled["status"], "disabled")
            self.assertEqual(existing.read_text(encoding="utf-8"), "existing-history")
            with self.assertRaises(FileExistsError):
                projection.project(skill_id="skill:route", enabled=True)
            self.assertEqual(existing.read_text(encoding="utf-8"), "existing-history")


if __name__ == "__main__":
    unittest.main()
