from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from runtime.contracts.enums import LIFECYCLE_INVALIDATED
from runtime.contracts.memory_types import SemanticMemoryRecord
from runtime.embedding_memory.embeddings import cosine_similarity


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class InMemorySemanticStore:
    """Small local semantic-memory store for contract testing.

    This is not a production vector database. It preserves the same semantics
    ExampleAgent will need when swapped to pgvector, Qdrant, Chroma, LanceDB, or FAISS.
    """

    records: dict[str, SemanticMemoryRecord] = field(default_factory=dict)

    def upsert(self, record: SemanticMemoryRecord) -> SemanticMemoryRecord:
        self.records[record["id"]] = record
        return record

    def get(self, memory_id: str) -> SemanticMemoryRecord | None:
        return self.records.get(memory_id)

    def all_for_user(self, user_id: str) -> list[SemanticMemoryRecord]:
        return [record for record in self.records.values() if record["user_id"] == user_id]

    def search(
        self,
        *,
        user_id: str,
        query_embedding: list[float],
        top_k: int = 8,
        min_similarity: float = 0.1,
        include_deprecated: bool = False,
    ) -> list[tuple[SemanticMemoryRecord, float]]:
        scored: list[tuple[SemanticMemoryRecord, float]] = []
        for record in self.all_for_user(user_id):
            lifecycle = record["lifecycle_status"]
            if lifecycle == LIFECYCLE_INVALIDATED:
                continue
            if lifecycle == "deprecated" and not include_deprecated:
                continue
            similarity = cosine_similarity(query_embedding, record["embedding"])
            if similarity >= min_similarity:
                scored.append((record, similarity))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    def mark_accessed(self, memory_id: str) -> None:
        record = self.records.get(memory_id)
        if record is None:
            return
        record["last_accessed"] = utc_now_iso()
