from __future__ import annotations

from runtime.allocator.contracts import EffortAllocatorGovernanceDecision, EffortAllocatorThresholdReviewRequest, FailureMode
from runtime.allocator.effort_allocator import evaluate_threshold_tuning_request

APPROVED_FAILURE_MODES = set(FailureMode.__args__)


def review_threshold_request(request: EffortAllocatorThresholdReviewRequest) -> EffortAllocatorGovernanceDecision:
    reasons: list[str] = []

    if not request["failure_distribution_available"]:
        reasons.append("failure_distribution_missing")
    if request["sample_size"] < request["project_minimum_sample_size"]:
        reasons.append("sample_too_small")
    if not request["repeated_failure_pattern"]:
        reasons.append("repeated_failure_pattern_missing")
    if not request["supporting_failure_modes"]:
        reasons.append("supporting_failure_modes_missing")
    for failure_mode in request["supporting_failure_modes"]:
        if failure_mode not in APPROVED_FAILURE_MODES:
            reasons.append(f"unknown_supporting_failure_mode:{failure_mode}")
    if not request["tradeoff_note"].strip():
        reasons.append("tradeoff_note_missing")
    if not request["rollback_path"].strip():
        reasons.append("rollback_path_missing")

    guard_result = evaluate_threshold_tuning_request(
        {
            "reason": request["tradeoff_note"],
            "compute_pressure_only": request["compute_pressure_only"],
            "failure_distribution_available": request["failure_distribution_available"],
            "observed_failure_modes": list(request["supporting_failure_modes"]),
        }
    )
    reasons.extend(reason for reason in guard_result["reasons"] if reason not in reasons)

    decision = "approved" if not reasons else "rejected"

    return {
        "event": "effort_allocator.governance_decision",
        "window_id": request["window_id"],
        "decision": decision,
        "requested_change": (
            f"{request['requested_change']['field']} "
            f"{request['requested_change']['current']} -> {request['requested_change']['proposed']}"
        ),
        "reasons": reasons,
        "execution_status": "not_applied_phase_02",
        "tradeoff_note": request["tradeoff_note"],
        "rollback_path": request["rollback_path"],
    }
