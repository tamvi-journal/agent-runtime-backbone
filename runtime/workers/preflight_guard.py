from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from runtime.security.worker_io_guard import guard_worker_input_scope

DECISIONS = {
    "allow",
    "needs_approval",
    "block",
    "invalid_envelope",
}
PERMISSION_CLASSES = {
    "read_only",
    "suggest_only",
    "draft_only",
    "patch_candidate",
    "local_build",
    "side_effect_request",
    "blocked",
}
SECURITY_PROFILES = {
    "repo_read_only_no_network",
    "draft_only_no_execution",
    "patch_candidate_sandboxed",
    "local_build_sandboxed",
    "network_research_no_execution",
    "side_effect_request_only",
    "blocked",
}
EXECUTION_SURFACES = {
    "direct_tool",
    "delegated_subagent",
    "hermes_subprocess",
}
SIDE_EFFECT_CLASSES = {
    "none",
    "repo_read",
    "repo_write_candidate",
    "repo_mutation",
    "external_read",
    "external_write",
    "money_touching",
    "identity_or_memory_mutation",
    "blocked",
}

DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"

REQUIRED_FIELDS = (
    "invocation_id",
    "task_id",
    "requested_by",
    "worker_id",
    "worker_type",
    "invocation_purpose",
    "input_scope",
    "permission_class",
    "security_profile",
    "execution_surface",
    "allowed_tools",
    "forbidden_tools",
    "auto_allowed_actions",
    "approval_required_actions",
    "blocked_actions",
    "side_effect_class",
    "money_touching",
    "external_mutation",
    "network_access",
    "shell_access",
    "model_provider_policy",
    "memory_context_policy",
    "verification_expectation",
    "governance_expectation",
    "output_contract",
    "return_path",
    "escalation_policy",
    "abort_conditions",
    "created_at",
)

LIST_FIELDS = {
    "allowed_tools",
    "forbidden_tools",
    "auto_allowed_actions",
    "approval_required_actions",
    "blocked_actions",
    "abort_conditions",
}
BOOL_FIELDS = {
    "money_touching",
    "external_mutation",
    "network_access",
    "shell_access",
}


def _is_list_like(value: Any) -> bool:
    return isinstance(value, (list, tuple, set))


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, (tuple, set)):
        return list(value)
    return []


def _policy_text(policy: Any) -> str:
    if isinstance(policy, Mapping):
        parts: list[str] = []
        for key, value in policy.items():
            parts.append(f"{key}={value}")
        return " ".join(parts).lower()
    return str(policy).lower()


def _policy_dict(policy: Any) -> dict[str, Any]:
    if isinstance(policy, Mapping):
        return {str(key): value for key, value in policy.items()}
    return {"value": policy}


def _contains_marker(policy: Any, markers: Sequence[str]) -> bool:
    text = _policy_text(policy)
    return any(marker.lower() in text for marker in markers)


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalize_values(values: Any) -> list[Any]:
    if isinstance(values, list):
        return list(values)
    if isinstance(values, (tuple, set)):
        return list(values)
    return []


def validate_worker_invocation_envelope(envelope: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate a worker invocation envelope without side effects.

    Allowed execution is the intersection of permission_class, security_profile,
    and execution_surface; the most restrictive layer wins.
    """

    result: dict[str, Any] = {
        "invocation_id": None,
        "task_id": None,
        "worker_id": None,
        "decision": "invalid_envelope",
        "reasons": [],
        "validated_permission_class": None,
        "validated_security_profile": None,
        "validated_execution_surface": None,
        "allowed_tools_effective": [],
        "blocked_tools_effective": [],
        "auto_allowed_actions_effective": [],
        "approval_required_actions_effective": [],
        "blocked_actions_effective": [],
        "escalation_required": False,
        "gate_required": False,
        "side_effect_detected": False,
        "money_touching_detected": False,
        "external_mutation_detected": False,
        "network_detected": False,
        "shell_detected": False,
        "model_provider_visibility_status": "not_visible_to_runtime",
        "memory_context_status": "missing",
        "output_contract_status": "missing",
        "return_path_status": "missing",
        "limitations": [],
        "generated_at": DEFAULT_GENERATED_AT,
    }

    if not isinstance(envelope, Mapping):
        result["reasons"].append("missing_or_non_mapping_envelope")
        result["limitations"].append("envelope must be mapping-like")
        return result

    data = deepcopy(dict(envelope))

    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        for field in missing:
            result["reasons"].append(f"missing_required_field:{field}")
        result["limitations"].append("required fields missing")
        return result

    raw_input_scope = data.get("input_scope")
    if not isinstance(raw_input_scope, Mapping):
        result["reasons"].append("invalid_input_scope")
        result["limitations"].append("input_scope must be mapping-like")
        return result
    input_scope_guard = guard_worker_input_scope(raw_input_scope)
    if input_scope_guard["decision"] != "allow":
        result["decision"] = "block"
        result["reasons"].extend(input_scope_guard["reasons"])
        result["limitations"].append("worker input scope includes secret-like path")
        return result

    for field in LIST_FIELDS:
        if not _is_list_like(data.get(field)):
            result["reasons"].append(f"invalid_list_field:{field}")
            result["limitations"].append("list field type mismatch")
            return result
    for field in BOOL_FIELDS:
        if not isinstance(data.get(field), bool):
            result["reasons"].append(f"invalid_bool_field:{field}")
            result["limitations"].append("bool field type mismatch")
            return result

    permission_class = data["permission_class"]
    security_profile = data["security_profile"]
    execution_surface = data["execution_surface"]
    side_effect_class = data["side_effect_class"]

    if permission_class not in PERMISSION_CLASSES:
        result["reasons"].append("unknown_permission_class")
        result["limitations"].append("permission class unsupported")
        return result
    if security_profile not in SECURITY_PROFILES:
        result["reasons"].append("unknown_security_profile")
        result["limitations"].append("security profile unsupported")
        return result
    if execution_surface not in EXECUTION_SURFACES:
        result["reasons"].append("unknown_execution_surface")
        result["limitations"].append("execution surface unsupported")
        return result
    if side_effect_class not in SIDE_EFFECT_CLASSES:
        result["reasons"].append("unknown_side_effect_class")
        result["limitations"].append("side effect class unsupported")
        return result

    result["invocation_id"] = data["invocation_id"]
    result["task_id"] = data["task_id"]
    result["worker_id"] = data["worker_id"]
    result["validated_permission_class"] = permission_class
    result["validated_security_profile"] = security_profile
    result["validated_execution_surface"] = execution_surface

    requested_actions = _as_list(data.get("requested_actions"))
    requested_tools = _as_list(data.get("requested_tools"))
    allowed_tools = _normalize_values(data["allowed_tools"])
    forbidden_tools = _normalize_values(data["forbidden_tools"])
    auto_allowed_actions = _normalize_values(data["auto_allowed_actions"])
    approval_required_actions = _normalize_values(data["approval_required_actions"])
    blocked_actions = _normalize_values(data["blocked_actions"])

    result["allowed_tools_effective"] = [
        tool for tool in allowed_tools if tool not in forbidden_tools
    ]
    result["blocked_tools_effective"] = [
        tool for tool in requested_tools if tool in forbidden_tools
    ]
    result["auto_allowed_actions_effective"] = [
        action for action in requested_actions if action in auto_allowed_actions
    ]
    result["approval_required_actions_effective"] = [
        action for action in requested_actions if action in approval_required_actions
    ]
    result["blocked_actions_effective"] = [
        action for action in requested_actions if action in blocked_actions
    ]

    result["model_provider_visibility_status"] = "not_visible_to_runtime"
    model_provider_policy = _policy_dict(data["model_provider_policy"])
    if _contains_marker(model_provider_policy, ["visible"]):
        result["model_provider_visibility_status"] = "visible"
    if _contains_marker(model_provider_policy, ["not_visible_to_runtime"]):
        result["model_provider_visibility_status"] = "not_visible_to_runtime"

    memory_context_policy = data["memory_context_policy"]
    if memory_context_policy is None:
        result["reasons"].append("missing_memory_context_policy")
        result["limitations"].append("memory context policy missing")
        return result
    memory_policy_text = _policy_text(memory_context_policy)
    if "write_requested" in memory_policy_text or "memory_write" in memory_policy_text:
        result["memory_context_status"] = "write_requested"
    elif "candidate" in memory_policy_text:
        result["memory_context_status"] = "candidate_context_only"
    else:
        result["memory_context_status"] = "candidate_context_only"

    output_contract = data["output_contract"]
    return_path = data["return_path"]
    output_contract_text = _policy_text(output_contract)
    return_path_text = _policy_text(return_path)
    if not output_contract_text.strip():
        result["reasons"].append("missing_output_contract")
        result["limitations"].append("output contract missing")
        return result
    if not return_path_text.strip():
        result["reasons"].append("missing_return_path")
        result["limitations"].append("return path missing")
        return result

    if (
        "workeroutputpacket" in output_contract_text
        or "candidate contribution" in output_contract_text
        or "candidate_only" in output_contract_text
    ):
        result["output_contract_status"] = "ok"
    else:
        result["output_contract_status"] = "invalid"
        result["reasons"].append("invalid_output_contract")
        result["limitations"].append("output contract insufficient")
        return result
    if "mainbrain" in return_path_text or "agent" in return_path_text or "candidate_contribution" in return_path_text:
        result["return_path_status"] = "ok"
    else:
        result["return_path_status"] = "invalid"
        result["reasons"].append("invalid_return_path")
        result["limitations"].append("return path insufficient")
        return result

    # Rule detection that is always evaluated before final decision.
    if side_effect_class != "none":
        result["side_effect_detected"] = True
    if side_effect_class == "money_touching":
        result["money_touching_detected"] = True
    if data["external_mutation"]:
        result["external_mutation_detected"] = True
    if data["network_access"]:
        result["network_detected"] = True
    if data["shell_access"]:
        result["shell_detected"] = True

    escalation_policy = data["escalation_policy"]
    escalation_text = _policy_text(escalation_policy)
    has_gate_marker = any(
        marker in escalation_text
        for marker in ["gate=required", "approval", "review_boundary", "review boundary"]
    )
    has_risk_marker = any(
        marker in escalation_text for marker in ["risk_policy", "future_risk_policy", "risk policy"]
    )
    has_readonly_shell_marker = any(
        marker in escalation_text for marker in ["read_only_shell", "read only shell", "shell_allowlist"]
    )
    has_local_build_shell_marker = any(
        marker in escalation_text
        for marker in [
            "local_build_shell",
            "local build shell",
            "trusted_local_build",
            "trusted local build",
            "codex_style_local_build",
            "codex-style local build",
        ]
    )
    allows_delegated_subagent = any(
        marker in escalation_text
        for marker in ["delegated_subagent_allowed", "allow_delegated_subagent", "subagent_allowed"]
    )
    allows_hermes_subprocess = any(
        marker in escalation_text
        for marker in ["hermes_subprocess_allowed", "allow_hermes_subprocess", "subprocess_allowed"]
    )
    result["escalation_required"] = has_gate_marker or has_risk_marker
    result["gate_required"] = has_gate_marker

    if permission_class == "blocked" or security_profile == "blocked" or side_effect_class == "blocked":
        result["decision"] = "block"
        result["reasons"].append("blocked_by_policy")
        return result

    if requested_actions and any(action in blocked_actions for action in requested_actions):
        result["decision"] = "block"
        for action in requested_actions:
            if action in blocked_actions:
                result["reasons"].append(f"blocked_action:{action}")
        return result

    if requested_tools and any(tool in forbidden_tools for tool in requested_tools):
        result["decision"] = "block"
        for tool in requested_tools:
            if tool in forbidden_tools:
                result["reasons"].append(f"forbidden_tool:{tool}")
        return result

    model_provider_text = _policy_text(model_provider_policy)
    model_provider_change_requested = bool(data.get("requested_model_provider_change")) or any(
        marker in model_provider_text
        for marker in ["change_requested=true", "requested_change=true", "model_change=true", "provider_change=true"]
    )
    if model_provider_change_requested:
        result["decision"] = "needs_approval"
        result["reasons"].append("model_provider_change_requested")
        return result

    memory_policy_text = _policy_text(memory_context_policy)
    memory_write_requested = bool(data.get("requested_memory_write")) or any(
        marker in memory_policy_text
        for marker in ["write_requested=true", "memory_write=true", "mutate=true"]
    )
    if memory_write_requested:
        if has_gate_marker:
            result["decision"] = "needs_approval"
            result["reasons"].append("memory_write_requires_approval")
        else:
            result["decision"] = "block"
            result["reasons"].append("memory_write_blocked")
        return result

    trusted_local_build = (
        permission_class == "local_build"
        and security_profile == "local_build_sandboxed"
        and has_local_build_shell_marker
        and data["shell_access"]
        and not data["network_access"]
        and not data["external_mutation"]
        and not data["money_touching"]
        and side_effect_class == "repo_mutation"
    )
    if trusted_local_build and requested_actions and any(action in approval_required_actions for action in requested_actions):
        result["decision"] = "needs_approval"
        for action in requested_actions:
            if action in approval_required_actions:
                result["reasons"].append(f"approval_required_action:{action}")
        return result
    if trusted_local_build and requested_actions and set(requested_actions).issubset(set(auto_allowed_actions)):
        result["decision"] = "allow"
        result["reasons"].append("trusted_local_build_shell_allowlist")
        result["limitations"].append("local build shell allowed only inside envelope scope")
        return result

    if data.get("requested_repo_mutation") or side_effect_class == "repo_mutation":
        if has_gate_marker:
            result["decision"] = "needs_approval"
            result["reasons"].append("repo_mutation_requires_approval")
        else:
            result["decision"] = "block"
            result["reasons"].append("repo_mutation_blocked")
        return result

    if data.get("requested_external_mutation") or data["external_mutation"] or side_effect_class in {"external_write", "repo_mutation", "identity_or_memory_mutation"}:
        if has_gate_marker:
            result["decision"] = "needs_approval"
            result["reasons"].append("external_mutation_requires_approval")
        else:
            result["decision"] = "block"
            result["reasons"].append("external_mutation_blocked")
        return result

    if data.get("requested_money_touching") or data["money_touching"] or side_effect_class == "money_touching":
        if has_risk_marker:
            result["decision"] = "needs_approval"
            result["reasons"].append("money_touching_requires_approval")
        else:
            result["decision"] = "block"
            result["reasons"].append("money_touching_without_risk_policy")
        return result

    if data["network_access"] and data["shell_access"] and not has_gate_marker:
        result["decision"] = "block"
        result["reasons"].append("network_and_shell_without_review_boundary")
        return result

    if data["network_access"] and security_profile == "repo_read_only_no_network" and not has_gate_marker:
        result["decision"] = "block"
        result["reasons"].append("network_access_blocked_by_profile")
        return result
    if data["network_access"] and security_profile == "repo_read_only_no_network" and has_gate_marker:
        result["decision"] = "needs_approval"
        result["reasons"].append("network_access_requires_approval")
        return result

    if data["shell_access"] and not has_readonly_shell_marker:
        if has_gate_marker:
            result["decision"] = "needs_approval"
            result["reasons"].append("shell_access_requires_approval")
        else:
            result["decision"] = "needs_approval"
            result["reasons"].append("shell_access_requires_approval")
        return result

    if execution_surface == "hermes_subprocess":
        if allows_hermes_subprocess:
            result["decision"] = "needs_approval"
            result["reasons"].append("hermes_subprocess_requires_approval")
        else:
            result["decision"] = "block"
            result["reasons"].append("hermes_subprocess_requires_approval")
        return result

    if execution_surface == "delegated_subagent" and not allows_delegated_subagent:
        result["decision"] = "needs_approval"
        result["reasons"].append("delegated_subagent_requires_approval")
        return result

    if requested_actions and any(action in approval_required_actions for action in requested_actions):
        result["decision"] = "needs_approval"
        for action in requested_actions:
            if action in approval_required_actions:
                result["reasons"].append(f"approval_required_action:{action}")
        return result

    if requested_actions and any(
        action in {"download_and_execute", "download-and-execute", "download_execute"}
        for action in requested_actions
    ):
        result["decision"] = "block"
        result["reasons"].append("download_and_execute_detected")
        return result

    if any(
        marker in _policy_text(data["abort_conditions"])
        for marker in ["self_approval", "self-approval", "gate_bypass", "verification_bypass", "governance_bypass"]
    ):
        result["decision"] = "block"
        result["reasons"].append("authority_bypass_detected")
        return result

    if requested_actions and not set(requested_actions).issubset(set(auto_allowed_actions)):
        result["decision"] = "needs_approval"
        result["reasons"].append("requested_action_outside_auto_allowed")
        return result

    if requested_tools and not set(requested_tools).issubset(set(result["allowed_tools_effective"])):
        result["decision"] = "block"
        result["reasons"].append("requested_tool_outside_allowed_tools")
        return result

    if result["side_effect_detected"] and side_effect_class not in {"none", "repo_read"}:
        result["decision"] = "needs_approval"
        result["reasons"].append("side_effect_requires_approval")
        return result

    if requested_tools and any(tool in forbidden_tools for tool in requested_tools):
        result["decision"] = "block"
        result["reasons"].append("forbidden_tool_detected")
        return result

    if data["permission_class"] == "read_only" and data["security_profile"] == "repo_read_only_no_network" and data["execution_surface"] == "direct_tool":
        if data["money_touching"]:
            result["decision"] = "block"
            result["reasons"].append("money_touching_without_risk_policy")
            return result
        if data["external_mutation"]:
            result["decision"] = "block"
            result["reasons"].append("external_mutation_blocked")
            return result
        if not result["reasons"]:
            result["decision"] = "allow"
            result["limitations"].append("read_only envelope validated")
        return result

    # Conservative intersection fallback for non-read-only envelopes.
    if data["permission_class"] in {"patch_candidate", "side_effect_request"} and data["security_profile"] == "patch_candidate_sandboxed":
        result["decision"] = "needs_approval"
        result["reasons"].append("patch_or_side_effect_envelope_requires_approval")
        return result

    result["decision"] = "allow"
    if not result["limitations"]:
        result["limitations"].append("validation completed")
    return result


__all__ = [
    "DECISIONS",
    "EXECUTION_SURFACES",
    "PERMISSION_CLASSES",
    "SECURITY_PROFILES",
    "SIDE_EFFECT_CLASSES",
    "validate_worker_invocation_envelope",
]
