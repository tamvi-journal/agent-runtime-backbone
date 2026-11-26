from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Literal

RETRIEVAL_NOTE = "retrieval candidates only; not truth by itself"
AllowedUse = Literal[
    "candidate_context",
    "historical_comparison_only",
    "evidence_reference_only",
    "blocked_do_not_use",
    "review_before_use",
]
BlockedStatus = Literal["allowed", "inert", "blocked", "review_required"]
TaskRelevance = Literal["relevant", "partially_relevant", "not_relevant", "unknown"]
ContradictionStatus = Literal[
    "none_known",
    "contradicts_current_context",
    "contradicted_by_newer_record",
    "needs_review",
    "unknown",
]


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _text(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _classify_allowed_use(
    *,
    authority_status: str,
    lifecycle_status: str,
    task_relevance: str,
    source: str,
    contradiction_status: str,
) -> tuple[AllowedUse, BlockedStatus, str]:
    authority = _text(authority_status)
    lifecycle = _text(lifecycle_status)
    relevance = _text(task_relevance)
    source_type = _text(source)
    contradiction = _text(contradiction_status)

    if lifecycle == "blocked" or authority == "invalidated":
        return "blocked_do_not_use", "blocked", "invalidated_records_blocked_by_default"

    if lifecycle == "inert" or authority == "deprecated":
        return "historical_comparison_only", "inert", "deprecated_or_replaced_inert_by_default"

    if lifecycle == "replaced":
        return "historical_comparison_only", "inert", "replaced_records_are_historical_unless_requested"

    if lifecycle == "review_required":
        return "review_before_use", "review_required", "review_required_before_use"

    if authority == "canonical":
        if lifecycle == "active" and relevance in {"relevant", "partially_relevant"}:
            allowed_use: AllowedUse = "candidate_context"
            blocked_status: BlockedStatus = "allowed"
            block_reason = ""
        else:
            allowed_use = "review_before_use"
            blocked_status = "review_required"
            block_reason = "canonical_memory_requires_task_relevance_check"
    elif authority == "candidate":
        if lifecycle == "active":
            allowed_use = "candidate_context"
            blocked_status = "allowed"
            block_reason = ""
        else:
            allowed_use = "review_before_use"
            blocked_status = "review_required"
            block_reason = "candidate_record_requires_review"
    else:
        allowed_use = "review_before_use"
        blocked_status = "review_required"
        block_reason = "unknown_authority_requires_review"

    if source_type == "unknown" and allowed_use != "blocked_do_not_use":
        allowed_use = "review_before_use"
        blocked_status = "review_required"
        block_reason = "unknown_source_requires_review"

    if contradiction in {"needs_review", "contradicts_current_context", "contradicted_by_newer_record"} and allowed_use == "candidate_context":
        allowed_use = "review_before_use"
        blocked_status = "review_required"
        block_reason = "contradiction_requires_review"

    return allowed_use, blocked_status, block_reason


def _normalize_candidate(raw_candidate: dict[str, Any]) -> dict[str, Any]:
    candidate = deepcopy(raw_candidate)
    memory_id = _text(candidate.get("memory_id", candidate.get("id", "")), "")
    candidate_id = _text(candidate.get("candidate_id", memory_id), memory_id or "unknown")
    source = _text(candidate.get("source"), "unknown")
    authority_status = _text(candidate.get("authority_status"), "unknown")
    lifecycle_status = _text(candidate.get("lifecycle_status"), "unknown")
    task_relevance = _text(candidate.get("task_relevance"), "unknown")
    contradiction_status = _text(candidate.get("contradiction_status"), "none_known")
    allowed_use, blocked_status, block_reason = _classify_allowed_use(
        authority_status=authority_status,
        lifecycle_status=lifecycle_status,
        task_relevance=task_relevance,
        source=source,
        contradiction_status=contradiction_status,
    )

    normalized = {
        "candidate_id": candidate_id,
        "memory_id": memory_id or candidate_id,
        "record_type": _text(candidate.get("record_type"), "unknown"),
        "content": candidate.get("content", "unknown"),
        "impact": candidate.get("impact", "unknown"),
        "source": source,
        "confidence": candidate.get("confidence", "unknown"),
        "authority_status": authority_status,
        "lifecycle_status": lifecycle_status,
        "evidence_handles": _list(candidate.get("evidence_handles")),
        "relation_handles": _list(candidate.get("relation_handles")),
        "rank_or_similarity_score": candidate.get("rank_or_similarity_score", 0.0),
        "blocked_status": blocked_status,
        "block_reason": block_reason,
        "retrieval_note": RETRIEVAL_NOTE,
        "task_relevance": task_relevance,
        "contradiction_status": contradiction_status,
        "allowed_use": allowed_use,
    }
    return normalized


def build_retrieval_candidate_context(
    query: str,
    raw_candidates: list[dict[str, Any]],
    *,
    retrieval_source: str = "provided_by_caller",
    generated_by: str = "retrieval_candidate_context_helper",
) -> dict[str, Any]:
    normalized_candidates = [_normalize_candidate(candidate) for candidate in raw_candidates]
    blocked_candidates = [candidate for candidate in normalized_candidates if candidate["blocked_status"] == "blocked"]
    candidates = [candidate for candidate in normalized_candidates if candidate["blocked_status"] != "blocked"]
    contradiction_notes = [
        {
            "candidate_id": candidate["candidate_id"],
            "memory_id": candidate["memory_id"],
            "contradiction_status": candidate["contradiction_status"],
            "note": "contradiction surfaced for review" if candidate["contradiction_status"] != "none_known" else "none",
        }
        for candidate in normalized_candidates
        if candidate["contradiction_status"] != "none_known"
    ]

    summary = {
        "total_candidates": len(normalized_candidates),
        "allowed_candidates": len(candidates),
        "blocked_candidates": len(blocked_candidates),
        "candidate_context": sum(1 for candidate in candidates if candidate["allowed_use"] == "candidate_context"),
        "historical_comparison_only": sum(1 for candidate in candidates if candidate["allowed_use"] == "historical_comparison_only"),
        "evidence_reference_only": sum(1 for candidate in candidates if candidate["allowed_use"] == "evidence_reference_only"),
        "review_before_use": sum(1 for candidate in candidates if candidate["allowed_use"] == "review_before_use"),
        "blocked_do_not_use": len(blocked_candidates),
    }

    return {
        "query": query,
        "retrieval_timestamp": utc_now_iso(),
        "retrieval_source": retrieval_source,
        "candidates": candidates,
        "blocked_candidates": blocked_candidates,
        "contradiction_notes": contradiction_notes,
        "candidate_summary": summary,
        "retrieval_note": RETRIEVAL_NOTE,
        "generated_by": generated_by,
        "review_status": "unreviewed",
    }
