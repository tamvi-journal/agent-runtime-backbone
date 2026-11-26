from __future__ import annotations

"""Pure routing-decision to envelope builder.

Builder may create the envelope, but Preflight Guard decides whether it can run.
Workflow network ≠ runtime network.
This module only builds a WorkerInvocationEnvelope; it does not execute workers,
call Controlled Invocation, call Preflight Guard, or approve execution.
"""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

WORKER_ID = "repo_research_worker"
WORKER_TYPE = "read_only_repo_research"
DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"
DEFAULT_CREATED_AT = DEFAULT_GENERATED_AT
DEFAULT_INVOCATION_ID = "inv-routing-envelope"
WORKFLOW_NETWORK_VS_RUNTIME_NETWORK = "Workflow network ≠ runtime network."

SUPPORTED_DECISION = "route_repo_research_worker"
SUPPORTED_REQUESTED_BY = {"mainbrain", "agent", "approved_runtime_component"}
SUPPORTED_SELECTED_WORKER = {"worker_id": WORKER_ID, "worker_type": WORKER_TYPE}
SUPPORTED_INVOCATION_PURPOSE = "candidate_repo_evidence"

ALLOWED_TOOLS = ["filesystem_read", "repo_scoped_read"]
FORBIDDEN_TOOLS = [
    "shell",
    "network",
    "browser",
    "download",
    "package_install",
    "git_write",
    "memory_write",
    "external_write",
]
AUTO_ALLOWED_ACTIONS = ["read_scoped_files", "collect_candidate_evidence"]
APPROVAL_REQUIRED_ACTIONS = [
    "repo_write_candidate",
    "repo_mutation",
    "external_read",
    "external_write",
    "memory_mutation",
    "model_provider_change",
    "delegated_subagent",
    "hermes_subprocess",
]
BLOCKED_ACTIONS = [
    "money_touching",
    "trading",
    "withdrawal",
    "download_and_execute",
    "arbitrary_code_execution",
    "worker_self_approval",
    "worker_self_invocation",
    "bypass_gate",
    "bypass_verification",
    "bypass_governance",
]
MODEL_PROVIDER_POLICY = {"visibility": "not_visible_to_runtime", "change_requested": False}
MEMORY_CONTEXT_POLICY = {"mode": "no_memory_write", "retrieval_context_allowed": False}
VERIFICATION_EXPECTATION = {"completion_authority": "verification_only", "worker_may_claim_completion": False}
GOVERNANCE_EXPECTATION = {"governance_authority": "governance_only", "worker_may_approve_governance": False}
OUTPUT_CONTRACT = {"type": "WorkerOutputPacket", "candidate_only": True}
RETURN_PATH = {"target": "MainBrain", "mode": "candidate_contribution"}
ESCALATION_POLICY = {"gate_required_for_side_effects": True, "approval_required_actions_route_to_gate": True}
ABORT_CONDITIONS = [
    "invalid_envelope",
    "blocked_action",
    "missing_input_scope",
    "unsafe_path",
    "network_requested",
    "money_touching_requested",
    "memory_mutation_requested",
]


def _copy_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    return None


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return []


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _lower_text(value: Any) -> str:
    return _text(value).lower()


def _has_path_traversal_marker(path_value: Any) -> bool:
    path_text = _text(path_value).replace("\\", "/")
    if not path_text:
        return False
    return any(part == ".." for part in path_text.split("/"))


def _combined_text(routing_decision: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "decision",
        "invocation_purpose",
        "next_step",
        "generated_at",
    ):
        text = _lower_text(routing_decision.get(key))
        if text:
            parts.append(text)
    for key in ("reasons", "limitations", "blocked_reasons"):
        for item in _as_list(routing_decision.get(key)):
            text = _lower_text(item)
            if text:
                parts.append(text)
    selected_worker = routing_decision.get("selected_worker")
    if isinstance(selected_worker, Mapping):
        for key, value in selected_worker.items():
            text = _lower_text(value)
            if text:
                parts.append(f"{_text(key)}={text}")
    proposed_input_scope = routing_decision.get("proposed_input_scope")
    if isinstance(proposed_input_scope, Mapping):
        for key, value in proposed_input_scope.items():
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    text = _lower_text(item)
                    if text:
                        parts.append(text)
            else:
                text = _lower_text(value)
                if text:
                    parts.append(text)
    return " ".join(parts)


def _invalid_result(
    task_id: Any,
    reasons: list[str],
    limitations: list[str],
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "decision": "invalid_routing_decision",
        "invocation_id": None,
        "envelope": None,
        "reasons": list(reasons),
        "limitations": list(limitations),
        "generated_at": generated_at,
    }


def _blocked_result(
    task_id: Any,
    reasons: list[str],
    limitations: list[str],
    *,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "decision": "blocked",
        "invocation_id": None,
        "envelope": None,
        "reasons": list(reasons),
        "limitations": list(limitations),
        "generated_at": generated_at,
    }


def _build_envelope(
    routing_decision: Mapping[str, Any],
    *,
    requested_by: str,
    invocation_id: str,
    created_at: str,
) -> dict[str, Any]:
    proposed_input_scope = _copy_mapping(routing_decision["proposed_input_scope"]) or {}
    paths_allowed = list(proposed_input_scope.get("paths_allowed", []))
    paths_excluded = list(proposed_input_scope.get("paths_excluded", []))
    research_question = proposed_input_scope.get("research_question")
    max_files = proposed_input_scope.get("max_files")
    max_bytes_per_file = proposed_input_scope.get("max_bytes_per_file")

    return {
        "invocation_id": invocation_id,
        "task_id": routing_decision.get("task_id"),
        "requested_by": requested_by,
        "worker_id": WORKER_ID,
        "worker_type": WORKER_TYPE,
        "invocation_purpose": _text(routing_decision.get("invocation_purpose")) or SUPPORTED_INVOCATION_PURPOSE,
        "input_scope": {
            "paths_allowed": paths_allowed,
            "paths_excluded": paths_excluded,
            "research_question": research_question,
            "max_files": max_files,
            "max_bytes_per_file": max_bytes_per_file,
        },
        "permission_class": "read_only",
        "security_profile": "repo_read_only_no_network",
        "execution_surface": "direct_tool",
        "allowed_tools": list(ALLOWED_TOOLS),
        "forbidden_tools": list(FORBIDDEN_TOOLS),
        "auto_allowed_actions": list(AUTO_ALLOWED_ACTIONS),
        "approval_required_actions": list(APPROVAL_REQUIRED_ACTIONS),
        "blocked_actions": list(BLOCKED_ACTIONS),
        "side_effect_class": "repo_read",
        "money_touching": False,
        "external_mutation": False,
        "network_access": False,
        "shell_access": False,
        "model_provider_policy": deepcopy(MODEL_PROVIDER_POLICY),
        "memory_context_policy": deepcopy(MEMORY_CONTEXT_POLICY),
        "verification_expectation": deepcopy(VERIFICATION_EXPECTATION),
        "governance_expectation": deepcopy(GOVERNANCE_EXPECTATION),
        "output_contract": deepcopy(OUTPUT_CONTRACT),
        "return_path": deepcopy(RETURN_PATH),
        "escalation_policy": deepcopy(ESCALATION_POLICY),
        "abort_conditions": list(ABORT_CONDITIONS),
        "created_at": created_at,
    }


def build_worker_invocation_envelope_from_routing_decision(
    routing_decision: Mapping[str, Any],
    *,
    requested_by: str,
    invocation_id: str | None = None,
    created_at: str | None = None,
) -> dict:
    """Convert a routing decision into a WorkerInvocationEnvelope only.

    Builder may create the envelope, but Preflight Guard decides whether it can run.
    """

    if not isinstance(routing_decision, Mapping):
        return _invalid_result(None, ["routing_decision_must_be_mapping"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK])

    decision_data = _copy_mapping(routing_decision) or {}
    task_id = decision_data.get("task_id")
    generated_at = _text(decision_data.get("generated_at")) or DEFAULT_GENERATED_AT
    requested_by_text = _text(requested_by)

    if not requested_by_text:
        return _invalid_result(task_id, ["requested_by_must_be_non_empty_string"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)
    if not isinstance(task_id, str) or not task_id.strip():
        return _invalid_result(task_id, ["task_id_must_be_present"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)

    decision = _text(decision_data.get("decision"))
    if decision != SUPPORTED_DECISION:
        return _invalid_result(task_id, ["unsupported_routing_decision"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)

    selected_worker = decision_data.get("selected_worker")
    if not isinstance(selected_worker, Mapping):
        return _invalid_result(task_id, ["selected_worker_must_be_present"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)
    selected_worker_copy = _copy_mapping(selected_worker) or {}
    if _text(selected_worker_copy.get("worker_id")) != WORKER_ID or _text(selected_worker_copy.get("worker_type")) != WORKER_TYPE:
        return _blocked_result(task_id, ["unknown_or_unsupported_worker"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)

    proposed_input_scope = decision_data.get("proposed_input_scope")
    if not isinstance(proposed_input_scope, Mapping):
        return _invalid_result(task_id, ["proposed_input_scope_must_be_present"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)
    proposed_input_scope_copy = _copy_mapping(proposed_input_scope) or {}

    paths_allowed = proposed_input_scope_copy.get("paths_allowed")
    if not isinstance(paths_allowed, list):
        return _invalid_result(task_id, ["paths_allowed_must_be_a_non_empty_list"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)
    normalized_paths_allowed = list(paths_allowed)
    if not normalized_paths_allowed:
        return _invalid_result(task_id, ["paths_allowed_must_be_a_non_empty_list"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)
    if any(not isinstance(path, str) or not path.strip() for path in normalized_paths_allowed):
        return _invalid_result(task_id, ["paths_allowed_must_contain_non_empty_strings"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)
    if any(_has_path_traversal_marker(path) for path in normalized_paths_allowed):
        return _blocked_result(task_id, ["unsafe_path_traversal_marker_detected"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)

    paths_excluded = proposed_input_scope_copy.get("paths_excluded", [])
    if not isinstance(paths_excluded, list):
        return _invalid_result(task_id, ["paths_excluded_must_be_a_list"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)
    if any(not isinstance(path, str) or not path.strip() for path in paths_excluded):
        return _invalid_result(task_id, ["paths_excluded_must_contain_non_empty_strings"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)

    approval_required = decision_data.get("approval_required")
    if not isinstance(approval_required, bool):
        return _invalid_result(task_id, ["approval_required_must_be_boolean"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)
    if approval_required:
        return _invalid_result(task_id, ["approval_required_must_be_false"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)

    blocked_reasons = decision_data.get("blocked_reasons")
    if not isinstance(blocked_reasons, list):
        return _invalid_result(task_id, ["blocked_reasons_must_be_a_list"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)
    if blocked_reasons:
        return _blocked_result(task_id, ["blocked_reasons_present"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)

    invocation_purpose = _text(decision_data.get("invocation_purpose"))
    if invocation_purpose and invocation_purpose != SUPPORTED_INVOCATION_PURPOSE:
        return _blocked_result(task_id, ["unsupported_invocation_purpose"], [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)

    combined_text = _combined_text(decision_data)
    forbidden_markers = {
        "runtime network requested": "runtime_network_requested",
        "network access": "runtime_network_requested",
        "browser access": "runtime_browser_requested",
        "browser": "runtime_browser_requested",
        "download and execute": "runtime_download_requested",
        "download": "runtime_download_requested",
        "package install": "runtime_package_install_requested",
        "money touching": "money_touching_requested",
        "money-touching": "money_touching_requested",
        "trading": "money_touching_requested",
        "withdraw": "money_touching_requested",
        "memory mutation": "memory_mutation_requested",
        "memory write": "memory_mutation_requested",
        "subagent": "subagent_routing_requested",
        "hermes delegation": "hermes_delegation_requested",
        "hermes_subprocess": "hermes_subprocess_requested",
        "hermes subprocess": "hermes_subprocess_requested",
        "open dispatcher": "open_dispatcher_requested",
        "dynamic plugin": "dynamic_plugin_requested",
        "self invocation": "worker_self_invocation_requested",
        "worker self invocation": "worker_self_invocation_requested",
        "bypass preflight": "bypass_preflight_guard_requested",
        "bypass guard": "bypass_preflight_guard_requested",
        "bypass controlled invocation": "bypass_controlled_invocation_requested",
    }
    forbidden_hits: list[str] = []
    for marker, reason in forbidden_markers.items():
        if marker in combined_text:
            forbidden_hits.append(reason)
    if forbidden_hits:
        return _blocked_result(task_id, list(dict.fromkeys(forbidden_hits)), [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK], generated_at=generated_at)

    invocation_id_value = _text(invocation_id) or _text(decision_data.get("invocation_id")) or f"{task_id}-envelope"
    created_at_value = _text(created_at) or _text(decision_data.get("generated_at")) or DEFAULT_CREATED_AT

    envelope = _build_envelope(
        decision_data,
        requested_by=requested_by_text,
        invocation_id=invocation_id_value,
        created_at=created_at_value,
    )

    reasons = [
        "routing_decision_to_envelope_built",
        "permission_shape_only",
        WORKFLOW_NETWORK_VS_RUNTIME_NETWORK,
    ]
    limitations = [
        "envelope_is_not_execution_approval",
        "no_worker_execution",
        WORKFLOW_NETWORK_VS_RUNTIME_NETWORK,
    ]
    return {
        "task_id": task_id,
        "decision": "built_envelope",
        "invocation_id": invocation_id_value,
        "envelope": envelope,
        "reasons": reasons,
        "limitations": limitations,
        "generated_at": created_at_value,
    }


__all__ = [
    "ABORT_CONDITIONS",
    "ALLOWED_TOOLS",
    "APPROVAL_REQUIRED_ACTIONS",
    "BLOCKED_ACTIONS",
    "DEFAULT_CREATED_AT",
    "DEFAULT_GENERATED_AT",
    "DEFAULT_INVOCATION_ID",
    "ESCALATION_POLICY",
    "FORBIDDEN_TOOLS",
    "GOVERNANCE_EXPECTATION",
    "MEMORY_CONTEXT_POLICY",
    "MODEL_PROVIDER_POLICY",
    "OUTPUT_CONTRACT",
    "RETURN_PATH",
    "SUPPORTED_DECISION",
    "SUPPORTED_INVOCATION_PURPOSE",
    "WORKER_ID",
    "WORKER_TYPE",
    "WORKFLOW_NETWORK_VS_RUNTIME_NETWORK",
    "VERIFICATION_EXPECTATION",
    "build_worker_invocation_envelope_from_routing_decision",
]
