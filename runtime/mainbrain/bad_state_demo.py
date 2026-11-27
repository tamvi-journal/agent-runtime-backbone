from __future__ import annotations

from typing import TypedDict

from runtime.contracts.enums import ROUTE_KERNEL_CAPABILITY_PATH, GATE_ALLOW
from runtime.contracts.types import CommitEvaluation, ObservabilityMirror
from runtime.monitor.commit import evaluate_commit
from runtime.monitor.observability import build_observability_mirror


class BadStateDemoResult(TypedDict):
    commit_status: str
    completion_claim_allowed: bool
    display_state: str
    verification_status: str
    reasons: list[str]
    evidence_handles: list[str]
    message: str
    final_response_allowed: bool


def build_bad_state_message(commit_result: CommitEvaluation, mirror: ObservabilityMirror) -> str:
    if commit_result["completion_claim_allowed"]:
        return "verified completion allowed"

    if mirror["display_state"] == "failure":
        return "completion not allowed; bad state detected and final completion wording is blocked"

    return "completion not allowed; work may exist but verification is incomplete"


def run_bad_state_demo(
    *,
    intended_action: str,
    executed_action: str,
    observed_outcome: str,
    evidence_handles: list[str],
    verification_status: str,
    completion_claim_requested: bool,
    worker_claim_present: bool,
    work_artifact_present: bool,
    gate_decision: str = GATE_ALLOW,
    route_class: str = ROUTE_KERNEL_CAPABILITY_PATH,
    mainbrain_verified: bool = False,
) -> BadStateDemoResult:
    commit_result = evaluate_commit(
        intended_action=intended_action,
        executed_action=executed_action,
        observed_outcome=observed_outcome,
        evidence_handles=evidence_handles,
        verification_status=verification_status,
        mainbrain_verified=mainbrain_verified,
        completion_claim_requested=completion_claim_requested,
        worker_claim_present=worker_claim_present,
        work_artifact_present=work_artifact_present,
    )
    mirror = build_observability_mirror(
        route_class=route_class,
        gate_decision=gate_decision,
        commit_result=commit_result,
        notes=["completion not allowed"],
    )

    return {
        "commit_status": commit_result["status"],
        "completion_claim_allowed": False,
        "display_state": mirror["display_state"],
        "verification_status": commit_result["verification_status"],
        "reasons": list(commit_result["reasons"]),
        "evidence_handles": list(commit_result["evidence_handles"]),
        "message": build_bad_state_message(commit_result, mirror),
        "final_response_allowed": False,
    }
