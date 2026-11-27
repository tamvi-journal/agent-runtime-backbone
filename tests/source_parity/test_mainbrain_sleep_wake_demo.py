import unittest

from runtime.contracts.sleep_types import AgentIdentity, DeltaState, LiveState
from runtime.sleep.snapshot import build_sleep_snapshot

from runtime.mainbrain.continuity_demo import consume_wake_decision, resume_from_snapshot

AGENT_IDENTITY: AgentIdentity = {
    "agent_name": "Agent",
    "agent_role": "runtime-continuity-agent",
    "lineage": "example-lineage",
    "version": "0.1",
}

LIVE_STATE: LiveState = {
    "coherence": 0.82,
    "uncertainty": 0.21,
    "level": "low",
    "verification_status": "verified",
    "current_focus": "task 015 demo",
}

DELTA_STATE: DeltaState = {
    "changed_since_last_snapshot": ["task 015 demo created"],
    "last_success": "task 016 merged",
    "last_failure": None,
    "last_blocker": None,
    "next_safe_action": "run wake sanity pass",
}


class MainBrainSleepWakeDemoTest(unittest.TestCase):
    def _snapshot(self, **kwargs):
        base = dict(
            agent_identity=AGENT_IDENTITY,
            task_id="task_015_sleep_wake_mainbrain_integration_demo",
            route_class="kernel_capability_path",
            gate_decision="allow",
            active_mode="demo_runtime_restart",
            live_state=LIVE_STATE,
            delta_state=DELTA_STATE,
        )
        base.update(kwargs)
        return build_sleep_snapshot(**base)

    def test_restart_flow_requires_wake_sanity_before_resume(self):
        snapshot = self._snapshot()
        result = resume_from_snapshot(snapshot, expected_identity=AGENT_IDENTITY, expected_task_id=snapshot["task_id"])

        self.assertEqual(result["resume_mode"], "resume_full")
        self.assertEqual(result["message"], "resume allowed under current wake checks")

    def test_mainbrain_consumes_wake_decision_not_snapshot_claim(self):
        snapshot = self._snapshot()
        result = resume_from_snapshot(snapshot, expected_identity=AGENT_IDENTITY, expected_task_id=snapshot["task_id"])

        self.assertNotIn("continuity proven", result["message"].lower())
        self.assertEqual(result["snapshot_id"], snapshot["snapshot_id"])

    def test_mainbrain_blocks_resume_without_wake_result(self):
        result = consume_wake_decision(None)

        self.assertEqual(result["resume_mode"], "restart_required")
        self.assertEqual(result["required_action"], "wake sanity required before continuing")
        self.assertEqual(result["message"], "wake sanity required before continuing")

    def test_mainbrain_rejects_full_continuity_claim_even_on_resume_full(self):
        snapshot = self._snapshot()
        result = resume_from_snapshot(snapshot, expected_identity=AGENT_IDENTITY, expected_task_id=snapshot["task_id"])

        self.assertEqual(result["message"], "resume allowed under current wake checks")
        self.assertNotEqual(result["message"], "continuity proven")

    def test_identity_mismatch_forces_restart_required(self):
        snapshot = self._snapshot()
        other_identity: AgentIdentity = {
            "agent_name": "Other",
            "agent_role": "runtime-continuity-agent",
            "lineage": "example-lineage",
            "version": "0.1",
        }

        result = resume_from_snapshot(snapshot, expected_identity=other_identity, expected_task_id=snapshot["task_id"])

        self.assertEqual(result["resume_mode"], "restart_required")
        self.assertIn("identity_mismatch", result["reasons"])

    def test_stale_handles_force_resume_with_refresh(self):
        snapshot = self._snapshot(stale_sensitive_handles=["commit:abc123"])
        result = resume_from_snapshot(snapshot, expected_identity=AGENT_IDENTITY, expected_task_id=snapshot["task_id"])

        self.assertEqual(result["resume_mode"], "resume_with_refresh")
        self.assertEqual(result["required_action"], "refresh required before continuing")

    def test_needs_approval_or_sandbox_only_becomes_resume_read_only(self):
        snapshot = self._snapshot(gate_decision="needs_approval")
        result = resume_from_snapshot(snapshot, expected_identity=AGENT_IDENTITY, expected_task_id=snapshot["task_id"])

        self.assertEqual(result["resume_mode"], "resume_read_only")
        self.assertEqual(result["required_action"], "read-only resume only")

    def test_task_scope_mismatch_requires_clarification(self):
        snapshot = self._snapshot()
        result = resume_from_snapshot(snapshot, expected_identity=AGENT_IDENTITY, expected_task_id="different_task")

        self.assertEqual(result["resume_mode"], "resume_with_clarification")
        self.assertEqual(result["required_action"], "clarification required before continuing")

    def test_mainbrain_returns_restart_mode_when_wake_fails(self):
        result = consume_wake_decision({
            "resume_decision": "restart_required",
            "status": "fail",
            "reasons": ["identity_mismatch"],
            "required_refreshes": [],
            "held_claims": ["cannot_claim_full_continuity"],
            "confidence": 0.3,
        })

        self.assertEqual(result["resume_mode"], "restart_required")
        self.assertEqual(result["required_action"], "restart required before continuing")
        self.assertEqual(result["message"], "restart required before continuing")
        self.assertIn("cannot_claim_full_continuity", result["held_claims"])

    def test_mainbrain_returns_read_only_mode_when_wake_warns_needs_approval(self):
        result = consume_wake_decision({
            "resume_decision": "resume_read_only",
            "status": "warn",
            "reasons": ["approval_required"],
            "required_refreshes": [],
            "held_claims": ["cannot_claim_full_continuity"],
            "confidence": 0.68,
        })

        self.assertEqual(result["resume_mode"], "resume_read_only")
        self.assertEqual(result["required_action"], "read-only resume only")

    def test_mainbrain_carries_held_claims_forward_as_blocked_claims(self):
        result = consume_wake_decision({
            "resume_decision": "resume_with_refresh",
            "status": "warn",
            "reasons": ["stale_sensitive_handles_require_refresh"],
            "required_refreshes": ["commit:abc123"],
            "held_claims": ["cannot_claim_full_continuity"],
            "confidence": 0.68,
        })

        self.assertEqual(result["held_claims"], ["cannot_claim_full_continuity"])


if __name__ == "__main__":
    unittest.main()
