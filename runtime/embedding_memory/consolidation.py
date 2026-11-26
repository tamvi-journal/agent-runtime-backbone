from __future__ import annotations

from runtime.contracts.memory_types import ConsolidationCandidate, MemoryKind, MemorySource

CORE_CHECKPOINT_MARKERS = (
    "checkpoint",
    "core",
    "axis",
    "boundary",
    "identity",
    "ontology",
    "skill",
    "trace",
)

TRANSIENT_REJECT_MARKERS = (
    "just chatting",
    "temporary mood",
    "raw transcript",
    "private reasoning",
    "hidden reasoning",
)


def classify_memory_kind(text: str) -> MemoryKind:
    lowered = text.lower()
    if any(term in lowered for term in ("coherence", "entropy", "resonance", "attractor")):
        return "ontology"
    if any(term in lowered for term in ("workflow", "procedure", "when this task", "skill")):
        return "skill"
    if any(term in lowered for term in ("repo", "runtime", "task", "spec")):
        return "project"
    if any(term in lowered for term in ("truth before fluency", "axis before capability", "mainbrain speaks last")):
        return "identity_axis"
    return "interaction_trace"


def should_consolidate(text: str) -> tuple[bool, str]:
    lowered = text.lower()
    if any(marker in lowered for marker in TRANSIENT_REJECT_MARKERS):
        return False, "transient_or_forbidden_storage_shape"
    if any(marker in lowered for marker in CORE_CHECKPOINT_MARKERS):
        return True, "contains_core_checkpoint_marker"
    if len(text.split()) >= 80:
        return True, "substantive_long_form_candidate"
    return False, "insufficient_stability_signal"


def build_consolidation_candidate(
    *,
    user_id: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
    source: MemorySource = "manual",
    source_handles: list[str] | None = None,
    explicit_kind: MemoryKind | None = None,
    explicit_approval: bool = False,
) -> ConsolidationCandidate | None:
    allowed, reason = should_consolidate(content)
    if not allowed:
        return None

    return {
        "user_id": user_id,
        "kind": explicit_kind or classify_memory_kind(content),
        "title": title,
        "content": content,
        "tags": tags or [],
        "source": source,
        "source_handles": source_handles or [],
        "strength": 0.75,
        "reason": reason,
        "requires_approval": not explicit_approval,
    }
