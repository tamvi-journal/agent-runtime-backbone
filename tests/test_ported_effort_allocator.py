import unittest
from typing import get_args

from runtime.allocator.contracts import (
    CognitionTopology,
    EffortLevel,
    MonitorIntensity,
    ReasoningEngine,
    VerificationRequirement,
)
from runtime.allocator.effort_allocator import allocate_effort, evaluate_threshold_tuning_request
from runtime.allocator.telemetry import build_effort_allocator_event


class EffortAllocatorV0Test(unittest.TestCase):
    def test_low_risk_high_stakes_routes_at_least_medium(self):
        request = {
            "task_type": "architecture",
            "active_mode": "design",
            "ambiguity_score": 0.2,
            "risk_score": 0.1,
            "stakes_signal": 0.9,
            "action_required": False,
            "memory_commit_possible": False,
            "disagreement_likelihood": 0.2,
            "mode_confidence": 0.8,
            "verification_gap_estimate": 0.2,
            "high_risk_domain": False,
            "unanswerable_likelihood": 0.1,
            "cue_strength": 0.2,
        }

        decision = allocate_effort(request)

        self.assertIn(decision["effort_level"], {"medium", "high"})
        self.assertGreaterEqual(decision["effort_score"], 2)
        self.assertEqual(decision["risk_score"], 0.1)
        self.assertEqual(decision["stakes_signal"], 0.9)

    def test_compute_pressure_alone_cannot_tune_thresholds_without_failure_distribution(self):
        tuning_request = {
            "reason": "reduce cost and latency",
            "compute_pressure_only": True,
            "failure_distribution_available": False,
            "observed_failure_modes": [],
        }

        result = evaluate_threshold_tuning_request(tuning_request)

        self.assertFalse(result["tuning_allowed"])
        self.assertIn("compute_pressure_only", result["reasons"])
        self.assertIn("failure_distribution_missing", result["reasons"])

    def test_low_stakes_formatting_routes_low(self):
        request = {
            "task_type": "formatting",
            "active_mode": "light_edit",
            "ambiguity_score": 0.1,
            "risk_score": 0.1,
            "stakes_signal": 0.1,
            "action_required": False,
            "memory_commit_possible": False,
            "disagreement_likelihood": 0.1,
            "mode_confidence": 0.95,
            "verification_gap_estimate": 0.1,
            "high_risk_domain": False,
            "unanswerable_likelihood": 0.1,
            "cue_strength": 0.8,
        }

        decision = allocate_effort(request)

        self.assertEqual(decision["effort_level"], "low")
        self.assertLessEqual(decision["effort_score"], 0)

    def test_memory_commit_possible_raises_effort(self):
        request = {
            "task_type": "analysis",
            "active_mode": "memory_sensitive",
            "ambiguity_score": 0.2,
            "risk_score": 0.2,
            "stakes_signal": 0.2,
            "action_required": False,
            "memory_commit_possible": True,
            "disagreement_likelihood": 0.2,
            "mode_confidence": 0.9,
            "verification_gap_estimate": 0.2,
            "high_risk_domain": False,
            "unanswerable_likelihood": 0.1,
            "cue_strength": 0.1,
        }

        decision = allocate_effort(request)

        self.assertGreaterEqual(decision["effort_score"], 2)
        self.assertIn(decision["effort_level"], {"medium", "high"})
        self.assertEqual(decision["memory_commit_status"], "possible")

    def test_allocator_output_is_advisory_only_and_cannot_claim_permission_or_completion(self):
        request = {
            "task_type": "execution",
            "active_mode": "sandbox",
            "ambiguity_score": 0.4,
            "risk_score": 0.6,
            "stakes_signal": 0.6,
            "action_required": True,
            "memory_commit_possible": False,
            "disagreement_likelihood": 0.2,
            "mode_confidence": 0.7,
            "verification_gap_estimate": 0.5,
            "high_risk_domain": False,
            "unanswerable_likelihood": 0.1,
            "cue_strength": 0.2,
        }

        decision = allocate_effort(request)

        self.assertTrue(decision["advisory_only"])
        self.assertFalse(decision["permission_claimed"])
        self.assertFalse(decision["completion_claimed"])
        self.assertEqual(decision["permission_decision"], "none")
        self.assertEqual(decision["completion_status"], "not_applicable")
        self.assertNotIn("gate_decision", decision)
        self.assertNotIn("route", decision)
        self.assertNotIn("allowed_toolsets", decision)

    def test_emitted_literals_match_declared_contract_sets(self):
        request = {
            "task_type": "research",
            "active_mode": "deep_read",
            "ambiguity_score": 0.75,
            "risk_score": 0.3,
            "stakes_signal": 0.8,
            "action_required": False,
            "memory_commit_possible": True,
            "disagreement_likelihood": 0.65,
            "mode_confidence": 0.45,
            "verification_gap_estimate": 0.7,
            "high_risk_domain": False,
            "unanswerable_likelihood": 0.4,
            "cue_strength": 0.2,
        }
        decision = allocate_effort(request)

        self.assertIn(decision["effort_level"], get_args(EffortLevel))
        self.assertIn(decision["cognition_topology"], get_args(CognitionTopology))
        self.assertIn(decision["monitor_intensity"], get_args(MonitorIntensity))
        self.assertIn(decision["verification_requirement"], get_args(VerificationRequirement))
        self.assertIn(decision["reasoning_engine"], get_args(ReasoningEngine))

    def test_telemetry_event_builder_shape_and_literals(self):
        request = {
            "task_type": "research",
            "active_mode": "deep_read",
            "ambiguity_score": 0.75,
            "risk_score": 0.3,
            "stakes_signal": 0.8,
            "action_required": False,
            "memory_commit_possible": True,
            "disagreement_likelihood": 0.65,
            "mode_confidence": 0.45,
            "verification_gap_estimate": 0.7,
            "high_risk_domain": False,
            "unanswerable_likelihood": 0.4,
            "cue_strength": 0.2,
        }
        decision = allocate_effort(request)

        event = build_effort_allocator_event(request, decision)

        self.assertEqual(
            set(event.keys()),
            {
                "event",
                "task_type",
                "active_mode",
                "ambiguity_score",
                "risk_score",
                "stakes_signal",
                "action_required",
                "memory_commit_possible",
                "disagreement_likelihood",
                "cue_strength",
                "effort_score",
                "effort_level",
                "cognition_topology",
                "monitor_intensity",
                "verification_requirement",
                "memory_commit_status",
                "reasoning_engine",
                "allocator_reason",
            },
        )
        self.assertEqual(event["event"], "effort_allocator.route")
        self.assertEqual(event["ambiguity_score"], request["ambiguity_score"])
        self.assertEqual(event["risk_score"], request["risk_score"])
        self.assertEqual(event["stakes_signal"], request["stakes_signal"])
        self.assertIn(event["effort_level"], get_args(EffortLevel))
        self.assertIn(event["cognition_topology"], get_args(CognitionTopology))
        self.assertIn(event["monitor_intensity"], get_args(MonitorIntensity))
        self.assertIn(event["verification_requirement"], get_args(VerificationRequirement))
        self.assertIn(event["reasoning_engine"], get_args(ReasoningEngine))


if __name__ == "__main__":
    unittest.main()
