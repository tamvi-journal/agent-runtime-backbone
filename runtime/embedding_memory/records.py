from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from runtime.contracts.enums import LIFECYCLE_PROVISIONAL, OBSIDIAN_NON_AUTHORITATIVE
from runtime.contracts.memory_types import MemoryKind, MemorySource, SemanticMemoryRecord
from runtime.embedding_memory.embeddings import DEFAULT_EMBEDDING_MODEL, embed_text


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_semantic_memory_record(
    *,
    user_id: str,
    kind: MemoryKind,
    title: str,
    content: str,
    tags: list[str] | None = None,
    source: MemorySource = "manual",
    source_handles: list[str] | None = None,
    strength: float = 0.75,
    metadata: dict[str, object] | None = None,
) -> SemanticMemoryRecord:
    """Build a provisional non-authoritative semantic memory record.

    The default status intentionally prevents accidental canonical memory mutation.
    """
    created_at = utc_now_iso()
    return {
        "id": f"mem_{uuid4().hex}",
        "user_id": user_id,
        "kind": kind,
        "title": title,
        "content": content,
        "tags": tags or [],
        "strength": max(0.0, min(float(strength), 1.0)),
        "source": source,
        "source_handles": source_handles or [],
        "lifecycle_status": LIFECYCLE_PROVISIONAL,
        "authority_status": OBSIDIAN_NON_AUTHORITATIVE,
        "created_at": created_at,
        "last_accessed": None,
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "embedding": embed_text(content),
        "metadata": metadata or {},
    }
