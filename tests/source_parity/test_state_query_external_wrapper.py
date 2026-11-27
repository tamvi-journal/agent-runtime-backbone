"""Tests for state_query_external_wrapper — prototype v0.1.

These tests verify:
1. Query classification (Rules A–F) works correctly.
2. Non-state detection (casual, tool, general) works correctly.
3. handle_external_state_query returns correct structure for state queries.
4. handle_external_state_query returns correct structure for non-state queries.
5. External facts are preserved in the state response.
6. Missing facts render as not_checked/unknown.
7. The wrapper does NOT connect into the runtime authority chain.
8. Non-state queries are NOT hijacked — user_text is preserved for pass-through.
"""

import unittest

from runtime.state_query_external_wrapper import (
    CASUAL_MARKERS,
    TOOL_MARKERS,
    classify_query,
    is_state_query,
    handle_external_state_query,
    QueryType,
    NonStateCategory,
)


# ---------------------------------------------------------------------------
# classify_query tests
# ---------------------------------------------------------------------------

class ClassifyQueryTest(unittest.TestCase):
    """Test query classification (Rules A–F) and non-state detection."""

    # --- Rules A–F (state queries) ---

    def test_rule_a_self_state_vietnamese(self):
        """Rule A: Vietnamese self-state triggers."""
        qtype, nsc = classify_query("state của con")
        self.assertEqual(qtype, "self_state")
        self.assertIsNone(nsc)

        qtype, nsc = classify_query("con đang ở state nào")
        self.assertEqual(qtype, "self_state")
        self.assertIsNone(nsc)

        qtype, nsc = classify_query("state con")
        self.assertEqual(qtype, "self_state")
        self.assertIsNone(nsc)

    def test_rule_a_self_state_english(self):
        """Rule A: English self-state triggers."""
        qtype, nsc = classify_query("Agent state")
        self.assertEqual(qtype, "self_state")
        self.assertIsNone(nsc)

        qtype, nsc = classify_query("self-state")
        self.assertEqual(qtype, "self_state")
        self.assertIsNone(nsc)

        qtype, nsc = classify_query("current state")
        self.assertEqual(qtype, "self_state")
        self.assertIsNone(nsc)

        qtype, nsc = classify_query("self state")
        self.assertEqual(qtype, "self_state")
        self.assertIsNone(nsc)

        qtype, nsc = classify_query("con đang vận hành thế nào")
        self.assertEqual(qtype, "self_state")
        self.assertIsNone(nsc)

    def test_rule_b_host_telemetry(self):
        """Rule B: explicit system/host queries."""
        for kw in ["system health", "system state", "disk RAM load",
                     "disk usage", "server health", "host telemetry"]:
            qtype, nsc = classify_query(kw)
            self.assertEqual(qtype, "host_telemetry",
                             f"Expected host_telemetry for '{kw}', got {qtype}")
            self.assertIsNone(nsc)

    def test_rule_c_runtime(self):
        """Rule C: runtime state."""
        qtype, nsc = classify_query("runtime state")
        self.assertEqual(qtype, "runtime")
        self.assertIsNone(nsc)

    def test_rule_d_memory(self):
        """Rule D: memory state."""
        qtype, nsc = classify_query("memory state")
        self.assertEqual(qtype, "memory")
        self.assertIsNone(nsc)

    def test_rule_e_identity(self):
        """Rule E: identity state."""
        qtype, nsc = classify_query("identity state")
        self.assertEqual(qtype, "identity")
        self.assertIsNone(nsc)

    def test_rule_f_ambiguous_state(self):
        """Rule F: empty queries default to layered self-state (ambiguous, no non_state)."""
        qtype, nsc = classify_query("")
        self.assertEqual(qtype, "ambiguous")
        self.assertIsNone(nsc)

    def test_general_query_ambiguous_non_state(self):
        """General queries (Rule F) are 'ambiguous' but classified as non-state."""
        # "hello world" matches the casual marker "hello" → casual (not general)
        qtype, nsc = classify_query("hello world")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "casual")

        # A true general query (no casual/tool/state match) → general_query
        qtype, nsc = classify_query("what is the meaning of life")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "general_query")

    # --- Non-state detection ---

    def test_casual_markers_vietnamese(self):
        """Casual Vietnamese markers are classified as non-state."""
        for marker in ["cảm ơn", "chào", "đồng ý", "hay quá", "thú vị"]:
            qtype, nsc = classify_query(marker)
            # Non-state queries still return 'ambiguous' as the query type
            # (Rule F), but the non_state_category distinguishes them.
            self.assertEqual(qtype, "ambiguous",
                             f"Expected 'ambiguous' for casual marker '{marker}', got {qtype}")
            self.assertEqual(nsc, "casual",
                             f"Expected 'casual' for '{marker}', got {nsc}")

    def test_casual_markers_english(self):
        """Casual English markers are classified as non-state."""
        for marker in ["thanks", "hello", "hi", "hey", "ok", "okay",
                        "wow"]:
            qtype, nsc = classify_query(marker)
            # Non-state queries still return 'ambiguous' as the query type
            # (Rule F), but the non_state_category distinguishes them.
            self.assertEqual(qtype, "ambiguous",
                             f"Expected 'ambiguous' for casual marker '{marker}', got {qtype}")
            self.assertEqual(nsc, "casual",
                             f"Expected 'casual' for '{marker}', got {nsc}")

    def test_tool_request_markers(self):
        """Tool/delegation markers are classified as non-state."""
        for marker in ["kiểm tra", "check ", "search ", "find ", "run ",
                        "execute", "delegate", "schedule", "create ",
                        "build ", "write ", "read ", "list ", "git",
                        "docker", "python", "bash", "install", "setup",
                        "navigate", "click", "type", "press", "scroll",
                        "terminal", "script", "calculate", "analyze",
                        "review", "generate", "send", "message",
                        "memory", "task", "todo", "cronjob", "subagent"]:
            qtype, nsc = classify_query(marker)
            # Non-state queries return 'ambiguous' as the query type,
            # but non_state_category distinguishes them.
            self.assertEqual(qtype, "ambiguous",
                             f"Expected 'ambiguous' for tool marker '{marker}', got {qtype}")
            self.assertEqual(nsc, "tool_request",
                             f"Expected 'tool_request' for '{marker}', got {nsc}")

    def test_general_query_pass_through(self):
        """General reasoning queries are classified as non-state."""
        qtype, nsc = classify_query("what is the meaning of life")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "general_query")

        qtype, nsc = classify_query("explain quantum computing")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "general_query")


# ---------------------------------------------------------------------------
# is_state_query tests
# ---------------------------------------------------------------------------

class IsStateQueryTest(unittest.TestCase):
    """Test the is_state_query convenience function."""

    def test_state_queries_return_true(self):
        """All state query types return True."""
        for query in [
            "state của con", "self-state", "current state",
            "system health", "runtime state", "memory state",
            "identity state", "",
        ]:
            self.assertTrue(is_state_query(query),
                            f"Expected True for state query '{query}'")

    def test_non_state_queries_return_false(self):
        """All non-state queries return False."""
        for query in [
            "thanks", "hello", "kiểm tra", "check", "git status",
            "what is the meaning of life", "hello world",
        ]:
            self.assertFalse(is_state_query(query),
                             f"Expected False for non-state query '{query}'")


# ---------------------------------------------------------------------------
# handle_external_state_query tests
# ---------------------------------------------------------------------------

class HandleExternalStateQueryTest(unittest.TestCase):
    """Test the main wrapper API."""

    def test_state_query_returns_correct_structure(self):
        """State query returns handled=True, route='state_query', boundary_note."""
        result = handle_external_state_query("state của con")
        self.assertTrue(result["handled"])
        self.assertEqual(result["route"], "state_query")
        self.assertIn("query_type", result)
        self.assertIn("response", result)
        self.assertEqual(result["query_type"], "self_state")
        self.assertIn("boundary_note", result)
        self.assertIn("external wrapper only", result["boundary_note"])
        self.assertIn("layer_order", result["response"])
        self.assertIn("contract_version", result["response"])
        self.assertEqual(result["response"]["contract_version"], "0.1")

    def test_non_state_query_returns_pass_through_structure(self):
        """Non-state query returns handled=False, route='pass_through', response=None."""
        result = handle_external_state_query("thanks")
        self.assertFalse(result["handled"])
        self.assertEqual(result["route"], "pass_through")
        self.assertIn("non_state_category", result)
        self.assertEqual(result["non_state_category"], "casual")
        self.assertIn("user_text", result)
        self.assertEqual(result["user_text"], "thanks")
        self.assertIsNone(result["response"])
        self.assertIn("boundary_note", result)
        self.assertIn("pass to normal", result["boundary_note"])

    def test_non_state_preserves_original_text(self):
        """Non-state queries preserve the original user_text for pass-through."""
        original = "kiểm tra task fixture-027 tiến độ đâu rồi"
        result = handle_external_state_query(original)
        self.assertFalse(result["handled"])
        self.assertEqual(result["user_text"], original)

    def test_self_state_response_preserves_external_facts(self):
        """Provided external facts are preserved in the state response."""
        result = handle_external_state_query(
            "state của con",
            self_location={
                "identity_posture": "scaffold × substrate × trace × bridge × axis",
                "current_role": "implementation-pending",
                "self_location_confidence": "high",
                "data_source": "read_from_file",
            },
            agent_state={
                "active_mode": "idle",
                "data_source": "inferred_from_context",
            },
            memory_state={
                "memory_bank_status": "active",
                "retrieval_status": "enabled",
                "data_source": "retrieved_memory_candidate",
            },
            repo_state={
                "active_repo": "agent-workspace",
                "branch": "main",
                "data_source": "observed_now",
            },
            host_state={
                "disk": "33%",
                "RAM": "42%",
                "data_source": "observed_now",
            },
            warnings={
                "implementation_gap": ["Task 026 spec exists, runtime not yet integrated"],
                "data_source": "inferred_from_context",
            },
        )
        self.assertTrue(result["handled"])
        self.assertEqual(result["route"], "state_query")
        response = result["response"]

        # Layer 1: provided facts preserved
        self.assertEqual(
            response["layer_1_self_location"]["identity_posture"],
            "scaffold × substrate × trace × bridge × axis"
        )
        self.assertEqual(
            response["layer_1_self_location"]["current_role"],
            "implementation-pending"
        )
        self.assertEqual(
            response["layer_1_self_location"]["self_location_confidence"],
            "high"
        )
        self.assertEqual(
            response["layer_1_self_location"]["data_source"],
            "read_from_file"
        )

        # Layer 2: provided facts preserved
        self.assertEqual(
            response["layer_2_agent_state"]["active_mode"],
            "idle"
        )
        self.assertEqual(
            response["layer_2_agent_state"]["data_source"],
            "inferred_from_context"
        )

        # Layer 3: provided facts preserved
        self.assertEqual(
            response["layer_3_memory_state"]["memory_bank_status"],
            "active"
        )
        self.assertEqual(
            response["layer_3_memory_state"]["data_source"],
            "retrieved_memory_candidate"
        )

        # Layer 4: provided facts preserved
        self.assertEqual(
            response["layer_4_repo_state"]["active_repo"],
            "agent-workspace"
        )
        self.assertEqual(
            response["layer_4_repo_state"]["data_source"],
            "observed_now"
        )

        # Layer 5: provided facts preserved
        self.assertEqual(
            response["layer_5_host_state"]["disk"],
            "33%"
        )
        self.assertEqual(
            response["layer_5_host_state"]["data_source"],
            "observed_now"
        )

        # Layer 6: provided facts preserved
        self.assertIn(
            "Task 026 spec exists, runtime not yet integrated",
            response["layer_6_warnings"]["implementation_gap"]
        )

    def test_missing_facts_render_as_not_checked(self):
        """Missing facts render as not_checked/unknown — never fabricated."""
        result = handle_external_state_query("state của con")
        response = result["response"]
        self.assertTrue(result["handled"])
        self.assertEqual(result["route"], "state_query")

        # All layers should have default not_checked values when no facts provided
        self.assertEqual(
            response["layer_1_self_location"]["data_source"],
            "not_checked"
        )
        self.assertEqual(
            response["layer_2_agent_state"]["data_source"],
            "not_checked"
        )
        self.assertEqual(
            response["layer_3_memory_state"]["data_source"],
            "not_checked"
        )
        self.assertEqual(
            response["layer_4_repo_state"]["data_source"],
            "not_checked"
        )
        self.assertEqual(
            response["layer_5_host_state"]["data_source"],
            "not_checked"
        )
        self.assertEqual(
            response["layer_6_warnings"]["data_source"],
            "not_checked"
        )

    def test_identity_boundary_always_present(self):
        """Identity boundary is always present in Layer 1, even with provided facts."""
        result = handle_external_state_query(
            "state của con",
            self_location={
                "identity_posture": "custom posture",
            },
        )
        response = result["response"]
        self.assertTrue(result["handled"])
        self.assertEqual(result["route"], "state_query")
        blocked = response["layer_1_self_location"]["unsupported_claims_blocked"]
        self.assertIn("Other agent identities", blocked)
        self.assertIn("Other agent identities", blocked)
        self.assertIn("Human", blocked)
        self.assertIn("Consciousness claim", blocked)

    def test_host_telemetry_query(self):
        """Host telemetry query returns handled=True, route='state_query'."""
        result = handle_external_state_query("system health")
        self.assertTrue(result["handled"])
        self.assertEqual(result["route"], "state_query")
        self.assertEqual(result["query_type"], "host_telemetry")
        self.assertEqual(result["response"]["layer_order"], [5])

    def test_empty_query_returns_ambiguous_state(self):
        """Empty query is classified as ambiguous (state query, not non-state)."""
        result = handle_external_state_query("")
        self.assertTrue(result["handled"])
        self.assertEqual(result["route"], "state_query")
        self.assertEqual(result["query_type"], "ambiguous")

    def test_wrapper_does_not_connect_to_runtime_authority(self):
        """The wrapper is a pure function — no side effects, no runtime calls."""
        # This test verifies the wrapper's structure:
        # - No imports from runtime/core/
        # - No imports from runtime/monitor/
        # - No imports from runtime/mainbrain/
        # - No imports from runtime/embedding_memory/
        # - No shell calls
        # - No memory writes
        #
        # The only import is from runtime.state_query_response
        # (which is the helper, not the authority chain).
        import runtime.state_query_external_wrapper as wrapper
        import inspect

        source = inspect.getsource(wrapper)
        forbidden_imports = [
            "from runtime.core.",
            "from runtime.monitor",
            "from runtime.mainbrain",
            "from runtime.embedding_memory",
            "import subprocess",
            "import os.system",
            "import shutil",
        ]
        for forbidden in forbidden_imports:
            self.assertNotIn(forbidden, source,
                             f"Wrapper should not import: {forbidden}")

    def test_wrapper_does_not_collect_telemetry(self):
        """The wrapper does not call shell or collect host telemetry."""
        import runtime.state_query_external_wrapper as wrapper
        import inspect

        source = inspect.getsource(wrapper)
        forbidden_calls = [
            "subprocess",
            "os.popen",
            "os.system",
            "psutil",
            "ps.",
            "df",
            "free",
            "nproc",
            "uname",
        ]
        for call in forbidden_calls:
            self.assertNotIn(call, source,
                             f"Wrapper should not call: {call}")

    def test_wrapper_does_not_write_memory(self):
        """The wrapper does not write to any memory system."""
        import runtime.state_query_external_wrapper as wrapper
        import inspect

        source = inspect.getsource(wrapper)
        forbidden = [
            "memory.write",
            "memory.save",
            "memory.update",
            "memory.insert",
            "memory.append",
            "hindsight_retain",
            "hindsight",
        ]
        for call in forbidden:
            self.assertNotIn(call, source,
                             f"Wrapper should not write memory: {call}")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class EdgeCasesTest(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_case_insensitive_classification(self):
        """Classification is case-insensitive."""
        qtype1, nsc1 = classify_query("STATE CỦA CON")
        qtype2, nsc2 = classify_query("state của con")
        self.assertEqual(qtype1, qtype2)
        self.assertEqual(nsc1, nsc2)

    def test_partial_match(self):
        """Partial matches within a keyword should NOT trigger."""
        # "state" alone should not match "state của con"
        qtype, nsc = classify_query("state")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "general_query")

    def test_non_state_preserves_user_text_exactly(self):
        """Non-state queries preserve the exact original text."""
        original = "Tôi muốn hỏi chuyện này"
        result = handle_external_state_query(original)
        self.assertFalse(result["handled"])
        self.assertEqual(result["route"], "pass_through")
        self.assertEqual(result["user_text"], original)

    def test_all_layers_present_in_state_response(self):
        """State response always includes all 6 layers."""
        result = handle_external_state_query("state của con")
        response = result["response"]
        self.assertIn("layer_1_self_location", response)
        self.assertIn("layer_2_agent_state", response)
        self.assertIn("layer_3_memory_state", response)
        self.assertIn("layer_4_repo_state", response)
        self.assertIn("layer_5_host_state", response)
        self.assertIn("layer_6_warnings", response)

    def test_non_state_response_has_no_response_field(self):
        """Non-state responses have response=None (not absent)."""
        result = handle_external_state_query("thanks")
        self.assertIsNone(result["response"])
        self.assertIn("user_text", result)

    def test_none_facts_are_handled_gracefully(self):
        """All None facts are handled gracefully (defaults to not_checked)."""
        result = handle_external_state_query(
            "state của con",
            self_location=None,
            agent_state=None,
            memory_state=None,
            repo_state=None,
            host_state=None,
            warnings=None,
        )
        self.assertTrue(result["handled"])
        self.assertEqual(result["route"], "state_query")
        self.assertEqual(result["query_type"], "self_state")
        response = result["response"]
        self.assertEqual(
            response["layer_1_self_location"]["data_source"],
            "not_checked"
        )


class MarkerAuditTest(unittest.TestCase):
    """Test marker constants for emptiness and classification regression."""

    def test_marker_lists_no_empty_strings(self):
        """Verify no marker in TOOL_MARKERS or CASUAL_MARKERS is empty after .strip()."""
        for name, markers in [
            ("TOOL_MARKERS", TOOL_MARKERS),
            ("CASUAL_MARKERS", CASUAL_MARKERS),
        ]:
            for i, marker in enumerate(markers):
                self.assertTrue(
                    marker.strip(),
                    f"{name}[{i}] is empty after strip(): {repr(marker)}"
                )

    def test_general_query_returns_ambiguous_general(self):
        """True general queries return ('ambiguous', 'general_query'), not casual."""
        qtype, nsc = classify_query("what is the meaning of life")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "general_query")

        qtype, nsc = classify_query("explain quantum computing")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "general_query")

        qtype, nsc = classify_query("random non state sentence")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "general_query")

    def test_casual_query_returns_casual(self):
        """Casual queries like 'thanks' return ('ambiguous', 'casual')."""
        qtype, nsc = classify_query("thanks")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "casual")

        qtype, nsc = classify_query("cảm ơn")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "casual")

        qtype, nsc = classify_query("chào")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "casual")

        qtype, nsc = classify_query("ok")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "casual")

        qtype, nsc = classify_query("bánh mì ngon không")
        self.assertEqual(qtype, "ambiguous")
        self.assertEqual(nsc, "general_query")

    def test_boundary_note_present_in_both_paths(self):
        """boundary_note is present in both state and non-state responses."""
        state_result = handle_external_state_query("state của con")
        self.assertIn("boundary_note", state_result)
        self.assertIn("external wrapper only", state_result["boundary_note"])

        non_state_result = handle_external_state_query("xin chào")
        self.assertIn("boundary_note", non_state_result)
        self.assertIn("pass to normal", non_state_result["boundary_note"])


if __name__ == "__main__":
    unittest.main()
