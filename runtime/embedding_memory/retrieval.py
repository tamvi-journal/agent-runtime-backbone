from __future__ import annotations

from runtime.contracts.enums import (
    LIFECYCLE_DEPRECATED,
    LIFECYCLE_INVALIDATED,
    OBSIDIAN_CANONICAL_REFERENCE,
)
from runtime.contracts.memory_types import (
    MemoryKind,
    MemoryRetrievalResult,
    SemanticMemoryCandidate,
    SemanticMemoryRecord,
)
from runtime.embedding_memory.embeddings import embed_text
from runtime.embedding_memory.store import InMemorySemanticStore

KIND_PRIORITIES: dict[str, float] = {
    "identity_axis": 0.20,
    "ontology": 0.16,
    "skill": 0.14,
    "project": 0.12,
    "user_profile": 0.10,
    "interaction_trace": 0.06,
    "canonical_candidate": 0.04,
}


def is_blocked(record: SemanticMemoryRecord) -> tuple[bool, str]:
    lifecycle = record["lifecycle_status"]
    if lifecycle == LIFECYCLE_INVALIDATED:
        return True, "invalidated_memory_blocked"
    if lifecycle == LIFECYCLE_DEPRECATED:
        return True, "deprecated_memory_inert_by_default"
    return False, ""


def rerank_score(record: SemanticMemoryRecord, similarity: float) -> float:
    kind_bonus = KIND_PRIORITIES.get(record["kind"], 0.0)
    authority_bonus = 0.08 if record["authority_status"] == OBSIDIAN_CANONICAL_REFERENCE else 0.0
    strength_bonus = max(0.0, min(float(record["strength"]), 1.0)) * 0.10
    return similarity + kind_bonus + authority_bonus + strength_bonus


def build_candidate(record: SemanticMemoryRecord, similarity: float) -> SemanticMemoryCandidate:
    blocked, block_reason = is_blocked(record)
    return {
        "record": record,
        "similarity": similarity,
        "rerank_score": rerank_score(record, similarity),
        "blocked": blocked,
        "block_reason": block_reason,
    }


def retrieve_candidates(
    *,
    store: InMemorySemanticStore,
    user_id: str,
    query: str,
    allowed_kinds: list[MemoryKind] | None = None,
    top_k: int = 8,
    min_similarity: float = 0.1,
    include_deprecated: bool = False,
) -> MemoryRetrievalResult:
    query_embedding = embed_text(query)
    raw_results = store.search(
        user_id=user_id,
        query_embedding=query_embedding,
        top_k=max(top_k * 2, top_k),
        min_similarity=min_similarity,
        include_deprecated=include_deprecated,
    )

    candidates: list[SemanticMemoryCandidate] = []
    allowed = set(allowed_kinds or [])
    for record, similarity in raw_results:
        if allowed and record["kind"] not in allowed:
            continue
        candidate = build_candidate(record, similarity)
        if not candidate["blocked"] or include_deprecated:
            candidates.append(candidate)

    candidates.sort(key=lambda item: item["rerank_score"], reverse=True)
    candidates = candidates[:top_k]

    if not candidates:
        status = "empty"
        notes = "no_candidate_memory_found"
    elif any(candidate["blocked"] for candidate in candidates):
        status = "partial"
        notes = "some_candidates_blocked_by_lifecycle"
    else:
        status = "passed"
        notes = "retrieval_candidates_only_not_truth"

    return {
        "query": query,
        "candidates": candidates,
        "retrieval_status": status,
        "notes": notes,
    }
