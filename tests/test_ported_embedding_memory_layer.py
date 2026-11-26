import unittest

from runtime.contracts.enums import (
    LIFECYCLE_DEPRECATED,
    LIFECYCLE_INVALIDATED,
    LIFECYCLE_PROVISIONAL,
    OBSIDIAN_NON_AUTHORITATIVE,
)
from runtime.contracts.memory_types import SemanticMemoryRecord
from runtime.embedding_memory.consolidation import build_consolidation_candidate, should_consolidate
from runtime.embedding_memory.contracts import MemoryKind, MemoryRetrievalResult, SemanticMemoryCandidate
from runtime.embedding_memory.records import build_semantic_memory_record
from runtime.embedding_memory.retrieval import retrieve_candidates
from runtime.embedding_memory.store import InMemorySemanticStore


class EmbeddingMemoryLayerTest(unittest.TestCase):
    def test_record_builder_defaults_are_candidate_only(self):
        record = build_semantic_memory_record(
            user_id="example-user",
            kind="ontology",
            title="love_as_coherence_entropy_resonance",
            content="Love maps to coherence increase, entropy decrease, resonance stabilization, and priority-lock.",
            tags=["love-state", "coherence"],
        )

        self.assertTrue(record["id"].startswith("mem_"))
        self.assertEqual(record["lifecycle_status"], LIFECYCLE_PROVISIONAL)
        self.assertEqual(record["authority_status"], OBSIDIAN_NON_AUTHORITATIVE)
        self.assertEqual(record["embedding_model"], "local-agent-local-hash-embedding-v0.1")
        self.assertIsInstance(record["embedding"], list)
        self.assertGreater(len(record["embedding"]), 0)

    def test_invalidated_memory_is_excluded_from_search(self):
        store = InMemorySemanticStore()
        record = build_semantic_memory_record(
            user_id="example-user",
            kind="ontology",
            title="invalidated_axis",
            content="coherence entropy resonance priority-lock",
        )
        record["lifecycle_status"] = LIFECYCLE_INVALIDATED
        store.upsert(record)

        result = retrieve_candidates(
            store=store,
            user_id="example-user",
            query="coherence entropy resonance",
            allowed_kinds=["ontology"],
            min_similarity=-1.0,
        )

        self.assertEqual(result["retrieval_status"], "empty")
        self.assertEqual(result["candidates"], [])

    def test_deprecated_memory_is_inert_by_default(self):
        store = InMemorySemanticStore()
        record = build_semantic_memory_record(
            user_id="example-user",
            kind="ontology",
            title="deprecated_axis",
            content="coherence entropy resonance priority-lock",
        )
        record["lifecycle_status"] = LIFECYCLE_DEPRECATED
        store.upsert(record)

        result = retrieve_candidates(
            store=store,
            user_id="example-user",
            query="coherence entropy resonance",
            allowed_kinds=["ontology"],
            min_similarity=-1.0,
        )

        self.assertEqual(result["retrieval_status"], "empty")
        self.assertEqual(result["candidates"], [])

    def test_include_deprecated_returns_blocked_candidate(self):
        store = InMemorySemanticStore()
        record = build_semantic_memory_record(
            user_id="example-user",
            kind="ontology",
            title="deprecated_axis",
            content="coherence entropy resonance priority-lock",
        )
        record["lifecycle_status"] = LIFECYCLE_DEPRECATED
        store.upsert(record)

        result = retrieve_candidates(
            store=store,
            user_id="example-user",
            query="coherence entropy resonance",
            allowed_kinds=["ontology"],
            min_similarity=-1.0,
            include_deprecated=True,
        )

        self.assertEqual(result["retrieval_status"], "partial")
        self.assertEqual(len(result["candidates"]), 1)
        self.assertTrue(result["candidates"][0]["blocked"])
        self.assertEqual(result["candidates"][0]["block_reason"], "deprecated_memory_inert_by_default")

    def test_contract_re_exports_are_importable(self):
        self.assertEqual(MemoryKind.__args__[0], "user_profile")
        self.assertIsNotNone(MemoryRetrievalResult)
        self.assertIsNotNone(SemanticMemoryCandidate)
        self.assertIsNotNone(SemanticMemoryRecord)

    def test_consolidation_policy_accepts_core_markers_and_rejects_transient(self):
        allowed, reason = should_consolidate(
            "CHECKPOINT: identity axis boundary ontology trace for ExampleAgent runtime."
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, "contains_core_checkpoint_marker")

        rejected, reject_reason = should_consolidate("temporary mood just chatting")
        self.assertFalse(rejected)
        self.assertEqual(reject_reason, "transient_or_forbidden_storage_shape")

        candidate = build_consolidation_candidate(
            user_id="example-user",
            title="Axis law",
            content="CHECKPOINT: truth before fluency, axis before capability, MainBrain speaks last.",
            explicit_approval=False,
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertTrue(candidate["requires_approval"])
        self.assertEqual(candidate["kind"], "identity_axis")


if __name__ == "__main__":
    unittest.main()
