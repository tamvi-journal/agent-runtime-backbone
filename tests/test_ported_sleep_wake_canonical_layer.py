import unittest

from runtime.contracts.sleep_types import AgentIdentity, DeltaState, LiveState
from runtime.sleep.snapshot import build_sleep_snapshot, validate_sleep_snapshot
from runtime.sleep.store import InMemorySleepSnapshotStore
from runtime.sleep.wake_sanity import run_wake_sanity_pass


EXAMPLE_AGENT_IDENTITY: AgentIdentity = {
    "agent_name": "ExampleAgent",
    "agent_role": "runtime-continuity-agent",
    "lineage": "example-lineage",
    "version": "0.1",
}

LIVE_STATE: LiveState = {
    "coherence": 0.82,
    "uncertainty": 0.21,
    "level": "low",
    "verification_status": "verified",
    "current_focus": "sleep wake canonical layer",
}

DELTA_STATE: DeltaState = {
    "changed_since_last_snapshot": ["added canonical files"],
    "last_success": "created snapshot contract",
    "last_failure": None,
    "last_blocker": None,
    "next_safe_action": "run wake sanity pass",
}


class SleepWakeCanonicalLayerTest(unittest.TestCase):
    def test_sleep_snapshot_required_fields_and_false_continuity_guard(self):
        snapshot = build_sleep_snapshot(
            agent_identity=EXAMPLE_AGENT_IDENTITY,
            task_id="task_013_sleep_wake_canonical_layer",
            route_class="kernel_capability_path",
            gate_decision="allow",
            active_mode="dormant_runtime_contract",
            live_state=LIVE_STATE,
            delta_state=DELTA_STATE,
        )
        ok, reasons = validate_sleep_snapshot(dict(snapshot))

        self.assertTrue(ok)
        self.assertEqual(reasons, [])
        self.assertIn("cannot_claim_full_continuity", snapshot["forbidden_claims"])
        self.assertTrue(snapshot["snapshot_id"].startswith("sleep_"))

    def test_sleep_snapshot_rejects_raw_transcript_dump_shape(self):
        snapshot = build_sleep_snapshot(
            agent_identity=EXAMPLE_AGENT_IDENTITY,
            task_id="task_013_sleep_wake_canonical_layer",
            route_class="kernel_capability_path",
            gate_decision="allow",
            active_mode="dormant_runtime_contract",
            live_state=LIVE_STATE,
            delta_state=DELTA_STATE,
        )
        malformed = dict(snapshot)
        malformed["raw_transcript"] = "x" * 501
        ok, reasons = validate_sleep_snapshot(malformed)

        self.assertFalse(ok)
        self.assertIn("raw_transcript_shape_not_allowed", reasons)

    def test_wake_blocks_identity_mismatch(self):
        snapshot = build_sleep_snapshot(
            agent_identity=EXAMPLE_AGENT_IDENTITY,
            task_id="task_013_sleep_wake_canonical_layer",
            route_class="kernel_capability_path",
            gate_decision="allow",
            active_mode="dormant_runtime_contract",
            live_state=LIVE_STATE,
            delta_state=DELTA_STATE,
        )
        other_identity: AgentIdentity = {
            "agent_name": "NotExampleAgent",
            "agent_role": "runtime-continuity-agent",
            "lineage": "example-lineage",
            "version": "0.1",
        }

        result = run_wake_sanity_pass(snapshot, expected_identity=other_identity)

        self.assertEqual(result["resume_decision"], "restart_required")
        self.assertEqual(result["status"], "fail")
        self.assertIn("identity_mismatch", result["reasons"])

    def test_wake_downgrades_stale_handles_to_refresh(self):
        snapshot = build_sleep_snapshot(
            agent_identity=EXAMPLE_AGENT_IDENTITY,
            task_id="task_013_sleep_wake_canonical_layer",
            route_class="kernel_capability_path",
            gate_decision="allow",
            active_mode="dormant_runtime_contract",
            live_state=LIVE_STATE,
            delta_state=DELTA_STATE,
            stale_sensitive_handles=["commit:abc123", "branch:main"],
        )

        result = run_wake_sanity_pass(snapshot, expected_identity=EXAMPLE_AGENT_IDENTITY)

        self.assertEqual(result["resume_decision"], "resume_with_refresh")
        self.assertEqual(result["status"], "warn")
        self.assertIn("stale_sensitive_handles_require_refresh", result["reasons"])
        self.assertEqual(result["required_refreshes"], ["commit:abc123", "branch:main"])

    def test_wake_preserves_governance_blocks_as_read_only(self):
        snapshot = build_sleep_snapshot(
            agent_identity=EXAMPLE_AGENT_IDENTITY,
            task_id="task_013_sleep_wake_canonical_layer",
            route_class="kernel_capability_path",
            gate_decision="needs_approval",
            active_mode="dormant_runtime_contract",
            live_state=LIVE_STATE,
            delta_state=DELTA_STATE,
        )

        result = run_wake_sanity_pass(snapshot, expected_identity=EXAMPLE_AGENT_IDENTITY)

        self.assertEqual(result["resume_decision"], "resume_read_only")
        self.assertEqual(result["status"], "warn")

    def test_task_scope_mismatch_requires_clarification(self):
        snapshot = build_sleep_snapshot(
            agent_identity=EXAMPLE_AGENT_IDENTITY,
            task_id="task_013_sleep_wake_canonical_layer",
            route_class="kernel_capability_path",
            gate_decision="allow",
            active_mode="dormant_runtime_contract",
            live_state=LIVE_STATE,
            delta_state=DELTA_STATE,
        )

        result = run_wake_sanity_pass(
            snapshot,
            expected_identity=EXAMPLE_AGENT_IDENTITY,
            expected_task_id="different_task",
        )

        self.assertEqual(result["resume_decision"], "resume_with_clarification")
        self.assertIn("task_scope_mismatch", result["reasons"])

    def test_store_latest_for_task(self):
        store = InMemorySleepSnapshotStore()
        snapshot = build_sleep_snapshot(
            agent_identity=EXAMPLE_AGENT_IDENTITY,
            task_id="task_013_sleep_wake_canonical_layer",
            route_class="kernel_capability_path",
            gate_decision="allow",
            active_mode="dormant_runtime_contract",
            live_state=LIVE_STATE,
            delta_state=DELTA_STATE,
        )
        store.upsert(snapshot)

        self.assertEqual(store.get(snapshot["snapshot_id"]), snapshot)
        self.assertEqual(store.latest_for_task("task_013_sleep_wake_canonical_layer"), snapshot)


if __name__ == "__main__":
    unittest.main()
