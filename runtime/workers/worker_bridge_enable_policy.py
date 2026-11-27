from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.workers.mainbrain_worker_execution_bridge import run_mainbrain_worker_execution_bridge
from runtime.workers.mainbrain_worker_routing import route_mainbrain_worker_request
from runtime.workers.routing_decision_to_envelope import build_worker_invocation_envelope_from_routing_decision

SUPPORTED_POLICY_MODES = {"disabled", "dry_run", "enabled_read_only"}
SUPPORTED_POLICY_DECISIONS = {
    "disabled",
    "invalid_mode",
    "dry_run_ready",
    "dry_run_no_worker_needed",
    "dry_run_needs_approval",
    "dry_run_blocked",
    "dry_run_invalid_request",
    "dry_run_invalid_routing_decision",
    "dry_run_builder_blocked",
    "completed_candidate",
    "no_worker_needed",
    "needs_approval",
    "blocked",
    "invalid_request",
    "invalid_routing_decision",
    "builder_blocked",
    "invocation_blocked",
    "invocation_needs_approval",
    "invocation_invalid_envelope",
}

DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"
ROUTE_DECISION = "route_repo_research_worker"
BUILT_ENVELOPE = "built_envelope"
COMPLETED_CANDIDATE = "completed_candidate"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _policy_base(
    *,
    request: Mapping[str, Any],
    mode: str,
    decision: str,
    routing_decision: Mapping[str, Any] | None = None,
    builder_result: Mapping[str, Any] | None = None,
    bridge_result: Mapping[str, Any] | None = None,
    invocation_result: Mapping[str, Any] | None = None,
    worker_output: Mapping[str, Any] | None = None,
    candidate_status: str = "not_applicable",
    generated_at: str | None = None,
) -> dict[str, Any]:
    request_data = _copy_mapping(request) or {}
    policy_result: dict[str, Any] = {
        "task_id": request_data.get("task_id") or (bridge_result or routing_decision or builder_result or {}).get("task_id"),
        "mode": mode,
        "decision": decision,
        "routing_decision": _copy_mapping(routing_decision) if routing_decision is not None else None,
        "builder_result": _copy_mapping(builder_result) if builder_result is not None else None,
        "bridge_result": _copy_mapping(bridge_result) if bridge_result is not None else None,
        "invocation_result": _copy_mapping(invocation_result) if invocation_result is not None else None,
        "candidate_status": candidate_status,
        "side_effect_request": None,
        "verification_needed": bool((bridge_result or invocation_result or {}).get("verification_needed", False)),
        "governance_needed": bool((bridge_result or invocation_result or {}).get("governance_needed", False)),
        "evidence_status": (bridge_result or invocation_result or {}).get("evidence_status", "not_checked"),
        "release_eligibility": (bridge_result or invocation_result or {}).get("release_eligibility", "not_eligible_pending_verification"),
        "release_gate": _copy_mapping((bridge_result or invocation_result or {}).get("release_gate")) or {
            "eligible_for_release": False,
            "release_eligibility": "not_eligible_pending_verification",
            "reason": "worker_not_executed",
        },
        "claimed_evidence_count": int((bridge_result or invocation_result or {}).get("claimed_evidence_count", 0) or 0),
        "verified_evidence_count": int((bridge_result or invocation_result or {}).get("verified_evidence_count", 0) or 0),
        "verified_by": (bridge_result or invocation_result or {}).get("verified_by"),
        "limitations": _copy_list((bridge_result or invocation_result or builder_result or routing_decision or {}).get("limitations", [])),
        "generated_at": generated_at or (bridge_result or invocation_result or builder_result or routing_decision or {}).get("generated_at") or _utc_now(),
    }
    if worker_output is not None:
        policy_result["worker_output"] = _copy_mapping(worker_output)
    return policy_result


def _dry_run_decision(route_decision: str, builder_decision: str | None = None) -> str:
    if route_decision == ROUTE_DECISION:
        if builder_decision == BUILT_ENVELOPE:
            return "dry_run_ready"
        if builder_decision == "invalid_routing_decision":
            return "dry_run_invalid_routing_decision"
        if builder_decision == "blocked":
            return "dry_run_builder_blocked"
        return "dry_run_builder_blocked"
    if route_decision == "no_worker_needed":
        return "dry_run_no_worker_needed"
    if route_decision == "needs_approval":
        return "dry_run_needs_approval"
    if route_decision == "blocked":
        return "dry_run_blocked"
    if route_decision == "invalid_request":
        return "dry_run_invalid_request"
    return "dry_run_invalid_routing_decision"


def run_worker_bridge_with_policy(
    request: Mapping[str, Any],
    repo_root: str | Path,
    *,
    mode: str = "disabled",
    requested_by: str = "MainBrain",
    invocation_id: str | None = None,
    created_at: str | None = None,
) -> dict:
    """Run the Worker Bridge Enable Policy wrapper."""

    request_copy = _copy_mapping(request) or {}
    if mode not in SUPPORTED_POLICY_MODES:
        return _policy_base(request=request_copy, mode=mode, decision="invalid_mode")

    if mode == "disabled":
        return _policy_base(request=request_copy, mode=mode, decision="disabled")

    routing_decision = route_mainbrain_worker_request(request_copy)
    route_decision = routing_decision.get("decision")

    if mode == "dry_run":
        builder_result = None
        builder_decision = None
        if route_decision == ROUTE_DECISION:
            builder_result = build_worker_invocation_envelope_from_routing_decision(
                routing_decision,
                requested_by=requested_by,
                invocation_id=invocation_id,
                created_at=created_at,
            )
            builder_decision = builder_result.get("decision")
        decision = _dry_run_decision(str(route_decision), str(builder_decision) if builder_decision is not None else None)
        candidate_status = "not_applicable"
        if decision == "dry_run_ready":
            candidate_status = "preview_only"
        return _policy_base(
            request=request_copy,
            mode=mode,
            decision=decision,
            routing_decision=routing_decision,
            builder_result=builder_result,
            candidate_status=candidate_status,
        )

    bridge_result = run_mainbrain_worker_execution_bridge(
        request_copy,
        repo_root,
        requested_by=requested_by,
        invocation_id=invocation_id,
        created_at=created_at,
    )
    decision = str(bridge_result.get("decision", "invalid_request"))
    worker_output = bridge_result.get("worker_output")
    return _policy_base(
        request=request_copy,
        mode=mode,
        decision=decision,
        routing_decision=bridge_result.get("routing_decision"),
        builder_result=bridge_result.get("builder_result"),
        bridge_result=bridge_result,
        invocation_result=bridge_result.get("invocation_result"),
        worker_output=worker_output,
        candidate_status=str(bridge_result.get("candidate_status", "not_applicable")),
        generated_at=str(bridge_result.get("generated_at") or DEFAULT_GENERATED_AT),
    )


__all__ = ["run_worker_bridge_with_policy", "SUPPORTED_POLICY_MODES", "SUPPORTED_POLICY_DECISIONS"]
