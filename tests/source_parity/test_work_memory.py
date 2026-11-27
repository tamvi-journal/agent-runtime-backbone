from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from runtime.work_memory import (
    AgentWorkMemoryHook,
    AgentWorkMemoryStore,
    WorkOperationConflict,
    WorkRevisionConflict,
)
from runtime import create_agent_work_memory_store


NOW = "2026-09-01T12:00:00+00:00"


class AgentWorkMemoryTest(unittest.TestCase):
    def make_store(self, root: str) -> AgentWorkMemoryStore:
        return AgentWorkMemoryStore(
            Path(root) / "agent-work-memory.sqlite3",
            clock=lambda: NOW,
        )

    def open_route_work(self, store: AgentWorkMemoryStore, *, suffix: str = "one") -> dict:
        return store.open_work(
            operation_id=f"operation:open:{suffix}",
            session_id=f"session:{suffix}",
            surface="agent-hermes",
            cluster="agent-work-memory",
            goal="Build cue-first Agent work continuity.",
            cue_terms=["agent", "lifecycle", "continuity"],
            initial_branch={
                "label": "lifecycle-hook",
                "purpose": "Connect bounded deltas to the real Agent runtime.",
                "cue_terms": ["hook", "lifecycle"],
                "return_point": "Return to the Agent work-memory root.",
            },
        )

    def test_contract_anchors_are_bounded_versioned_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            opened = self.open_route_work(store)
            task_id = opened["projection"]["task_id"]
            branch_id = opened["projection"]["active_branch_id"]

            with self.assertRaises(ValueError):
                store.checkpoint(
                    operation_id="operation:routine:too-long",
                    task_id=task_id,
                    expected_revision=1,
                    session_id="session:one",
                    surface="agent-hermes",
                    kind="progress",
                    summary="x" * 1001,
                    branch_id=branch_id,
                )

            first = store.checkpoint(
                operation_id="operation:anchor:one",
                task_id=task_id,
                expected_revision=1,
                session_id="session:one",
                surface="agent-hermes",
                kind="contract_anchor",
                summary="A" * 8000,
                branch_id=branch_id,
                provenance_refs=["owner:example:contract-one"],
            )
            first_id = first["event"]["event_id"]
            self.assertEqual(first["event"]["contract_version"], 1)

            with self.assertRaises(ValueError):
                store.checkpoint(
                    operation_id="operation:anchor:missing-parent",
                    task_id=task_id,
                    expected_revision=2,
                    session_id="session:one",
                    surface="agent-hermes",
                    kind="contract_anchor",
                    summary="revised without lineage",
                    branch_id=branch_id,
                    provenance_refs=["owner:example:contract-two"],
                )

            with self.assertRaises(WorkOperationConflict):
                store.checkpoint(
                    operation_id="operation:anchor:missing-parent",
                    task_id=task_id,
                    expected_revision=2,
                    session_id="session:one",
                    surface="agent-hermes",
                    kind="contract_anchor",
                    summary="different rejected retry",
                    branch_id=branch_id,
                    provenance_refs=["owner:example:contract-two", first_id],
                )

            with self.assertRaisesRegex(
                ValueError,
                "revised contract_anchor must reference the previous contract anchor",
            ):
                store.checkpoint(
                    operation_id="operation:anchor:missing-parent",
                    task_id=task_id,
                    expected_revision=2,
                    session_id="session:one",
                    surface="agent-hermes",
                    kind="contract_anchor",
                    summary="revised without lineage",
                    branch_id=branch_id,
                    provenance_refs=["owner:example:contract-two"],
                )

            second = store.checkpoint(
                operation_id="operation:anchor:two",
                task_id=task_id,
                expected_revision=2,
                session_id="session:one",
                surface="agent-hermes",
                kind="contract_anchor",
                summary="Revised contract without deleting version one.",
                branch_id=branch_id,
                provenance_refs=["owner:example:contract-two", first_id],
            )
            self.assertEqual(second["event"]["contract_version"], 2)
            self.assertEqual(second["event"]["previous_contract_anchor_id"], first_id)

            compact = store.context("agent lifecycle", task_id=task_id)
            self.assertNotIn("contract_anchor", compact)
            with self.assertRaises(ValueError):
                store.context(
                    "agent lifecycle",
                    task_id=task_id,
                    include_contract_anchor=True,
                    explicit_contract_opt_in=False,
                )
            historical = store.context(
                "agent lifecycle",
                task_id=task_id,
                include_contract_anchor=True,
                explicit_contract_opt_in=True,
                contract_anchor_id=first_id,
                budget_chars=20000,
            )
            self.assertEqual(historical["contract_anchor"]["content"], "A" * 8000)
            self.assertEqual(len(historical["contract_anchor_index"]), 2)

            with sqlite3.connect(store.db_path) as conn:
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        "UPDATE work_events SET summary='overwrite' WHERE event_id=?",
                        (first_id,),
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute("DELETE FROM work_events WHERE event_id=?", (first_id,))

    def test_public_runtime_factory_keeps_work_memory_in_its_own_store(self):
        with tempfile.TemporaryDirectory() as root:
            store = create_agent_work_memory_store(Path(root))
            self.assertEqual(
                store.db_path,
                Path(root) / "runtime_state/work_memory/agent-work-memory.sqlite3",
            )

    def test_retrieval_routes_by_exact_cues_before_loading_any_task_body(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            route = self.open_route_work(store, suffix="route")
            market = store.open_work(
                operation_id="operation:open:market",
                session_id="session:market",
                surface="agent-hermes",
                cluster="agent-market",
                goal="Monitor market evidence.",
                cue_terms=["market", "indicator"],
                initial_branch={
                    "label": "market-radar",
                    "purpose": "Track evidence families.",
                    "cue_terms": ["radar", "rsi"],
                    "return_point": "Return to the market root.",
                },
            )

            routed = store.route("agent lifecycle hook")
            self.assertEqual([item["task_id"] for item in routed], [route["projection"]["task_id"]])
            self.assertNotIn("goal", routed[0])
            self.assertNotIn("purpose", routed[0])
            with self.assertRaises(ValueError):
                store.context("market radar", task_id=route["projection"]["task_id"])
            candidates = store.context("market radar")
            self.assertEqual(candidates["candidates"][0]["task_id"], market["projection"]["task_id"])

    def test_branch_parking_preserves_return_point_and_history(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            opened = self.open_route_work(store)
            task_id = opened["projection"]["task_id"]
            first_branch = opened["projection"]["active_branch_id"]
            opened_second = store.checkpoint(
                operation_id="operation:branch:open",
                task_id=task_id,
                expected_revision=1,
                session_id="session:one",
                surface="agent-hermes",
                kind="branch_open",
                summary="Explore hook integration separately.",
                branch={
                    "label": "runtime-integration",
                    "purpose": "Verify the consuming Hermes hook.",
                    "cue_terms": ["runtime", "integration"],
                    "return_point": "Return after a live synthetic hook receipt.",
                },
            )
            second_branch = opened_second["projection"]["active_branch_id"]
            parked = store.checkpoint(
                operation_id="operation:branch:park",
                task_id=task_id,
                expected_revision=2,
                session_id="session:one",
                surface="agent-hermes",
                kind="branch_park",
                summary="Park runtime integration after preserving its return point.",
                branch_id=second_branch,
                branch_status="parked",
                provenance_refs=[opened_second["event"]["event_id"]],
            )
            branches = {item["branch_id"]: item for item in parked["projection"]["branches"]}
            self.assertEqual(branches[second_branch]["status"], "parked")
            self.assertEqual(branches[second_branch]["return_point"], "Return after a live synthetic hook receipt.")
            self.assertIn(first_branch, branches)
            self.assertEqual([event["kind"] for event in store.history(task_id)], ["open", "branch_open", "branch_park"])

    def test_hook_ignores_transcripts_and_captures_only_explicit_material_delta(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            opened = self.open_route_work(store)
            task_id = opened["projection"]["task_id"]
            branch_id = opened["projection"]["active_branch_id"]
            hook = AgentWorkMemoryHook(store)

            pre = hook.handle({
                "hook_event_name": "pre_llm_call",
                "session_id": "session:one",
                "extra": {"user_message": "Continue the Agent lifecycle hook."},
            })
            self.assertIn(task_id, pre["context"])
            self.assertIn("AGENT_WORK_DELTA", pre["context"])
            before = len(store.history(task_id))
            ignored = hook.handle({
                "hook_event_name": "post_llm_call",
                "session_id": "session:one",
                "extra": {
                    "turn_id": "turn:no-delta",
                    "user_message": "Thanks",
                    "assistant_response": "Ordinary conversation RAW_TRANSCRIPT_SENTINEL",
                },
            })
            self.assertEqual(ignored["status"], "ignored_no_material_delta")
            self.assertEqual(len(store.history(task_id)), before)

            marker = {
                "action": "checkpoint",
                "task_id": task_id,
                "expected_revision": 1,
                "kind": "outcome",
                "summary": "Focused work-memory tests passed and direction remains aligned.",
                "branch_id": branch_id,
                "provenance_refs": ["test:agent-work-memory:pass"],
                "open_loops": [],
                "next_action": None,
            }
            captured = hook.handle({
                "hook_event_name": "post_llm_call",
                "session_id": "session:one",
                "extra": {
                    "turn_id": "turn:material-delta",
                    "user_message": "Finish the Agent lifecycle hook.",
                    "assistant_response": "Done. RAW_TRANSCRIPT_SENTINEL\n<!--AGENT_WORK_DELTA\n" + json.dumps(marker) + "\n-->",
                },
            })
            self.assertEqual(captured["status"], "captured")
            history = store.history(task_id)
            self.assertEqual(history[-1]["summary"], marker["summary"])
            self.assertNotIn("RAW_TRANSCRIPT_SENTINEL", json.dumps(history))

            with sqlite3.connect(store.db_path) as conn:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn("skill_versions", tables)
            self.assertNotIn("pattern_revisions", tables)

    def test_executable_hook_uses_the_real_json_wire_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            db_path = Path(root) / "wire.sqlite3"
            store = AgentWorkMemoryStore(db_path, clock=lambda: NOW)
            self.open_route_work(store)
            db_path.chmod(0o600)
            script = Path(__file__).resolve().parents[2] / "runtime" / "agent_work_memory_hook.py"
            payload = {
                "hook_event_name": "pre_llm_call",
                "session_id": "session:wire",
                "extra": {"user_message": "agent lifecycle hook"},
            }
            env = os.environ.copy()
            env["AGENT_WORK_MEMORY_DB"] = str(db_path)
            result = subprocess.run(
                [sys.executable, str(script)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertIn("AGENT_WORK_DELTA", output["context"])


if __name__ == "__main__":
    unittest.main()
