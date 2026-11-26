from __future__ import annotations

from runtime.allocator.contracts import EffortAllocatorDecision, EffortAllocatorEvaluatorLabel, FailureMode

APPROVED_FAILURE_MODES = set(FailureMode.__args__)


def evaluate_allocator_outcome(
    decision: EffortAllocatorDecision,
    observed_outcome: EffortAllocatorEvaluatorLabel,
) -> EffortAllocatorEvaluatorLabel:
    failure_modes = _normalize_failure_modes(observed_outcome, decision)
    label_confidence = observed_outcome.get("label_confidence", 0.5)

    return {
        "observed_outcome": observed_outcome["observed_outcome"],
        "failure_modes": failure_modes,
        "meaningful_error": observed_outcome["meaningful_error"],
        "wasted_effort": observed_outcome["wasted_effort"],
        "human_correction_required": observed_outcome["human_correction_required"],
        "completion_reversal": observed_outcome["completion_reversal"],
        "memory_error": observed_outcome["memory_error"],
        "recognition_degradation": observed_outcome["recognition_degradation"],
        "label_confidence": label_confidence,
        "notes": observed_outcome.get("notes", ""),
    }


def _normalize_failure_modes(
    observed_outcome: EffortAllocatorEvaluatorLabel,
    decision: EffortAllocatorDecision,
) -> list[str]:
    normalized = [
        failure_mode
        for failure_mode in observed_outcome.get("failure_modes", [])
        if failure_mode in APPROVED_FAILURE_MODES
    ]

    if observed_outcome["meaningful_error"] and decision["effort_level"] == "low" and "misrouted_low_effort" not in normalized:
        normalized.append("misrouted_low_effort")
    if observed_outcome["recognition_degradation"] and "recognition_flattening" not in normalized:
        normalized.append("recognition_flattening")
    if observed_outcome["memory_error"] and "memory_commit_mistake" not in normalized:
        normalized.append("memory_commit_mistake")
    if observed_outcome["completion_reversal"] and "false_completion" not in normalized:
        normalized.append("false_completion")
    if observed_outcome["wasted_effort"] and decision["effort_level"] in {"high", "max"} and "compute_without_gain" not in normalized:
        normalized.append("compute_without_gain")

    return normalized
