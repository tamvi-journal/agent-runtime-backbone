from __future__ import annotations

from runtime.contracts.sleep_types import AgentIdentity, SleepSnapshot, WakeSanityResult
from runtime.sleep.decisions import build_wake_result, decide_resume_level
from runtime.sleep.snapshot import validate_sleep_snapshot


def identity_matches(snapshot_identity: AgentIdentity, expected_identity: AgentIdentity | None) -> bool:
    if expected_identity is None:
        return True
    for key in ("agent_name", "agent_role", "lineage"):
        if snapshot_identity.get(key) != expected_identity.get(key):
            return False
    return True


def task_scope_matches(snapshot: SleepSnapshot, expected_task_id: str | None) -> bool:
    if expected_task_id is None:
        return True
    return snapshot["task_id"] == expected_task_id


def stale_handles_requiring_refresh(snapshot: SleepSnapshot) -> list[str]:
    if snapshot["wake_requirements"].get("refresh_stale_handles", True):
        return list(snapshot.get("stale_sensitive_handles", []))
    return []


def run_wake_sanity_pass(
    snapshot: SleepSnapshot,
    *,
    expected_identity: AgentIdentity | None = None,
    expected_task_id: str | None = None,
) -> WakeSanityResult:
    reasons: list[str] = []
    required_refreshes: list[str] = []

    snapshot_ok, snapshot_reasons = validate_sleep_snapshot(dict(snapshot))
    if not snapshot_ok:
        reasons.extend(snapshot_reasons)

    identity_ok = identity_matches(snapshot["agent_identity"], expected_identity)
    if not identity_ok:
        reasons.append("identity_mismatch")

    scope_ok = task_scope_matches(snapshot, expected_task_id)
    if not scope_ok:
        reasons.append("task_scope_mismatch")

    required_refreshes = stale_handles_requiring_refresh(snapshot)
    if required_refreshes:
        reasons.append("stale_sensitive_handles_require_refresh")

    gate_decision = snapshot.get("gate_decision", "sandbox_only")
    verification_status = snapshot["live_state"].get("verification_status", "unverified")

    resume_decision = decide_resume_level(
        identity_ok=identity_ok,
        snapshot_ok=snapshot_ok,
        task_scope_ok=scope_ok,
        stale_handles=required_refreshes,
        gate_decision=gate_decision,
        verification_status=verification_status,
    )

    confidence = 0.92
    if resume_decision == "restart_required":
        confidence = 0.35
    elif resume_decision != "resume_full":
        confidence = 0.68

    return build_wake_result(
        resume_decision=resume_decision,
        reasons=reasons,
        required_refreshes=required_refreshes,
        held_claims=list(snapshot.get("forbidden_claims", [])),
        confidence=confidence,
    )
