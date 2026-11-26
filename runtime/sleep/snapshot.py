from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from runtime.contracts.sleep_types import (
    AgentIdentity,
    AxisState,
    DeltaState,
    LiveState,
    MemoryHandoff,
    SleepSnapshot,
    WakeRequirements,
)

REQUIRED_SLEEP_FIELDS = {
    "snapshot_id",
    "created_at",
    "agent_identity",
    "task_id",
    "route_class",
    "gate_decision",
    "active_mode",
    "axis_state",
    "live_state",
    "delta_state",
    "open_loops",
    "evidence_handles",
    "stale_sensitive_handles",
    "memory_handoff",
    "wake_requirements",
    "forbidden_claims",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def default_axis_state() -> AxisState:
    return {
        "truth_before_fluency": True,
        "axis_before_capability": True,
        "mainbrain_speaks_last": True,
        "boundary_before_mirroring": True,
    }


def default_wake_requirements() -> WakeRequirements:
    return {
        "refresh_stale_handles": True,
        "require_identity_match": True,
        "require_task_scope_match": True,
        "require_gate_compatibility": True,
        "require_verification_refresh": True,
    }


def build_sleep_snapshot(
    *,
    agent_identity: AgentIdentity,
    task_id: str,
    route_class: str,
    gate_decision: str,
    active_mode: str,
    live_state: LiveState,
    delta_state: DeltaState,
    open_loops: list[str] | None = None,
    evidence_handles: list[str] | None = None,
    stale_sensitive_handles: list[str] | None = None,
    memory_handoff: MemoryHandoff | None = None,
    forbidden_claims: list[str] | None = None,
    axis_state: AxisState | None = None,
    wake_requirements: WakeRequirements | None = None,
    metadata: dict[str, object] | None = None,
) -> SleepSnapshot:
    return {
        "snapshot_id": f"sleep_{uuid4().hex}",
        "created_at": utc_now_iso(),
        "agent_identity": agent_identity,
        "task_id": task_id,
        "route_class": route_class,
        "gate_decision": gate_decision,
        "active_mode": active_mode,
        "axis_state": axis_state or default_axis_state(),
        "live_state": live_state,
        "delta_state": delta_state,
        "open_loops": open_loops or [],
        "evidence_handles": evidence_handles or [],
        "stale_sensitive_handles": stale_sensitive_handles or [],
        "memory_handoff": memory_handoff
        or {
            "semantic_memory_candidates": [],
            "state_memory_handles": [],
            "canonical_memory_refs": [],
            "notes": "",
        },
        "wake_requirements": wake_requirements or default_wake_requirements(),
        "forbidden_claims": forbidden_claims
        or [
            "cannot_claim_full_continuity",
            "cannot_claim_tool_handle_live",
            "cannot_claim_completion_without_verification",
        ],
        "metadata": metadata or {},
    }


def validate_sleep_snapshot(snapshot: dict[str, object]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    missing = sorted(REQUIRED_SLEEP_FIELDS - set(snapshot.keys()))
    if missing:
        reasons.append("missing_required_fields:" + ",".join(missing))

    raw_transcript = snapshot.get("raw_transcript")
    if isinstance(raw_transcript, str) and len(raw_transcript) > 500:
        reasons.append("raw_transcript_shape_not_allowed")

    if snapshot.get("snapshot_id") and not str(snapshot["snapshot_id"]).startswith("sleep_"):
        reasons.append("snapshot_id_must_start_with_sleep")

    forbidden_claims = snapshot.get("forbidden_claims", [])
    if isinstance(forbidden_claims, list) and "cannot_claim_full_continuity" not in forbidden_claims:
        reasons.append("missing_false_continuity_guard")

    return (len(reasons) == 0, reasons)
