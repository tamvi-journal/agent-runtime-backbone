from __future__ import annotations

from runtime.canonical.contracts import PromotionDecision
from runtime.contracts.enums import (
    MONITOR_STATUS_VERIFIED_COMPLETE,
    OBSIDIAN_CANDIDATE,
    OBSIDIAN_CANONICAL_REFERENCE,
    OBSIDIAN_NON_AUTHORITATIVE,
    VERIFICATION_PASSED,
)

_VETO_REASONS = {
    "evidence_gap_detected",
    "verification_not_passed",
    "completion_claim_without_verification",
    "completion_claim_without_mainbrain_verification",
    "worker_output_unverified_by_mainbrain",
}


def evaluate_promotion_request(
    *,
    verification_status: str,
    completion_claim_allowed: bool,
    commit_status: str,
    display_state: str,
    evidence_handles: list[str],
    reasons: list[str],
    current_canonical_status: str,
    requested_target: str,
    origin_kind: str,
) -> PromotionDecision:
    del current_canonical_status  # v0.1 does not derive promotion from prior note state.

    decision_reasons = list(reasons)

    if origin_kind == "delegate":
        return {
            "decision": "promotion_blocked",
            "target_status": OBSIDIAN_NON_AUTHORITATIVE,
            "promotion_allowed": False,
            "reasons": decision_reasons + ["delegate_origin_cannot_promote"],
            "message": "promotion blocked: delegate origin cannot directly promote canonical docs",
        }

    if origin_kind == "worker":
        return {
            "decision": "promotion_blocked",
            "target_status": OBSIDIAN_NON_AUTHORITATIVE,
            "promotion_allowed": False,
            "reasons": decision_reasons + ["worker_origin_cannot_promote"],
            "message": "promotion blocked: worker origin cannot directly promote canonical docs",
        }

    if requested_target == OBSIDIAN_CANONICAL_REFERENCE:
        return {
            "decision": "needs_approval",
            "target_status": OBSIDIAN_NON_AUTHORITATIVE,
            "promotion_allowed": False,
            "reasons": decision_reasons + ["canonical_reference_requires_approval"],
            "message": "canonical_reference promotion needs approval; no automatic governance path exists in v0.1",
        }

    if verification_status != VERIFICATION_PASSED:
        decision_reasons.append("verification_not_passed")
    if not completion_claim_allowed:
        decision_reasons.append("completion_claim_not_allowed")
    if commit_status != MONITOR_STATUS_VERIFIED_COMPLETE:
        decision_reasons.append("commit_status_not_verified_complete")
    if display_state != "success":
        decision_reasons.append("display_state_not_success")
    if not evidence_handles:
        decision_reasons.append("missing_evidence_handles")
    if any(reason in _VETO_REASONS for reason in reasons):
        decision_reasons.append("veto_reason_present")

    if decision_reasons:
        return {
            "decision": "promotion_blocked",
            "target_status": OBSIDIAN_NON_AUTHORITATIVE,
            "promotion_allowed": False,
            "reasons": decision_reasons,
            "message": "promotion blocked; canonical candidate conditions are not fully satisfied",
        }

    if requested_target == OBSIDIAN_CANDIDATE:
        return {
            "decision": "allow_candidate",
            "target_status": OBSIDIAN_CANDIDATE,
            "promotion_allowed": True,
            "reasons": [],
            "message": "candidate promotion allowed under v0.1 gate",
        }

    return {
        "decision": "stay_non_authoritative",
        "target_status": OBSIDIAN_NON_AUTHORITATIVE,
        "promotion_allowed": False,
        "reasons": ["unsupported_requested_target"],
        "message": "promotion blocked; unsupported requested target",
    }
