from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"
DEFAULT_EVENT_ID = "audit-unknown"

POLICY_DISABLED_STAGE = "policy_disabled"
POLICY_INVALID_MODE_STAGE = "policy_invalid_mode"
DRY_RUN_ROUTING_STAGE = "dry_run_routing"
DRY_RUN_ENVELOPE_PREVIEW_STAGE = "dry_run_envelope_preview"
ROUTING_STOPPED_STAGE = "routing_stopped"
BUILDER_STOPPED_STAGE = "builder_stopped"
INVOCATION_STOPPED_STAGE = "invocation_stopped"
WORKER_CANDIDATE_RETURNED_STAGE = "worker_candidate_returned"
UNKNOWN_STAGE = "unknown"

_DISABLED_MODES = {"disabled", "dry_run", "invalid_mode"}
_INVOCATION_DECISIONS = {
    "completed_candidate",
    "invocation_blocked",
    "invocation_needs_approval",
    "invocation_invalid_envelope",
}
_ROUTING_STOPPED_DECISIONS = {"no_worker_needed", "needs_approval", "blocked", "invalid_request"}
_BUILDER_STOPPED_DECISIONS = {"invalid_routing_decision", "builder_blocked"}


def _copy_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    return None


def _copy_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return []


def _mapping_decision(value: Any) -> str | None:
    if isinstance(value, Mapping):
        decision = value.get("decision")
        if decision is None:
            return None
        return str(decision)
    if value is None:
        return None
    return str(value)


def _nested_mapping(value: Any) -> dict[str, Any] | None:
    return _copy_mapping(value)


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _unwrap_bridge_result(record: Mapping[str, Any]) -> dict[str, Any]:
    root = _copy_mapping(record) or {}
    nested = root.get("bridge_result")
    if isinstance(nested, Mapping):
        bridge_result = _copy_mapping(nested) or {}
    else:
        bridge_result = root
    return {"root": root, "bridge_result": bridge_result}


def _classify_path_stage(mode: str | None, decision: str | None, builder_decision: str | None, worker_output_present: bool) -> str:
    if mode == "disabled":
        return POLICY_DISABLED_STAGE
    if decision == "invalid_mode":
        return POLICY_INVALID_MODE_STAGE
    if mode == "dry_run":
        if decision == "dry_run_ready" and builder_decision == "built_envelope":
            return DRY_RUN_ENVELOPE_PREVIEW_STAGE
        return DRY_RUN_ROUTING_STAGE
    if decision in _ROUTING_STOPPED_DECISIONS:
        return ROUTING_STOPPED_STAGE
    if decision in _BUILDER_STOPPED_DECISIONS:
        return BUILDER_STOPPED_STAGE
    if decision in _INVOCATION_DECISIONS:
        return INVOCATION_STOPPED_STAGE if decision != "completed_candidate" else WORKER_CANDIDATE_RETURNED_STAGE
    if worker_output_present:
        return WORKER_CANDIDATE_RETURNED_STAGE
    return UNKNOWN_STAGE


def _truth_claims() -> dict[str, bool]:
    return {
        "claims_truth": False,
        "claims_completion": False,
        "claims_approval": False,
        "claims_governance": False,
        "claims_side_effect_permission": False,
    }


def build_worker_bridge_audit_record(
    bridge_result: Mapping[str, Any],
    *,
    event_id: str | None = None,
    generated_at: str | None = None,
) -> dict:
    """Build a pure audit record from a worker bridge or policy result."""

    context = _unwrap_bridge_result(bridge_result)
    root = context["root"]
    bridge = context["bridge_result"]

    mode = _first_present(root.get("mode"), bridge.get("mode"))
    decision = _first_present(root.get("decision"), bridge.get("decision"))
    routing_decision = _nested_mapping(_first_present(root.get("routing_decision"), bridge.get("routing_decision")))
    builder_result = _nested_mapping(_first_present(root.get("builder_result"), bridge.get("builder_result")))
    invocation_result = _nested_mapping(_first_present(root.get("invocation_result"), bridge.get("invocation_result")))
    preflight_decision = _mapping_decision(
        _first_present(
            root.get("preflight"),
            bridge.get("preflight"),
            (invocation_result or {}).get("preflight"),
        )
    )
    worker_output = _nested_mapping(_first_present(root.get("worker_output"), bridge.get("worker_output")))

    routing_decision_text = _mapping_decision(routing_decision)
    builder_decision_text = _mapping_decision(builder_result)
    invocation_decision_text = _mapping_decision(invocation_result)
    worker_output_present = bool(worker_output)

    worker_execution_attempted = False
    if mode not in _DISABLED_MODES:
        if invocation_result is not None:
            worker_execution_attempted = True
        elif worker_output_present:
            worker_execution_attempted = True
        elif decision in _INVOCATION_DECISIONS:
            worker_execution_attempted = True

    stage = _classify_path_stage(mode, decision, builder_decision_text, worker_output_present)

    worker_id = _first_present(
        (worker_output or {}).get("worker_id"),
        bridge.get("worker_id"),
        root.get("worker_id"),
    )
    worker_type = _first_present(
        (worker_output or {}).get("worker_type"),
        bridge.get("worker_type"),
        root.get("worker_type"),
    )
    candidate_status = _first_present(
        (worker_output or {}).get("candidate_status"),
        bridge.get("candidate_status"),
        root.get("candidate_status"),
        None,
    )
    security_profile = _first_present(
        (worker_output or {}).get("security_profile"),
        bridge.get("security_profile"),
        root.get("security_profile"),
    )
    execution_surface = _first_present(
        (worker_output or {}).get("execution_surface"),
        bridge.get("execution_surface"),
        root.get("execution_surface"),
    )
    side_effect_request = _first_present(root.get("side_effect_request"), bridge.get("side_effect_request"))
    verification_needed = bool(
        _first_present(root.get("verification_needed"), bridge.get("verification_needed"), (invocation_result or {}).get("verification_needed"), False)
    )
    governance_needed = bool(
        _first_present(root.get("governance_needed"), bridge.get("governance_needed"), (invocation_result or {}).get("governance_needed"), False)
    )
    evidence_status = _first_present(
        root.get("evidence_status"),
        bridge.get("evidence_status"),
        (invocation_result or {}).get("evidence_status"),
        (worker_output or {}).get("evidence_status"),
        "not_checked",
    )
    release_eligibility = _first_present(
        root.get("release_eligibility"),
        bridge.get("release_eligibility"),
        (invocation_result or {}).get("release_eligibility"),
        (worker_output or {}).get("release_eligibility"),
        "not_eligible_pending_verification",
    )
    release_gate = _copy_mapping(
        _first_present(
            root.get("release_gate"),
            bridge.get("release_gate"),
            (invocation_result or {}).get("release_gate"),
            (worker_output or {}).get("release_gate"),
        )
    ) or {
        "eligible_for_release": False,
        "release_eligibility": release_eligibility,
        "reason": evidence_status,
    }
    claimed_evidence_count = int(_first_present(root.get("claimed_evidence_count"), bridge.get("claimed_evidence_count"), (invocation_result or {}).get("claimed_evidence_count"), (worker_output or {}).get("claimed_evidence_count"), 0) or 0)
    verified_evidence_count = int(_first_present(root.get("verified_evidence_count"), bridge.get("verified_evidence_count"), (invocation_result or {}).get("verified_evidence_count"), (worker_output or {}).get("verified_evidence_count"), 0) or 0)
    verified_by = _first_present(root.get("verified_by"), bridge.get("verified_by"), (invocation_result or {}).get("verified_by"), (worker_output or {}).get("verified_by"))
    limitations_source = _first_present(root.get("limitations"), bridge.get("limitations"), (invocation_result or {}).get("limitations"), (builder_result or {}).get("limitations"), (routing_decision or {}).get("limitations"), (worker_output or {}).get("limitations"))
    limitations = _copy_list(limitations_source)
    record = {
        "event_id": event_id or _first_present(root.get("event_id"), bridge.get("event_id"), DEFAULT_EVENT_ID),
        "task_id": _first_present(root.get("task_id"), bridge.get("task_id")),
        "mode": mode,
        "decision": decision,
        "path_stage": stage,
        "worker_execution_attempted": worker_execution_attempted,
        "worker_output_present": worker_output_present,
        "worker_id": worker_id,
        "worker_type": worker_type,
        "security_profile": security_profile,
        "execution_surface": execution_surface,
        "routing_decision": routing_decision_text,
        "builder_decision": builder_decision_text,
        "invocation_decision": invocation_decision_text,
        "preflight_decision": preflight_decision,
        "candidate_status": candidate_status,
        "side_effect_request": side_effect_request,
        "verification_needed": verification_needed,
        "governance_needed": governance_needed,
        "evidence_status": evidence_status,
        "release_eligibility": release_eligibility,
        "release_gate": release_gate,
        "claimed_evidence_count": claimed_evidence_count,
        "verified_evidence_count": verified_evidence_count,
        "verified_by": verified_by,
        "limitations": limitations,
        "authority_claims": _truth_claims(),
        "generated_at": generated_at or _first_present(root.get("generated_at"), bridge.get("generated_at"), DEFAULT_GENERATED_AT),
    }
    return record


__all__ = ["build_worker_bridge_audit_record"]
