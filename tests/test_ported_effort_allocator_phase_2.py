import importlib
import unittest
from typing import get_args

from runtime.allocator.effort_allocator import allocate_effort


class EffortAllocatorPhase2RedTest(unittest.TestCase):
    def _sample_request(self):
        return {
            "task_type": "architecture",
            "active_mode": "design",
            "ambiguity_score": 0.72,
            "risk_score": 0.35,
            "stakes_signal": 0.88,
            "action_required": False,
            "memory_commit_possible": True,
            "disagreement_likelihood": 0.61,
            "mode_confidence": 0.44,
            "verification_gap_estimate": 0.68,
            "high_risk_domain": False,
            "unanswerable_likelihood": 0.25,
            "cue_strength": 0.15,
        }

    def _sample_decision(self):
        return allocate_effort(self._sample_request())

    def _sample_observed_outcome(self):
        return {
            "observed_outcome": "partial_success",
            "failure_modes": ["stakes_underrated", "recognition_flattening"],
            "meaningful_error": True,
            "wasted_effort": False,
            "human_correction_required": True,
            "completion_reversal": False,
            "memory_error": False,
            "recognition_degradation": True,
            "label_confidence": 0.81,
            "notes": "phase 02 red test fixture",
        }

    def test_outcome_record_contract_exists(self):
        contracts = importlib.import_module("runtime.allocator.contracts")
        self.assertTrue(
            hasattr(contracts, "EffortAllocatorOutcomeRecord"),
            "Missing EffortAllocatorOutcomeRecord contract in runtime.allocator.contracts",
        )
        self.assertTrue(
            hasattr(contracts, "EffortAllocatorEvaluatorLabel"),
            "Missing EffortAllocatorEvaluatorLabel contract in runtime.allocator.contracts",
        )

    def test_failure_mode_literals_exist(self):
        contracts = importlib.import_module("runtime.allocator.contracts")
        self.assertTrue(hasattr(contracts, "FailureMode"), "Missing FailureMode literal contract")

        failure_modes = set(get_args(getattr(contracts, "FailureMode")))
        self.assertEqual(
            failure_modes,
            {
                "false_completion",
                "missed_ambiguity_case",
                "misrouted_low_effort",
                "unnecessary_high_effort",
                "disagreement_suppression",
                "stakes_underrated",
                "verification_underrouted",
                "memory_commit_mistake",
                "recognition_flattening",
                "compute_without_gain",
            },
        )

    def test_evaluator_labels_outcomes_but_cannot_tune_thresholds(self):
        evaluator = importlib.import_module("runtime.allocator.evaluator")
        self.assertTrue(
            hasattr(evaluator, "evaluate_allocator_outcome"),
            "Missing evaluate_allocator_outcome in runtime.allocator.evaluator",
        )

        result = evaluator.evaluate_allocator_outcome(self._sample_decision(), self._sample_observed_outcome())

        self.assertIn("failure_modes", result)
        self.assertTrue(result["failure_modes"])
        self.assertTrue("label_confidence" in result or "label_uncertainty" in result)
        self.assertNotIn("gate_decision", result)
        self.assertNotIn("route_authority", result)
        self.assertNotIn("threshold_update", result)
        self.assertNotIn("threshold_mutation", result)
        self.assertNotIn("config_patch", result)
        self.assertFalse(result.get("permission_claimed", False))
        self.assertFalse(result.get("completion_claimed", False))
        self.assertEqual(result.get("permission_decision", "none"), "none")

    def test_distribution_summary_aggregates_failure_counts_without_recommending_mutation(self):
        contracts = importlib.import_module("runtime.allocator.contracts")
        self.assertTrue(
            hasattr(contracts, "EffortAllocatorDistributionSummary"),
            "Missing EffortAllocatorDistributionSummary contract",
        )

        telemetry = importlib.import_module("runtime.allocator.telemetry")
        self.assertTrue(
            hasattr(telemetry, "build_effort_allocator_distribution_summary_event"),
            "Missing build_effort_allocator_distribution_summary_event in runtime.allocator.telemetry",
        )

    def test_threshold_review_requires_evidence(self):
        contracts = importlib.import_module("runtime.allocator.contracts")
        self.assertTrue(
            hasattr(contracts, "EffortAllocatorThresholdReviewRequest"),
            "Missing EffortAllocatorThresholdReviewRequest contract",
        )

        governance = importlib.import_module("runtime.allocator.governance")
        self.assertTrue(
            hasattr(governance, "review_threshold_request"),
            "Missing review_threshold_request in runtime.allocator.governance",
        )

        request = {
            "event": "effort_allocator.threshold_review_request",
            "window_id": "red-window",
            "requested_change": {
                "field": "verification_gap_estimate_threshold",
                "current": 0.60,
                "proposed": 0.65,
                "direction": "raise",
            },
            "failure_distribution_available": True,
            "sample_size": 12,
            "project_minimum_sample_size": 10,
            "repeated_failure_pattern": True,
            "supporting_failure_modes": ["compute_without_gain"],
            "compute_pressure_only": False,
            "tradeoff_note": "reduce wasted high-effort routing without lowering safety coverage",
            "rollback_path": "restore prior threshold if verification misses rise",
        }

        decision = governance.review_threshold_request(request)
        self.assertIn("decision", decision)
        self.assertIn("reasons", decision)
        self.assertEqual(decision.get("execution_status", "not_applied_phase_02"), "not_applied_phase_02")

    def test_governance_decision_is_offline_only(self):
        contracts = importlib.import_module("runtime.allocator.contracts")
        self.assertTrue(
            hasattr(contracts, "EffortAllocatorGovernanceDecision"),
            "Missing EffortAllocatorGovernanceDecision contract",
        )

        telemetry = importlib.import_module("runtime.allocator.telemetry")
        self.assertTrue(
            hasattr(telemetry, "build_governance_decision_event"),
            "Missing build_governance_decision_event in runtime.allocator.telemetry",
        )

        governance = importlib.import_module("runtime.allocator.governance")
        decision = governance.review_threshold_request(
            {
                "event": "effort_allocator.threshold_review_request",
                "window_id": "offline-only-red",
                "requested_change": {
                    "field": "verification_gap_estimate_threshold",
                    "current": 0.60,
                    "proposed": 0.65,
                    "direction": "raise",
                },
                "failure_distribution_available": True,
                "sample_size": 15,
                "project_minimum_sample_size": 10,
                "repeated_failure_pattern": True,
                "supporting_failure_modes": ["unnecessary_high_effort", "compute_without_gain"],
                "compute_pressure_only": False,
                "tradeoff_note": "tradeoff recorded",
                "rollback_path": "restore old threshold",
            }
        )
        self.assertIn(decision["decision"], {"approved", "rejected"})
        self.assertEqual(decision.get("execution_status", "not_applied_phase_02"), "not_applied_phase_02")
        self.assertNotIn("applied_threshold_change", decision)
        self.assertNotIn("thresholds_written", decision)

    def test_unknown_supporting_failure_mode_causes_governance_rejection(self):
        governance = importlib.import_module("runtime.allocator.governance")
        decision = governance.review_threshold_request(
            {
                "event": "effort_allocator.threshold_review_request",
                "window_id": "unknown-mode-red",
                "requested_change": {
                    "field": "verification_gap_estimate_threshold",
                    "current": 0.60,
                    "proposed": 0.65,
                    "direction": "raise",
                },
                "failure_distribution_available": True,
                "sample_size": 15,
                "project_minimum_sample_size": 10,
                "repeated_failure_pattern": True,
                "supporting_failure_modes": ["unnecessary_high_effort", "not_a_real_failure_mode"],
                "compute_pressure_only": False,
                "tradeoff_note": "tradeoff recorded",
                "rollback_path": "restore old threshold",
            }
        )
        self.assertEqual(decision["decision"], "rejected")
        self.assertIn("unknown_supporting_failure_mode:not_a_real_failure_mode", decision["reasons"])
        self.assertEqual(decision.get("execution_status", "not_applied_phase_02"), "not_applied_phase_02")

    def test_distribution_summary_event_copies_input_maps(self):
        telemetry = importlib.import_module("runtime.allocator.telemetry")
        failure_counts = {"compute_without_gain": 1}
        by_effort_level = {"high": 2}

        event = telemetry.build_effort_allocator_distribution_summary_event(
            window_id="copy-red",
            sample_size=3,
            failure_counts=failure_counts,
            by_effort_level=by_effort_level,
            notes="snapshot test",
        )

        failure_counts["compute_without_gain"] = 99
        by_effort_level["high"] = 77

        self.assertEqual(event["failure_counts"]["compute_without_gain"], 1)
        self.assertEqual(event["by_effort_level"]["high"], 2)

    def test_authority_smuggling_guard(self):
        evaluator = importlib.import_module("runtime.allocator.evaluator")
        result = evaluator.evaluate_allocator_outcome(self._sample_decision(), self._sample_observed_outcome())

        self.assertNotIn("gate_decision", result)
        self.assertEqual(result.get("permission_decision", "none"), "none")
        self.assertFalse(result.get("completion_claimed", False))
        self.assertFalse(result.get("permission_claimed", False))
        self.assertNotIn("route_authority", result)
        self.assertNotIn("threshold_mutation", result)


if __name__ == "__main__":
    unittest.main()
