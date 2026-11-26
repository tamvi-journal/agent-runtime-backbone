from __future__ import annotations

from runtime.allocator.contracts import (
    EffortAllocatorDecision,
    EffortAllocatorRequest,
    ThresholdTuningDecision,
    ThresholdTuningRequest,
)

HIGH_SIGNAL = 0.70
DISAGREEMENT_SIGNAL = 0.60
LOW_MODE_CONFIDENCE = 0.50

HEAVY_TASK_TYPES = {"architecture", "execution", "research", "verify"}
LIGHT_TASK_TYPES = {"rewrite", "formatting", "small_talk"}
FAILURE_DISTRIBUTION_MIN = 1


def allocate_effort(request: EffortAllocatorRequest) -> EffortAllocatorDecision:
    score = 0
    reasons: list[str] = []

    if request["task_type"] in HEAVY_TASK_TYPES:
        score += 2
        reasons.append(f"task_type:{request['task_type']}")
    if request["ambiguity_score"] >= HIGH_SIGNAL:
        score += 2
        reasons.append("ambiguity_high")
    if request["risk_score"] >= HIGH_SIGNAL:
        score += 2
        reasons.append("risk_high")
    if request["stakes_signal"] >= HIGH_SIGNAL:
        score += 2
        reasons.append("stakes_high")
    if request["action_required"]:
        score += 2
        reasons.append("action_required")
    if request["memory_commit_possible"]:
        score += 2
        reasons.append("memory_commit_possible")
    if request["disagreement_likelihood"] >= DISAGREEMENT_SIGNAL:
        score += 2
        reasons.append("disagreement_likely")
    if request["mode_confidence"] < LOW_MODE_CONFIDENCE:
        score += 1
        reasons.append("mode_confidence_low")
    if request["verification_gap_estimate"] >= HIGH_SIGNAL:
        score += 1
        reasons.append("verification_gap_high")
    if request["high_risk_domain"]:
        score += 2
        reasons.append("high_risk_domain")
    if request["unanswerable_likelihood"] >= DISAGREEMENT_SIGNAL:
        score += 1
        reasons.append("unanswerable_likely")
    if request["cue_strength"] >= 0.75:
        score -= 2
        reasons.append("cue_strength_strong")
    if request["task_type"] in LIGHT_TASK_TYPES:
        score -= 2
        reasons.append(f"task_type_light:{request['task_type']}")

    effort_level = _select_effort_level(score)
    cognition_topology = _select_cognition_topology(score)
    monitor_intensity = _select_monitor_intensity(score)
    verification_requirement = _select_verification_requirement(request, score)
    reasoning_engine = _select_reasoning_engine(score)
    memory_commit_status = "possible" if request["memory_commit_possible"] else "not_possible"

    return {
        "task_type": request["task_type"],
        "active_mode": request["active_mode"],
        "ambiguity_score": request["ambiguity_score"],
        "risk_score": request["risk_score"],
        "stakes_signal": request["stakes_signal"],
        "effort_score": score,
        "effort_level": effort_level,
        "cognition_topology": cognition_topology,
        "monitor_intensity": monitor_intensity,
        "verification_requirement": verification_requirement,
        "memory_commit_status": memory_commit_status,
        "reasoning_engine": reasoning_engine,
        "allocator_reason": ", ".join(reasons) if reasons else "baseline_low_context",
        "advisory_only": True,
        "permission_claimed": False,
        "completion_claimed": False,
        "permission_decision": "none",
        "completion_status": "not_applicable",
    }


def evaluate_threshold_tuning_request(request: ThresholdTuningRequest) -> ThresholdTuningDecision:
    reasons: list[str] = []
    if request["compute_pressure_only"]:
        reasons.append("compute_pressure_only")
    if not request["failure_distribution_available"] or len(request["observed_failure_modes"]) < FAILURE_DISTRIBUTION_MIN:
        reasons.append("failure_distribution_missing")

    tuning_allowed = not reasons
    message = (
        "threshold tuning allowed because a failure distribution exists and the request is not compute-pressure-only"
        if tuning_allowed
        else "threshold tuning blocked until routing errors are observed beyond compute pressure alone"
    )

    return {
        "tuning_allowed": tuning_allowed,
        "reasons": reasons,
        "message": message,
    }


def _select_effort_level(score: int) -> str:
    if score >= 8:
        return "max"
    if score >= 5:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def _select_cognition_topology(score: int) -> str:
    if score >= 8:
        return "deep_review"
    if score >= 5:
        return "dual_pass"
    if score >= 2:
        return "structured_single_pass"
    return "single_pass"


def _select_monitor_intensity(score: int) -> str:
    if score >= 8:
        return "strict"
    if score >= 5:
        return "elevated"
    if score >= 2:
        return "standard"
    return "light"


def _select_verification_requirement(request: EffortAllocatorRequest, score: int) -> str:
    if request["action_required"] or request["risk_score"] >= HIGH_SIGNAL or request["high_risk_domain"]:
        return "required"
    if score >= 2 or request["verification_gap_estimate"] >= HIGH_SIGNAL:
        return "recommended"
    return "light"


def _select_reasoning_engine(score: int) -> str:
    if score >= 8:
        return "deep_deliberation"
    if score >= 5:
        return "dual_pass"
    if score >= 2:
        return "deliberate"
    return "fast_path"
