import inspect
from copy import deepcopy
from pathlib import Path
import unittest

from runtime.retrieval_candidate_context import build_retrieval_candidate_context


class RetrievalCandidateContextTest(unittest.TestCase):
    def _base_candidate(self, **overrides):
        candidate = {
            "candidate_id": "cand_001",
            "memory_id": "mem_001",
            "record_type": "event",
            "content": "user said retrieval should be candidate-only",
            "impact": "avoid authority drift",
            "source": "read_from_file",
            "confidence": 0.91,
            "authority_status": "candidate",
            "lifecycle_status": "active",
            "evidence_handles": ["evidence://1"],
            "relation_handles": ["relation://1"],
            "rank_or_similarity_score": 0.88,
            "task_relevance": "relevant",
            "contradiction_status": "none_known",
        }
        candidate.update(overrides)
        return candidate

    def test_candidate_active_becomes_candidate_context(self):
        packet = build_retrieval_candidate_context("query", [self._base_candidate()])
        self.assertEqual(packet["candidates"][0]["allowed_use"], "candidate_context")
        self.assertEqual(packet["candidates"][0]["blocked_status"], "allowed")
        self.assertEqual(packet["candidates"][0]["retrieval_note"], "retrieval candidates only; not truth by itself")

    def test_canonical_active_becomes_candidate_context_after_relevance_check(self):
        packet = build_retrieval_candidate_context(
            "query",
            [self._base_candidate(authority_status="canonical", task_relevance="relevant")],
        )
        self.assertEqual(packet["candidates"][0]["allowed_use"], "candidate_context")
        self.assertEqual(packet["candidates"][0]["task_relevance"], "relevant")

    def test_deprecated_inert_becomes_historical_comparison_only(self):
        packet = build_retrieval_candidate_context(
            "query",
            [self._base_candidate(authority_status="deprecated", lifecycle_status="inert")],
        )
        self.assertEqual(packet["candidates"][0]["allowed_use"], "historical_comparison_only")
        self.assertEqual(packet["candidates"][0]["blocked_status"], "inert")

    def test_invalidated_blocked_is_separated_from_candidates(self):
        packet = build_retrieval_candidate_context(
            "query",
            [self._base_candidate(authority_status="invalidated", lifecycle_status="blocked")],
        )
        self.assertEqual(packet["blocked_candidates"][0]["allowed_use"], "blocked_do_not_use")
        self.assertEqual(packet["blocked_candidates"][0]["blocked_status"], "blocked")
        self.assertEqual(packet["candidates"], [])

    def test_unknown_source_forces_review_before_use(self):
        packet = build_retrieval_candidate_context(
            "query",
            [self._base_candidate(source="unknown")],
        )
        self.assertEqual(packet["candidates"][0]["allowed_use"], "review_before_use")
        self.assertEqual(packet["candidates"][0]["blocked_status"], "review_required")

    def test_retrieval_note_is_always_present(self):
        packet = build_retrieval_candidate_context("query", [self._base_candidate()])
        self.assertEqual(packet["retrieval_note"], "retrieval candidates only; not truth by itself")
        self.assertEqual(packet["candidates"][0]["retrieval_note"], "retrieval candidates only; not truth by itself")

    def test_blocked_candidates_are_kept_separate(self):
        packet = build_retrieval_candidate_context(
            "query",
            [
                self._base_candidate(candidate_id="cand_1"),
                self._base_candidate(candidate_id="cand_2", authority_status="invalidated", lifecycle_status="blocked"),
            ],
        )
        self.assertEqual(len(packet["candidates"]), 1)
        self.assertEqual(len(packet["blocked_candidates"]), 1)
        self.assertEqual(packet["blocked_candidates"][0]["candidate_id"], "cand_2")

    def test_input_candidates_are_not_mutated(self):
        raw = [self._base_candidate()]
        original = deepcopy(raw)
        build_retrieval_candidate_context("query", raw)
        self.assertEqual(raw, original)

    def test_contradiction_status_is_preserved(self):
        packet = build_retrieval_candidate_context(
            "query",
            [self._base_candidate(contradiction_status="needs_review")],
        )
        self.assertEqual(packet["candidates"][0]["contradiction_status"], "needs_review")
        self.assertEqual(packet["contradiction_notes"][0]["contradiction_status"], "needs_review")

    def test_packet_contains_no_truth_or_completion_claim_fields(self):
        packet = build_retrieval_candidate_context("query", [self._base_candidate()])
        forbidden_keys = {"truth_status", "completion_status", "completed", "completion", "truth"}
        self.assertTrue(forbidden_keys.isdisjoint(packet.keys()))
        self.assertTrue(forbidden_keys.isdisjoint(packet["candidates"][0].keys()))

    def test_no_forbidden_imports_in_helper_source(self):
        source = Path("runtime/retrieval_candidate_context.py").read_text(encoding="utf-8")
        forbidden = [
            "runtime.embedding_memory",
            "runtime.mainbrain",
            "runtime.monitor",
            "runtime.core.gate",
            "runtime.core.verification",
            "subprocess",
            "os.system",
        ]
        for item in forbidden:
            self.assertNotIn(item, source)

    def test_no_shell_or_memory_write_behavior_in_helper_source(self):
        source = inspect.getsource(__import__("runtime.retrieval_candidate_context", fromlist=["*"]))
        forbidden = [
            "write_text(",
            "write_bytes(",
            "terminal(",
            "shell",
            "query_database",
            "memory_store",
            "os.system",
            "subprocess",
        ]
        for item in forbidden:
            self.assertNotIn(item, source)


if __name__ == "__main__":
    unittest.main()
