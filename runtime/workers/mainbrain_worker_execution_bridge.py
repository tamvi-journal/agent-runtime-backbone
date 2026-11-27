from __future__ import annotations

"""MainBrain Worker Execution Bridge runtime helper.

The execution bridge connects approved local helper steps; it does not create
new authority.
Execution bridge may orchestrate routing → envelope building → controlled
invocation, but output remains candidate evidence only.
"""

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.workers.controlled_invocation import invoke_worker_with_envelope
from runtime.workers.mainbrain_worker_routing import route_mainbrain_worker_request
from runtime.workers.routing_decision_to_envelope import (
    build_worker_invocation_envelope_from_routing_decision,
)

SUPPORTED_BRIDGE_DECISIONS = {
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


def _bridge_base(
    *,
    request: Mapping[str, Any],
    routing_decision: Mapping[str, Any] | None,
    decision: str,
    candidate_status: str = "not_applicable",
    builder_result: Mapping[str, Any] | None = None,
    invocation_result: Mapping[str, Any] | None = None,
    worker_output: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    request_data = _copy_mapping(request) or {}
    bridge_result: dict[str, Any] = {
        "task_id": request_data.get("task_id") or (routing_decision or {}).get("task_id"),
        "decision": decision,
        "routing_decision": _copy_mapping(routing_decision) if routing_decision is not None else None,
        "candidate_status": candidate_status,
        "side_effect_request": None,
        "verification_needed": bool((invocation_result or {}).get("verification_needed", False)),
        "governance_needed": bool((invocation_result or {}).get("governance_needed", False)),
        "evidence_status": (invocation_result or {}).get("evidence_status", "not_checked"),
        "release_eligibility": (invocation_result or {}).get("release_eligibility", "not_eligible_pending_verification"),
        "release_gate": _copy_mapping((invocation_result or {}).get("release_gate")) or {
            "eligible_for_release": False,
            "release_eligibility": "not_eligible_pending_verification",
            "reason": "worker_not_executed",
        },
        "claimed_evidence_count": int((invocation_result or {}).get("claimed_evidence_count", 0) or 0),
        "verified_evidence_count": int((invocation_result or {}).get("verified_evidence_count", 0) or 0),
        "verified_by": (invocation_result or {}).get("verified_by"),
        "limitations": _copy_list(
            (invocation_result or builder_result or routing_decision or {}).get("limitations", [])
        ),
        "generated_at": generated_at
        or (invocation_result or builder_result or routing_decision or {}).get("generated_at")
        or _utc_now(),
    }
    if builder_result is not None:
        bridge_result["builder_result"] = _copy_mapping(builder_result)
    if invocation_result is not None:
        bridge_result["invocation_result"] = _copy_mapping(invocation_result)
    if worker_output is not None:
        bridge_result["worker_output"] = _copy_mapping(worker_output)
    return bridge_result


def _map_invocation_decision(decision: str) -> str:
    if decision == "completed_candidate":
        return "completed_candidate"
    if decision in {"block", "blocked"}:
        return "invocation_blocked"
    if decision == "needs_approval":
        return "invocation_needs_approval"
    if decision == "invalid_envelope":
        return "invocation_invalid_envelope"
    return "invocation_blocked"


def run_mainbrain_worker_execution_bridge(
    request: Mapping[str, Any],
    repo_root: str | Path,
    *,
    requested_by: str = "MainBrain",
    invocation_id: str | None = None,
    created_at: str | None = None,
) -> dict:
    """Run the approved MainBrain → builder → controlled invocation bridge."""

    request_copy = _copy_mapping(request) or {}
    routing_decision = route_mainbrain_worker_request(request_copy)
    route_decision = routing_decision.get("decision")

    if route_decision != ROUTE_DECISION:
        return _bridge_base(
            request=request_copy,
            routing_decision=routing_decision,
            decision=route_decision,
            candidate_status="not_applicable",
        )

    builder_result = build_worker_invocation_envelope_from_routing_decision(
        routing_decision,
        requested_by=requested_by,
        invocation_id=invocation_id,
        created_at=created_at,
    )
    builder_decision = builder_result.get("decision")
    if builder_decision != BUILT_ENVELOPE:
        decision = "invalid_routing_decision" if builder_decision == "invalid_routing_decision" else "builder_blocked"
        return _bridge_base(
            request=request_copy,
            routing_decision=routing_decision,
            decision=decision,
            candidate_status="not_applicable",
            builder_result=builder_result,
        )

    invocation_result = invoke_worker_with_envelope(builder_result["envelope"], repo_root)
    invocation_decision = _map_invocation_decision(str(invocation_result.get("decision")))
    if invocation_decision != COMPLETED_CANDIDATE:
        return _bridge_base(
            request=request_copy,
            routing_decision=routing_decision,
            decision=invocation_decision,
            candidate_status=_copy_mapping(invocation_result).get("candidate_status", "not_applicable") if _copy_mapping(invocation_result) else "not_applicable",
            builder_result=builder_result,
            invocation_result=invocation_result,
        )

    worker_output = invocation_result.get("worker_output")
    return _bridge_base(
        request=request_copy,
        routing_decision=routing_decision,
        decision=COMPLETED_CANDIDATE,
        candidate_status=(worker_output or {}).get("candidate_status", "candidate"),
        builder_result=builder_result,
        invocation_result=invocation_result,
        worker_output=worker_output,
        generated_at=(worker_output or invocation_result).get("generated_at") if isinstance(worker_output or invocation_result, Mapping) else None,
    )


__all__ = ["run_mainbrain_worker_execution_bridge", "SUPPORTED_BRIDGE_DECISIONS"]
