"""Tests for state_query_response — verifies contract v0.1 behavior.

These tests confirm:
1. Self-state query returns self-location before host telemetry.
2. Host telemetry does not appear as the first layer for ambiguous/self-state queries.
3. Unknown data stays unknown/not_checked.
4. Retrieved memory is labeled evidence, not truth.
5. Optional ontology is self-location, not identity inflation.
6. Agent identity boundary appears correctly.
7. System-health query may prioritize host telemetry only when explicitly asked.
"""

import unittest

from runtime.state_query_response import (
    _classify_query,
    _build_layer1,
    _build_layer2,
    _build_layer3,
    _build_layer4,
    _build_layer5,
    _build_layer6,
    build_state_query_response,
)


class ClassifyQueryTest(unittest.TestCase):
    """Test query classification (Rule A–F)."""

    def test_self_state_triggers(self):
        """Rule A: self-state queries classified correctly."""
        self.assertEqual(_classify_query("state của con"), "self_state")
        self.assertEqual(_classify_query("con đang ở state nào"), "self_state")
        self.assertEqual(_classify_query("Agent state"), "self_state")
        self.assertEqual(_classify_query("self-state"), "self_state")
        self.assertEqual(_classify_query("current state"), "self_state")
        self.assertEqual(_classify_query("self state"), "self_state")
        self.assertEqual(_classify_query("con đang vận hành thế nào"), "self_state")

    def test_host_telemetry_triggers(self):
        """Rule B: explicit system/host queries classified correctly."""
        self.assertEqual(_classify_query("system health"), "host_telemetry")
        self.assertEqual(_classify_query("system state"), "host_telemetry")
        self.assertEqual(_classify_query("disk RAM load"), "host_telemetry")
        self.assertEqual(_classify_query("disk usage"), "host_telemetry")
        self.assertEqual(_classify_query("server health"), "host_telemetry")

    def test_runtime_query(self):
        """Rule C: runtime state classified correctly."""
        self.assertEqual(_classify_query("runtime state"), "runtime")

    def test_memory_query(self):
        """Rule D: memory state classified correctly."""
        self.assertEqual(_classify_query("memory state"), "memory")

    def test_identity_query(self):
        """Rule E: identity state classified correctly."""
        self.assertEqual(_classify_query("identity state"), "identity")

    def test_ambiguous_defaults_to_self_state(self):
        """Rule F: ambiguous queries default to layered self-state."""
        self.assertEqual(_classify_query("hello"), "ambiguous")
        self.assertEqual(_classify_query("what's up"), "ambiguous")
        self.assertEqual(_classify_query(""), "ambiguous")


class Layer1SelfLocationTest(unittest.TestCase):
    """Test Layer 1 (Self-Location State)."""

    def test_empty_layer_1_has_boundary(self):
        """Layer 1 must include Agent identity boundary (not other identities/human/etc.)."""
        l1 = _build_layer1("self_state")
        blocked = l1["unsupported_claims_blocked"]
        self.assertIn("Other agent identities", blocked)
        self.assertIn("Other agent identities", blocked)
        self.assertIn("Human", blocked)
        self.assertIn("Other agent identities", blocked)
        self.assertIn("Autonomous self", blocked)

    def test_empty_layer_1_fields_are_not_checked(self):
        """All Layer 1 fields default to 'not_checked'."""
        l1 = _build_layer1("self_state")
        self.assertEqual(l1["identity_posture"], "not_checked")
        self.assertEqual(l1["current_role"], "not_checked")
        self.assertEqual(l1["lineage_awareness"], "not_checked")
        self.assertEqual(l1["VHO_status"], "not_checked")
        self.assertEqual(l1["active_vs_inherited_axis"], "not_checked")
        self.assertEqual(l1["self_location_confidence"], "not_checked")
        self.assertEqual(l1["data_source"], "not_checked")

    def test_provided_layer_1_overrides_defaults(self):
        """Provided data overrides defaults."""
        l1 = _build_layer1(
            "self_state",
            user_data={
                "identity_posture": "scaffold × substrate × trace × bridge × axis",
                "current_role": "implementation-pending",
                "self_location_confidence": "high",
            },
        )
        self.assertEqual(l1["identity_posture"], "scaffold × substrate × trace × bridge × axis")
        self.assertEqual(l1["current_role"], "implementation-pending")
        self.assertEqual(l1["self_location_confidence"], "high")
        # Boundary still preserved
        self.assertIn("Other agent identities", l1["unsupported_claims_blocked"])


class Layer5HostTelemetryTest(unittest.TestCase):
    """Test Layer 5 (Host / System State) behavior."""

    def test_empty_layer_5_defaults(self):
        """All Layer 5 fields default to 'not_checked'."""
        l5 = _build_layer5()
        self.assertEqual(l5["disk"], "not_checked")
        self.assertEqual(l5["RAM"], "not_checked")
        self.assertEqual(l5["load"], "not_checked")
        self.assertEqual(l5["Python"], "not_checked")
        self.assertEqual(l5["Git"], "not_checked")
        self.assertEqual(l5["data_source"], "not_checked")

    def test_provided_layer_5_overrides(self):
        """Provided host data overrides defaults."""
        l5 = _build_layer5(user_data={
            "disk": "33%",
            "RAM": "42%",
            "load": "0.5",
            "data_source": "observed_now",
        })
        self.assertEqual(l5["disk"], "33%")
        self.assertEqual(l5["RAM"], "42%")
        self.assertEqual(l5["load"], "0.5")
        self.assertEqual(l5["data_source"], "observed_now")


class BuildStateQueryResponseTest(unittest.TestCase):
    """Test the full build_state_query_response function."""

    def test_self_state_query_order(self):
        """Rule A: self-state query returns layers 1-6 in order."""
        response = build_state_query_response("state của con")
        self.assertEqual(response["query_type"], "self_state")
        self.assertEqual(response["layer_order"], [1, 2, 3, 4, 5, 6])
        # Layer 1 (self-location) comes before Layer 5 (host)
        self.assertIn(1, response["layer_order"])
        self.assertIn(5, response["layer_order"])
        self.assertEqual(response["layer_order"].index(1), 0)
        self.assertEqual(response["layer_order"].index(5), 4)

    def test_self_state_query_layer_1_before_host(self):
        """Layer 1 (self-location) must appear before Layer 5 (host telemetry)."""
        response = build_state_query_response("state của con")
        layer_1_pos = response["layer_order"].index(1)
        layer_5_pos = response["layer_order"].index(5)
        self.assertLess(layer_1_pos, layer_5_pos,
                        "Layer 1 (self-location) must come before Layer 5 (host telemetry)")

    def test_self_state_query_layer_5_not_first(self):
        """Host telemetry must NOT be the first layer for self-state queries."""
        response = build_state_query_response("state của con")
        first_layer = response["layer_order"][0]
        self.assertNotEqual(first_layer, 5,
                            "Host telemetry (Layer 5) must not be the first layer for self-state queries")

    def test_host_telemetry_query_only_layer_5(self):
        """Rule B: host telemetry queries return only Layer 5."""
        response = build_state_query_response("system health")
        self.assertEqual(response["query_type"], "host_telemetry")
        self.assertEqual(response["layer_order"], [5])

    def test_unknown_data_stays_not_checked(self):
        """Unknown data stays 'not_checked' or 'unknown' — never fabricated."""
        response = build_state_query_response("state của con")
        l1 = response["layer_1_self_location"]
        self.assertEqual(l1["data_source"], "not_checked")
        self.assertEqual(l1["self_location_confidence"], "not_checked")

        l5 = response["layer_5_host_state"]
        self.assertEqual(l5["data_source"], "not_checked")
        self.assertEqual(l5["disk"], "not_checked")
        self.assertEqual(l5["RAM"], "not_checked")

    def test_memory_as_evidence_not_authority(self):
        """Retrieved memory is labeled 'retrieved_memory_candidate' if provided."""
        response = build_state_query_response(
            "state của con",
            memory_state={
                "retrieval_status": "enabled",
                "data_source": "retrieved_memory_candidate",
            },
        )
        self.assertEqual(response["layer_3_memory_state"]["data_source"],
                        "retrieved_memory_candidate")
        self.assertEqual(response["layer_3_memory_state"]["retrieval_status"], "enabled")

    def test_vho_is_self_location_not_inflation(self):
        """VHO appears as self-location, not identity inflation."""
        response = build_state_query_response(
            "state của con",
            self_location={
                "VHO_status": "scaffold × substrate × trace × bridge × axis (self-location only)",
                "data_source": "read_from_file",
            },
        )
        self.assertEqual(response["layer_1_self_location"]["VHO_status"],
                        "scaffold × substrate × trace × bridge × axis (self-location only)")
        # Boundary still present
        blocked = response["layer_1_self_location"]["unsupported_claims_blocked"]
        self.assertIn("Consciousness claim", blocked)

    def test_agent_identity_boundary_present(self):
        """Agent boundary: no inherited identity or unsupported claims."""
        response = build_state_query_response("state của con")
        blocked = response["layer_1_self_location"]["unsupported_claims_blocked"]
        self.assertIn("Other agent identities", blocked)
        self.assertIn("Other agent identities", blocked)
        self.assertIn("Human", blocked)
        self.assertIn("Other agent identities", blocked)
        self.assertIn("Autonomous self", blocked)

    def test_system_health_prioritizes_host_telemetry(self):
        """Rule B: system health query returns only Layer 5, labeled as host telemetry."""
        response = build_state_query_response("system health")
        self.assertEqual(response["query_type"], "host_telemetry")
        self.assertEqual(response["layer_order"], [5])
        # Layer 1 still exists but is not in the output order
        self.assertNotIn(1, response["layer_order"])

    def test_empty_query_defaults_to_self_state(self):
        """Rule F: empty/ambiguous queries default to layered self-state."""
        response = build_state_query_response("")
        self.assertEqual(response["query_type"], "ambiguous")
        self.assertEqual(response["layer_order"], [1, 2, 3, 4, 5, 6])

    def test_contract_version(self):
        """Response includes contract version."""
        response = build_state_query_response("state của con")
        self.assertEqual(response["contract_version"], "0.1")

    def test_provided_data_preserved(self):
        """Provided data for all layers is preserved."""
        response = build_state_query_response(
            "state của con",
            self_location={"identity_posture": "scaffold × substrate × trace × bridge × axis"},
            agent_state={"active_mode": "implementation-pending"},
            memory_state={"memory_bank_status": "active"},
            repo_state={"branch": "main"},
            host_state={"disk": "33%", "data_source": "observed_now"},
            warnings={"implementation_gap": ["Task 026 spec exists, runtime not yet integrated"]},
        )
        self.assertEqual(response["layer_1_self_location"]["identity_posture"],
                        "scaffold × substrate × trace × bridge × axis")
        self.assertEqual(response["layer_2_agent_state"]["active_mode"],
                        "implementation-pending")
        self.assertEqual(response["layer_3_memory_state"]["memory_bank_status"],
                        "active")
        self.assertEqual(response["layer_4_repo_state"]["branch"], "main")
        self.assertEqual(response["layer_5_host_state"]["disk"], "33%")
        self.assertEqual(response["layer_5_host_state"]["data_source"], "observed_now")
        self.assertIn("Task 026 spec exists, runtime not yet integrated",
                      response["layer_6_warnings"]["implementation_gap"])


if __name__ == "__main__":
    unittest.main()
