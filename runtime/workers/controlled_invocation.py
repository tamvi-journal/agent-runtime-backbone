from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime.workers.evidence_gate import (
    RELEASE_NOT_ELIGIBLE_PENDING_VERIFICATION,
    build_worker_evidence_gate,
)
from runtime.workers.preflight_guard import validate_worker_invocation_envelope
from runtime.workers.repo_research_worker import run_repo_research_worker

WORKER_ID = "repo_research_worker"
WORKER_TYPE = "read_only_repo_research"
DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _mapping_copy(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    return None


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return []


def _dedupe(values: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _base_result(
    envelope: Mapping[str, Any] | None,
    preflight: Mapping[str, Any],
    *,
    decision: str,
    worker_output: dict[str, Any] | None,
    candidate_status: str,
    evidence_gate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    data = _mapping_copy(envelope) or {}
    gate = _mapping_copy(evidence_gate) or {}
    preflight_limitations = _as_list(preflight.get("limitations")) or _as_list(preflight.get("reasons"))
    gate_limitations = _as_list(gate.get("limitations"))
    release_eligibility = gate.get("release_eligibility", RELEASE_NOT_ELIGIBLE_PENDING_VERIFICATION)
    verification_needed = bool(gate.get("verification_needed", bool(data.get("verification_expectation"))))
    return {
        "invocation_id": data.get("invocation_id") or f"inv-{uuid4().hex}",
        "task_id": data.get("task_id"),
        "worker_id": data.get("worker_id"),
        "worker_type": data.get("worker_type"),
        "decision": decision,
        "preflight": deepcopy(dict(preflight)),
        "worker_output": worker_output,
        "return_path": data.get("return_path"),
        "candidate_status": candidate_status,
        "side_effect_request": None,
        "verification_needed": verification_needed,
        "governance_needed": bool(data.get("governance_expectation")),
        "evidence_status": gate.get("evidence_status", "not_checked"),
        "release_eligibility": release_eligibility,
        "release_gate": gate.get(
            "release_gate",
            {
                "eligible_for_release": False,
                "release_eligibility": release_eligibility,
                "reason": "worker_not_executed",
            },
        ),
        "claimed_evidence_handles": deepcopy(gate.get("claimed_evidence_handles", [])),
        "claimed_evidence_count": int(gate.get("claimed_evidence_count", 0) or 0),
        "verified_evidence": deepcopy(gate.get("verified_evidence")),
        "verified_evidence_handles": deepcopy(gate.get("verified_evidence_handles", [])),
        "verified_evidence_count": int(gate.get("verified_evidence_count", 0) or 0),
        "verified_checks_run": list(gate.get("verified_checks_run", [])),
        "verified_by": gate.get("verified_by"),
        "limitations": _dedupe(preflight_limitations + gate_limitations),
        "generated_at": _utc_now(),
    }


def _blocked_result(envelope: Mapping[str, Any] | None, preflight: Mapping[str, Any], decision: str) -> dict[str, Any]:
    return _base_result(
        envelope,
        preflight,
        decision=decision,
        worker_output=None,
        candidate_status="blocked",
    )


def _annotate_worker_output(worker_output: dict[str, Any], evidence_gate: Mapping[str, Any]) -> dict[str, Any]:
    output = deepcopy(worker_output)
    gate_limitations = _as_list(evidence_gate.get("limitations"))
    output["evidence_status"] = evidence_gate.get("evidence_status")
    output["release_eligibility"] = evidence_gate.get("release_eligibility")
    output["release_gate"] = deepcopy(evidence_gate.get("release_gate"))
    output["claimed_evidence_handles"] = deepcopy(evidence_gate.get("claimed_evidence_handles", []))
    output["claimed_evidence_count"] = int(evidence_gate.get("claimed_evidence_count", 0) or 0)
    output["verified_evidence_count"] = int(evidence_gate.get("verified_evidence_count", 0) or 0)
    output["verification_needed"] = bool(evidence_gate.get("verification_needed", output.get("verification_needed", True)))
    output["limitations"] = _dedupe(_as_list(output.get("limitations")) + gate_limitations)
    return output


def invoke_worker_with_envelope(envelope: Mapping[str, Any], repo_root: str | Path) -> dict[str, Any]:
    preflight = validate_worker_invocation_envelope(envelope)
    data = _mapping_copy(envelope)
    if data is None:
        return _blocked_result(envelope, preflight, "invalid_envelope")

    worker_id = data.get("worker_id")
    worker_type = data.get("worker_type")
    if worker_id != WORKER_ID or worker_type != WORKER_TYPE:
        return _blocked_result(envelope, preflight, "blocked")

    decision = preflight.get("decision")
    if decision == "invalid_envelope":
        return _blocked_result(envelope, preflight, "invalid_envelope")
    if decision == "needs_approval":
        return _blocked_result(envelope, preflight, "needs_approval")
    if decision != "allow":
        return _blocked_result(envelope, preflight, "blocked")

    worker_output = run_repo_research_worker(envelope, repo_root)
    candidate_status = worker_output.get("candidate_status", "blocked")
    evidence_gate = build_worker_evidence_gate(worker_output, envelope)
    annotated_worker_output = _annotate_worker_output(worker_output, evidence_gate)
    wrapper_decision = "completed_candidate" if candidate_status == "candidate" else "blocked"

    return _base_result(
        envelope,
        preflight,
        decision=wrapper_decision,
        worker_output=annotated_worker_output,
        candidate_status=candidate_status,
        evidence_gate=evidence_gate,
    )


__all__ = ["invoke_worker_with_envelope"]
