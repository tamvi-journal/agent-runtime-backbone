from __future__ import annotations

from runtime.allocator.contracts import (
    EffortAllocatorDecision,
    EffortAllocatorDistributionSummary,
    EffortAllocatorGovernanceDecision,
    EffortAllocatorOutcomeRecord,
    EffortAllocatorRequest,
    EffortAllocatorTelemetryEvent,
    EffortAllocatorThresholdReviewRequest,
)


def build_effort_allocator_event(
    request: EffortAllocatorRequest,
    decision: EffortAllocatorDecision,
) -> EffortAllocatorTelemetryEvent:
    return {
        "event": "effort_allocator.route",
        "task_type": request["task_type"],
        "active_mode": request["active_mode"],
        "ambiguity_score": request["ambiguity_score"],
        "risk_score": request["risk_score"],
        "stakes_signal": request["stakes_signal"],
        "action_required": request["action_required"],
        "memory_commit_possible": request["memory_commit_possible"],
        "disagreement_likelihood": request["disagreement_likelihood"],
        "cue_strength": request["cue_strength"],
        "effort_score": decision["effort_score"],
        "effort_level": decision["effort_level"],
        "cognition_topology": decision["cognition_topology"],
        "monitor_intensity": decision["monitor_intensity"],
        "verification_requirement": decision["verification_requirement"],
        "memory_commit_status": decision["memory_commit_status"],
        "reasoning_engine": decision["reasoning_engine"],
        "allocator_reason": decision["allocator_reason"],
    }


def build_effort_allocator_outcome_event(
    turn_id: str,
    session_id: str,
    decision: EffortAllocatorDecision,
    observed_outcome: dict,
) -> EffortAllocatorOutcomeRecord:
    return {
        "event": "effort_allocator.outcome",
        "turn_id": turn_id,
        "session_id": session_id,
        "task_type": decision["task_type"],
        "active_mode": decision["active_mode"],
        "effort_score": decision["effort_score"],
        "effort_level": decision["effort_level"],
        "cognition_topology": decision["cognition_topology"],
        "verification_requirement": decision["verification_requirement"],
        "allocator_reason": decision["allocator_reason"],
        "observed_outcome": observed_outcome["observed_outcome"],
        "failure_modes": list(observed_outcome["failure_modes"]),
        "meaningful_error": observed_outcome["meaningful_error"],
        "wasted_effort": observed_outcome["wasted_effort"],
        "human_correction_required": observed_outcome["human_correction_required"],
        "completion_reversal": observed_outcome["completion_reversal"],
        "memory_error": observed_outcome["memory_error"],
        "recognition_degradation": observed_outcome["recognition_degradation"],
        "label_confidence": observed_outcome["label_confidence"],
        "notes": observed_outcome.get("notes", ""),
    }


def build_effort_allocator_distribution_summary_event(
    window_id: str,
    sample_size: int,
    failure_counts: dict[str, int],
    by_effort_level: dict[str, int],
    notes: str = "",
) -> EffortAllocatorDistributionSummary:
    return {
        "event": "effort_allocator.distribution_summary",
        "window_id": window_id,
        "sample_size": sample_size,
        "failure_counts": dict(failure_counts),
        "by_effort_level": dict(by_effort_level),
        "notes": notes,
    }


def build_effort_allocator_threshold_review_request_event(
    request: EffortAllocatorThresholdReviewRequest,
) -> EffortAllocatorThresholdReviewRequest:
    return dict(request)


def build_governance_decision_event(
    decision: EffortAllocatorGovernanceDecision,
) -> EffortAllocatorGovernanceDecision:
    return dict(decision)
