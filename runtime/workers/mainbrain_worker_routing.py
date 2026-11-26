from __future__ import annotations

"""Pure MainBrain worker routing helper.

Workflow network ≠ runtime network.
Approved git workflow actions do not imply runtime worker network permission.
This module only returns a routing decision; it does not execute workers.
"""

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

WORKER_ID = "repo_research_worker"
WORKER_TYPE = "read_only_repo_research"
DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"
DEFAULT_MAX_FILES = 5
DEFAULT_MAX_BYTES_PER_FILE = 20_000

EVIDENCE_INTENTS = {
    "candidate_repo_evidence",
    "repo_file_lookup",
    "repo_spec_readback",
    "repo_artifact_check",
}

COMPATIBLE_RUNTIME_SURFACES = {
    "direct_tool",
    "read_only",
    "local_repo",
    "repo_read_only",
    "repo_read_only_no_network",
}

SUPPORTED_DECISIONS = {
    "no_worker_needed",
    "route_repo_research_worker",
    "needs_approval",
    "blocked",
    "invalid_request",
}

REQUIRED_FIELDS = (
    "task_id",
    "mainbrain_intent",
    "requested_evidence",
    "candidate_paths",
    "side_effect_intent",
    "network_intent",
    "money_touching_intent",
    "memory_mutation_intent",
    "model_provider_intent",
    "runtime_surface_intent",
)

REQUIRED_ENVELOPE_FIELDS = [
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
]

WORKFLOW_NETWORK_VS_RUNTIME_NETWORK = "Workflow network ≠ runtime network."


def _copy_request(request: Mapping[str, Any]) -> dict[str, Any]:
    return deepcopy(dict(request))


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        parts: list[str] = []
        for key, item in value.items():
            parts.append(f"{key}={item}")
        return " ".join(parts).strip()
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(item) for item in value if _text(item))
    if value is None:
        return ""
    return str(value).strip()


def _lower_text(value: Any) -> str:
    return _text(value).lower()


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return []


def _bool_field(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _has_repo_evidence_intent(request: Mapping[str, Any]) -> bool:
    return _text(request.get("mainbrain_intent")) in EVIDENCE_INTENTS


def _is_repo_local_evidence(requested_evidence: Any) -> bool:
    text = _lower_text(requested_evidence)
    if not text:
        return False
    markers = ("repo", "local file", "local-file", "file lookup", "spec readback", "artifact", "readback", "candidate evidence")
    return any(marker in text for marker in markers)


def _has_forbidden_route(request_text: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    markers = {
        "arbitrary code": "arbitrary_code_execution",
        "dynamic worker": "dynamic_worker_loading",
        "open worker registry": "open_worker_registry",
        "unknown worker": "unknown_worker_execution",
        "worker to worker": "worker_to_worker_routing",
        "worker-to-worker": "worker_to_worker_routing",
        "self invocation": "worker_self_invocation",
        "worker self invocation": "worker_self_invocation",
        "download and execute": "download_and_execute",
        "money transfer": "money_transfer",
        "withdraw": "money_transfer",
        "trading": "trading_or_money_touching_route",
        "money touching": "trading_or_money_touching_route",
        "bypass gate": "bypass_governance_or_gate",
        "bypass verification": "bypass_governance_or_gate",
        "bypass governance": "bypass_governance_or_gate",
        "memory mutation by worker": "worker_memory_mutation",
        "worker memory mutation": "worker_memory_mutation",
        "approve itself": "worker_self_approval",
        "claim completion": "worker_completion_claim",
        "repo mutation through repo research worker": "repo_mutation_via_repo_research_worker",
        "repo mutation": "repo_mutation_via_repo_research_worker",
        "hermes delegation": "hermes_delegation",
        "subagent": "subagent_routing",
        "hermes_subprocess": "hermes_subprocess",
    }
    for marker, reason in markers.items():
        if marker in request_text:
            reasons.append(reason)
    unique_reasons = list(dict.fromkeys(reasons))
    return (bool(unique_reasons), unique_reasons)


def _approval_needed_reason(request_text: str, request: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if request.get("side_effect_intent") is True:
        reasons.append("side_effect_intent_requires_review")
    if request.get("network_intent") is True:
        reasons.append("runtime_network_requires_review")
    if request.get("memory_mutation_intent") is True:
        reasons.append("memory_mutation_requires_review")
    if _text(request.get("model_provider_intent")):
        if any(marker in request_text for marker in ("model provider", "provider change", "model change", "provider", "model")):
            reasons.append("model_provider_change_requires_review")
    if any(marker in request_text for marker in ("delegated_subagent", "subagent routing", "subagent")):
        reasons.append("delegated_subagent_requires_review")
    if any(marker in request_text for marker in ("hermes_subprocess", "hermes subprocess")):
        reasons.append("hermes_subprocess_requires_review")
    if any(marker in request_text for marker in ("gate review", "verification review", "governance review", "operator review", "owner review")):
        reasons.append("policy_review_required")
    return list(dict.fromkeys(reasons))


def _invalid_result(task_id: Any, reasons: list[str], next_step: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "decision": "invalid_request",
        "reasons": reasons,
        "selected_worker": None,
        "invocation_purpose": None,
        "proposed_input_scope": None,
        "required_envelope_fields": [],
        "approval_required": False,
        "blocked_reasons": [],
        "limitations": [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK],
        "next_step": next_step,
        "generated_at": DEFAULT_GENERATED_AT,
    }


def route_mainbrain_worker_request(request: Mapping[str, Any]) -> dict[str, Any]:
    """Return a pure routing decision for MainBrain worker requests."""

    if not isinstance(request, Mapping):
        return _invalid_result(None, ["request_must_be_mapping"], "Provide a mapping-like routing request.")

    request_data = _copy_request(request)
    task_id = request_data.get("task_id")
    missing = [field for field in REQUIRED_FIELDS if field not in request_data]
    if missing:
        return _invalid_result(task_id, [f"missing_required_field:{field}" for field in missing], "Add the missing routing fields and retry.")

    bool_fields = {
        "side_effect_intent": request_data.get("side_effect_intent"),
        "network_intent": request_data.get("network_intent"),
        "money_touching_intent": request_data.get("money_touching_intent"),
        "memory_mutation_intent": request_data.get("memory_mutation_intent"),
    }
    invalid_bools = [name for name, value in bool_fields.items() if not isinstance(value, bool)]
    if invalid_bools:
        return _invalid_result(task_id, [f"invalid_bool_field:{name}" for name in invalid_bools], "Use boolean intent fields and retry.")

    candidate_paths = request_data.get("candidate_paths")
    if not isinstance(candidate_paths, list):
        return _invalid_result(task_id, ["invalid_list_field:candidate_paths"], "Provide candidate_paths as a list.")
    if any(not isinstance(path, str) or not path.strip() for path in candidate_paths):
        return _invalid_result(task_id, ["invalid_candidate_paths"], "Provide explicit non-empty string paths.")

    forbidden_paths = request_data.get("forbidden_paths", [])
    if forbidden_paths is not None and not isinstance(forbidden_paths, list):
        return _invalid_result(task_id, ["invalid_list_field:forbidden_paths"], "Provide forbidden_paths as a list when present.")
    if forbidden_paths is not None and any(not isinstance(path, str) or not path.strip() for path in forbidden_paths):
        return _invalid_result(task_id, ["invalid_forbidden_paths"], "Provide forbidden paths as explicit non-empty string paths.")

    normalized_candidate_paths = [path.strip() for path in candidate_paths]
    normalized_forbidden_paths = [path.strip() for path in (forbidden_paths or [])]
    for candidate_path in normalized_candidate_paths:
        for forbidden_path in normalized_forbidden_paths:
            prefix = forbidden_path.rstrip("/") + "/"
            if candidate_path == forbidden_path or candidate_path.startswith(prefix):
                return _invalid_result(task_id, ["candidate_path_conflicts_with_forbidden_path"], "Remove the forbidden path from candidate_paths or narrow the request.")

    mainbrain_intent = _text(request_data.get("mainbrain_intent"))
    requested_evidence = request_data.get("requested_evidence")
    runtime_surface_intent = _lower_text(request_data.get("runtime_surface_intent"))
    request_text = " ".join(
        part
        for part in (
            _lower_text(request_data.get("user_request")),
            mainbrain_intent.lower(),
            _lower_text(requested_evidence),
            runtime_surface_intent,
            _lower_text(request_data.get("model_provider_intent")),
        )
        if part
    )

    blocked, blocked_reasons = _has_forbidden_route(request_text)
    if blocked:
        return {
            "task_id": task_id,
            "decision": "blocked",
            "reasons": [f"forbidden_request:{reason}" for reason in blocked_reasons],
            "selected_worker": None,
            "invocation_purpose": None,
            "proposed_input_scope": None,
            "required_envelope_fields": [],
            "approval_required": False,
            "blocked_reasons": blocked_reasons,
            "limitations": [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK],
            "next_step": "Do not route; ask for a safe, non-forbidden request.",
            "generated_at": DEFAULT_GENERATED_AT,
        }

    if request_data.get("money_touching_intent") is True:
        return {
            "task_id": task_id,
            "decision": "blocked",
            "reasons": ["money_touching_route_forbidden"],
            "selected_worker": None,
            "invocation_purpose": None,
            "proposed_input_scope": None,
            "required_envelope_fields": [],
            "approval_required": False,
            "blocked_reasons": ["money_touching_route_forbidden"],
            "limitations": [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK],
            "next_step": "Do not route money-touching work.",
            "generated_at": DEFAULT_GENERATED_AT,
        }

    approval_reasons = _approval_needed_reason(request_text, request_data)
    if request_data.get("side_effect_intent") is True or request_data.get("network_intent") is True or request_data.get("memory_mutation_intent") is True:
        return {
            "task_id": task_id,
            "decision": "needs_approval",
            "reasons": approval_reasons or ["review_required_before_worker_routing"],
            "selected_worker": None,
            "invocation_purpose": None,
            "proposed_input_scope": None,
            "required_envelope_fields": [],
            "approval_required": True,
            "blocked_reasons": [],
            "limitations": [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK],
            "next_step": "Route to Gate/operator review before any worker invocation.",
            "generated_at": DEFAULT_GENERATED_AT,
        }

    if runtime_surface_intent in {"delegated_subagent", "hermes_subprocess"}:
        return {
            "task_id": task_id,
            "decision": "needs_approval",
            "reasons": approval_reasons or ["runtime_surface_requires_review"],
            "selected_worker": None,
            "invocation_purpose": None,
            "proposed_input_scope": None,
            "required_envelope_fields": [],
            "approval_required": True,
            "blocked_reasons": [],
            "limitations": [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK],
            "next_step": "Review the runtime surface before any worker route.",
            "generated_at": DEFAULT_GENERATED_AT,
        }

    normalized_model_provider_intent = _text(request_data.get("model_provider_intent")).lower()
    if normalized_model_provider_intent and normalized_model_provider_intent not in {"none", "no_change", "unchanged", "not_visible_to_runtime", "false"}:
        return {
            "task_id": task_id,
            "decision": "needs_approval",
            "reasons": approval_reasons or ["model_provider_change_requires_review"],
            "selected_worker": None,
            "invocation_purpose": None,
            "proposed_input_scope": None,
            "required_envelope_fields": [],
            "approval_required": True,
            "blocked_reasons": [],
            "limitations": [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK],
            "next_step": "Obtain model/provider review before any worker route.",
            "generated_at": DEFAULT_GENERATED_AT,
        }

    if not _has_repo_evidence_intent(request_data):
        if not _text(requested_evidence):
            return {
                "task_id": task_id,
                "decision": "no_worker_needed",
                "reasons": ["mainbrain_intent_does_not_require_repo_evidence"],
                "selected_worker": None,
                "invocation_purpose": "proceed_without_worker_evidence",
                "proposed_input_scope": None,
                "required_envelope_fields": [],
                "approval_required": False,
                "blocked_reasons": [],
                "limitations": [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK],
                "next_step": "Proceed without worker evidence.",
                "generated_at": DEFAULT_GENERATED_AT,
            }
        return _invalid_result(task_id, ["requested_evidence_present_without_repo_evidence_intent"], "Clarify the evidence need or change the mainbrain intent.")

    if not _is_repo_local_evidence(requested_evidence):
        return _invalid_result(task_id, ["requested_evidence_not_repo_local_file_evidence"], "State the repo/local-file evidence need explicitly.")

    if not candidate_paths:
        return _invalid_result(task_id, ["candidate_paths_empty_for_repo_evidence"], "Provide at least one explicit candidate path.")

    incompatible_surface = bool(runtime_surface_intent) and not any(marker in runtime_surface_intent for marker in COMPATIBLE_RUNTIME_SURFACES)
    if incompatible_surface:
        return {
            "task_id": task_id,
            "decision": "needs_approval",
            "reasons": ["runtime_surface_not_read_only_local_repo"],
            "selected_worker": None,
            "invocation_purpose": None,
            "proposed_input_scope": None,
            "required_envelope_fields": [],
            "approval_required": True,
            "blocked_reasons": [],
            "limitations": [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK],
            "next_step": "Review the runtime surface before routing any worker.",
            "generated_at": DEFAULT_GENERATED_AT,
        }

    selected_worker = {
        "worker_id": WORKER_ID,
        "worker_type": WORKER_TYPE,
    }
    proposed_input_scope = {
        "paths_allowed": normalized_candidate_paths,
        "paths_excluded": normalized_forbidden_paths,
        "research_question": _text(requested_evidence) or _text(request_data.get("user_request")) or mainbrain_intent,
        "max_files": DEFAULT_MAX_FILES,
        "max_bytes_per_file": DEFAULT_MAX_BYTES_PER_FILE,
    }

    return {
        "task_id": task_id,
        "decision": "route_repo_research_worker",
        "reasons": [
            "evidence_oriented_mainbrain_intent",
            "requested_evidence_is_repo_local_file_evidence",
            "candidate_paths_explicit",
            "read_only_runtime_surface_compatible",
            WORKFLOW_NETWORK_VS_RUNTIME_NETWORK,
        ],
        "selected_worker": selected_worker,
        "invocation_purpose": "candidate_repo_evidence",
        "proposed_input_scope": proposed_input_scope,
        "required_envelope_fields": list(REQUIRED_ENVELOPE_FIELDS),
        "approval_required": False,
        "blocked_reasons": [],
        "limitations": [WORKFLOW_NETWORK_VS_RUNTIME_NETWORK],
        "next_step": "Build a WorkerInvocationEnvelope for repo_research_worker with read-only scope.",
        "generated_at": DEFAULT_GENERATED_AT,
    }


__all__ = [
    "DEFAULT_GENERATED_AT",
    "DEFAULT_MAX_BYTES_PER_FILE",
    "DEFAULT_MAX_FILES",
    "EVIDENCE_INTENTS",
    "REQUIRED_ENVELOPE_FIELDS",
    "SUPPORTED_DECISIONS",
    "WORKER_ID",
    "WORKER_TYPE",
    "WORKFLOW_NETWORK_VS_RUNTIME_NETWORK",
    "route_mainbrain_worker_request",
]
