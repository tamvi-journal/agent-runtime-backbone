from __future__ import annotations

from typing import Literal, TypedDict

TaskType = Literal[
    "architecture",
    "execution",
    "research",
    "verify",
    "analysis",
    "rewrite",
    "formatting",
    "small_talk",
]
EffortLevel = Literal["low", "medium", "high", "max"]
CognitionTopology = Literal["single_pass", "structured_single_pass", "dual_pass", "deep_review"]
MonitorIntensity = Literal["light", "standard", "elevated", "strict"]
VerificationRequirement = Literal["light", "recommended", "required"]
ReasoningEngine = Literal["fast_path", "deliberate", "dual_pass", "deep_deliberation"]
FailureMode = Literal[
    "false_completion",
    "missed_ambiguity_case",
    "misrouted_low_effort",
    "unnecessary_high_effort",
    "disagreement_suppression",
    "stakes_underrated",
    "verification_underrouted",
    "memory_commit_mistake",
    "recognition_flattening",
    "compute_without_gain",
]
GovernanceDecision = Literal["approved", "rejected"]
ExecutionStatus = Literal["not_applied_phase_02"]


class EffortAllocatorRequest(TypedDict):
    task_type: str
    active_mode: str
    ambiguity_score: float
    risk_score: float
    stakes_signal: float
    action_required: bool
    memory_commit_possible: bool
    disagreement_likelihood: float
    mode_confidence: float
    verification_gap_estimate: float
    high_risk_domain: bool
    unanswerable_likelihood: float
    cue_strength: float


class EffortAllocatorDecision(TypedDict):
    task_type: str
    active_mode: str
    ambiguity_score: float
    risk_score: float
    stakes_signal: float
    effort_score: int
    effort_level: EffortLevel | str
    cognition_topology: CognitionTopology | str
    monitor_intensity: MonitorIntensity | str
    verification_requirement: VerificationRequirement | str
    memory_commit_status: str
    reasoning_engine: ReasoningEngine | str
    allocator_reason: str
    advisory_only: bool
    permission_claimed: bool
    completion_claimed: bool
    permission_decision: str
    completion_status: str


class EffortAllocatorTelemetryEvent(TypedDict):
    event: Literal["effort_allocator.route"]
    task_type: str
    active_mode: str
    ambiguity_score: float
    risk_score: float
    stakes_signal: float
    action_required: bool
    memory_commit_possible: bool
    disagreement_likelihood: float
    cue_strength: float
    effort_score: int
    effort_level: EffortLevel | str
    cognition_topology: CognitionTopology | str
    monitor_intensity: MonitorIntensity | str
    verification_requirement: VerificationRequirement | str
    memory_commit_status: str
    reasoning_engine: ReasoningEngine | str
    allocator_reason: str


class ThresholdTuningRequest(TypedDict):
    reason: str
    compute_pressure_only: bool
    failure_distribution_available: bool
    observed_failure_modes: list[str]


class ThresholdTuningDecision(TypedDict):
    tuning_allowed: bool
    reasons: list[str]
    message: str


class EffortAllocatorEvaluatorLabel(TypedDict):
    observed_outcome: str
    failure_modes: list[FailureMode | str]
    meaningful_error: bool
    wasted_effort: bool
    human_correction_required: bool
    completion_reversal: bool
    memory_error: bool
    recognition_degradation: bool
    label_confidence: float
    notes: str


class EffortAllocatorOutcomeRecord(TypedDict):
    event: Literal["effort_allocator.outcome"]
    turn_id: str
    session_id: str
    task_type: str
    active_mode: str
    effort_score: int
    effort_level: EffortLevel | str
    cognition_topology: CognitionTopology | str
    verification_requirement: VerificationRequirement | str
    allocator_reason: str
    observed_outcome: str
    failure_modes: list[FailureMode | str]
    meaningful_error: bool
    wasted_effort: bool
    human_correction_required: bool
    completion_reversal: bool
    memory_error: bool
    recognition_degradation: bool
    label_confidence: float
    notes: str


class EffortAllocatorDistributionSummary(TypedDict):
    event: Literal["effort_allocator.distribution_summary"]
    window_id: str
    sample_size: int
    failure_counts: dict[str, int]
    by_effort_level: dict[str, int]
    notes: str


class RequestedThresholdChange(TypedDict):
    field: str
    current: float
    proposed: float
    direction: str


class EffortAllocatorThresholdReviewRequest(TypedDict):
    event: Literal["effort_allocator.threshold_review_request"]
    window_id: str
    requested_change: RequestedThresholdChange
    failure_distribution_available: bool
    sample_size: int
    project_minimum_sample_size: int
    repeated_failure_pattern: bool
    supporting_failure_modes: list[FailureMode | str]
    compute_pressure_only: bool
    tradeoff_note: str
    rollback_path: str


class EffortAllocatorGovernanceDecision(TypedDict):
    event: Literal["effort_allocator.governance_decision"]
    window_id: str
    decision: GovernanceDecision | str
    requested_change: str
    reasons: list[str]
    execution_status: ExecutionStatus | str
    tradeoff_note: str
    rollback_path: str
