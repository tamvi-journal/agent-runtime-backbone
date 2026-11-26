from __future__ import annotations

"""Evidence and release eligibility helpers for the agent worker outputs.

Worker packets may report evidence handles, but those handles are claims from
inside the worker boundary. This module keeps that separate from evidence that
MainBrain or another external verifier has checked independently.
"""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

EVIDENCE_STATUS_CLAIMED_ONLY = "claimed_only"
EVIDENCE_STATUS_EXTERNALLY_VERIFIED = "externally_verified"
EVIDENCE_STATUS_MISSING = "missing_claimed_evidence"

RELEASE_ELIGIBLE_FOR_MAINBRAIN_REVIEW = "eligible_for_mainbrain_review"
RELEASE_NOT_ELIGIBLE_PENDING_VERIFICATION = "not_eligible_pending_verification"

CLAIMED_EVIDENCE_LIMITATION = "worker-reported evidence is claimed, not independently verified"
MISSING_EVIDENCE_LIMITATION = "worker returned no claimed evidence handles"
PENDING_VERIFICATION_LIMITATION = "release requires MainBrain or external verification"
VERIFIER_ARTIFACT_MISSING_LIMITATION = "verified evidence needs an inspectable artifact or evidence handle"
SELF_VERIFICATION_LIMITATION = "worker identity cannot verify its own output"


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return []


def _copy_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    return None


def _copy_mapping_list(value: Any) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for item in _as_list(value):
        mapped = _copy_mapping(item)
        if mapped is not None:
            copied.append(mapped)
    return copied


def _dedupe_text(values: list[Any]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            deduped.append(text)
            seen.add(text)
    return deduped


def _extract_verified_evidence(envelope: Mapping[str, Any] | None) -> dict[str, Any] | None:
    data = _copy_mapping(envelope) or {}
    candidate = data.get("verified_evidence")
    if candidate is None:
        candidate = data.get("verification_result")
    verified = _copy_mapping(candidate)
    if verified is None:
        return None

    handles = _copy_mapping_list(
        verified.get("evidence_handles")
        or verified.get("verified_evidence_handles")
        or verified.get("artifacts")
        or verified.get("artifact_handles")
    )
    checks_run = _dedupe_text(_as_list(verified.get("checks_run") or verified.get("verified_checks")))
    verified_by = str(verified.get("verified_by") or verified.get("verifier") or verified.get("source") or "").strip()
    worker_identity = str(data.get("worker_id") or data.get("agent_id") or "").strip()
    self_verification = bool(worker_identity and verified_by and worker_identity == verified_by)
    valid = bool(verified_by and handles and not self_verification)

    return {
        "valid": valid,
        "verified_by": verified_by or None,
        "evidence_handles": handles,
        "checks_run": checks_run,
        "artifact_missing": bool(verified_by and not handles),
        "self_verification": self_verification,
        "raw": verified,
    }


def build_worker_evidence_gate(
    worker_output: Mapping[str, Any] | None,
    envelope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify worker evidence without granting truth or completion authority.

    Claimed worker evidence alone never makes a result release-eligible. the agent
    only marks the candidate eligible for MainBrain review when an external
    verifier supplies valid verified evidence through the invocation envelope.
    """

    output = _copy_mapping(worker_output) or {}
    claimed_handles = _copy_mapping_list(output.get("evidence_handles"))
    verified = _extract_verified_evidence(envelope)
    verified_handles = _copy_mapping_list((verified or {}).get("evidence_handles"))
    verified_checks = _dedupe_text(_as_list((verified or {}).get("checks_run")))
    verification_valid = bool((verified or {}).get("valid"))

    if verification_valid:
        evidence_status = EVIDENCE_STATUS_EXTERNALLY_VERIFIED
        release_eligibility = RELEASE_ELIGIBLE_FOR_MAINBRAIN_REVIEW
        verification_needed = False
        limitations: list[str] = []
    elif claimed_handles:
        evidence_status = EVIDENCE_STATUS_CLAIMED_ONLY
        release_eligibility = RELEASE_NOT_ELIGIBLE_PENDING_VERIFICATION
        verification_needed = True
        limitations = [CLAIMED_EVIDENCE_LIMITATION, PENDING_VERIFICATION_LIMITATION]
    else:
        evidence_status = EVIDENCE_STATUS_MISSING
        release_eligibility = RELEASE_NOT_ELIGIBLE_PENDING_VERIFICATION
        verification_needed = True
        limitations = [MISSING_EVIDENCE_LIMITATION, PENDING_VERIFICATION_LIMITATION]
    if (verified or {}).get("artifact_missing") and VERIFIER_ARTIFACT_MISSING_LIMITATION not in limitations:
        limitations.append(VERIFIER_ARTIFACT_MISSING_LIMITATION)
    if (verified or {}).get("self_verification") and SELF_VERIFICATION_LIMITATION not in limitations:
        limitations.append(SELF_VERIFICATION_LIMITATION)
    evidence_findings = []
    if (verified or {}).get("artifact_missing"):
        evidence_findings.append({"kind": "verifier_artifact_missing", "severity": "medium"})
    if (verified or {}).get("self_verification"):
        evidence_findings.append({"kind": "self_verification", "severity": "medium"})

    return {
        "evidence_status": evidence_status,
        "release_eligibility": release_eligibility,
        "verification_needed": verification_needed,
        "claimed_evidence_handles": claimed_handles,
        "claimed_evidence_count": len(claimed_handles),
        "verified_evidence": deepcopy((verified or {}).get("raw")) if verification_valid else None,
        "verified_evidence_handles": verified_handles if verification_valid else [],
        "verified_evidence_count": len(verified_handles) if verification_valid else 0,
        "verified_checks_run": verified_checks if verification_valid else [],
        "verified_by": (verified or {}).get("verified_by") if verification_valid else None,
        "evidence_findings": evidence_findings,
        "limitations": limitations,
        "release_gate": {
            "eligible_for_release": release_eligibility == RELEASE_ELIGIBLE_FOR_MAINBRAIN_REVIEW,
            "release_eligibility": release_eligibility,
            "reason": evidence_status,
        },
    }


__all__ = [
    "build_worker_evidence_gate",
    "EVIDENCE_STATUS_CLAIMED_ONLY",
    "EVIDENCE_STATUS_EXTERNALLY_VERIFIED",
    "EVIDENCE_STATUS_MISSING",
    "RELEASE_ELIGIBLE_FOR_MAINBRAIN_REVIEW",
    "RELEASE_NOT_ELIGIBLE_PENDING_VERIFICATION",
]
