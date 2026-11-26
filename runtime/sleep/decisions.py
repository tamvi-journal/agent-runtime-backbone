from __future__ import annotations

from runtime.contracts.sleep_types import ResumeDecision, WakeSanityResult


def decide_resume_level(
    *,
    identity_ok: bool,
    snapshot_ok: bool,
    task_scope_ok: bool,
    stale_handles: list[str],
    gate_decision: str,
    verification_status: str,
) -> ResumeDecision:
    if not snapshot_ok:
        return "restart_required"
    if not identity_ok:
        return "restart_required"
    if gate_decision in {"deny"}:
        return "restart_required"
    if not task_scope_ok:
        return "resume_with_clarification"
    if gate_decision in {"needs_approval", "sandbox_only"}:
        return "resume_read_only"
    if stale_handles:
        return "resume_with_refresh"
    if verification_status in {"pending", "partial", "unverified"}:
        return "resume_with_refresh"
    return "resume_full"


def build_wake_result(
    *,
    resume_decision: ResumeDecision,
    reasons: list[str] | None = None,
    required_refreshes: list[str] | None = None,
    held_claims: list[str] | None = None,
    confidence: float = 0.7,
) -> WakeSanityResult:
    status = "pass"
    if resume_decision == "restart_required":
        status = "fail"
    elif resume_decision != "resume_full":
        status = "warn"

    return {
        "resume_decision": resume_decision,
        "status": status,
        "reasons": reasons or [],
        "required_refreshes": required_refreshes or [],
        "held_claims": held_claims or [],
        "confidence": max(0.0, min(float(confidence), 1.0)),
    }
