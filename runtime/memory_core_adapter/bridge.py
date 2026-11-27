from __future__ import annotations

from typing import Any

from runtime.retrieval_candidate_context import build_retrieval_candidate_context


def _authority_status(value: str) -> str:
    if value in {"canonical_reference", "protected"}:
        return "canonical"
    if value in {"deprecated", "invalidated"}:
        return value
    return "candidate"


def _lifecycle_status(revision: dict[str, Any]) -> str:
    status = revision.get("revision_status")
    if status == "current":
        return "active"
    if status == "superseded":
        return "replaced"
    if status == "invalidated":
        return "blocked"
    return "review_required"


def build_candidate_context(
    memory_runtime,
    query: str,
    *,
    scope: str = "global",
    limit: int = 8,
) -> dict[str, Any]:
    """Translate Memory Core hits into the agent's existing candidate boundary.

    The result remains unreviewed candidate context. MainBrain, verification,
    gate, and governance continue to decide whether any claim may be used.
    """
    hits = memory_runtime.retrieve_readonly(query, scope=scope, limit=limit, token_budget=1400)
    raw_candidates: list[dict[str, Any]] = []
    for hit in hits:
        revision = hit.revision
        evidence = memory_runtime.store.evidence_for_revision(
            revision["revision_id"]
        )
        contradicts = any(item["stance"] == "contradicts" for item in evidence)
        raw_candidates.append(
            {
                "candidate_id": revision["revision_id"],
                "memory_id": revision["record_id"],
                "record_type": revision["record_class"],
                "content": revision["summary"] or revision["content"],
                "impact": revision["impact"],
                "source": "retrieved_memory_candidate",
                "confidence": revision["confidence"],
                "authority_status": _authority_status(
                    revision["authority_status"]
                ),
                "lifecycle_status": _lifecycle_status(revision),
                "evidence_handles": [
                    item["source_ref"] for item in evidence if item["source_ref"]
                ],
                "relation_handles": list(hit.reasons),
                "rank_or_similarity_score": hit.score,
                "task_relevance": "relevant",
                "contradiction_status": (
                    "needs_review" if contradicts else "none_known"
                ),
            }
        )
    packet = build_retrieval_candidate_context(
        query,
        raw_candidates,
        retrieval_source="memory_core_instance_profile",
        generated_by="agent_memory_core_adapter",
    )
    packet["authority_boundary"] = {
        "mainbrain": "unchanged",
        "monitor": "unchanged",
        "gate": "unchanged",
        "verification": "unchanged",
        "memory_decides_truth": False,
    }
    return packet
