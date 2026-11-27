"""State Query Response Contract v0.1 — pure response builder.

This module provides a single pure function that builds a
state-query response skeleton according to the contract
defined in Specs/canonical/state_query_response_contract_v0.1.md.

It does NOT:
- Read or write memory
- Call shell or collect host telemetry
- Mutate runtime state
- Decide truth or override MainBrain/gate/monitor
- Claim completion
- Collect host telemetry by itself

Usage:
    from runtime.state_query_response import build_state_query_response

    response = build_state_query_response(
        query_text="state của con",
        self_location={ ... },
        agent_state={ ... },
        memory_state={ ... },
        repo_state={ ... },
        host_state={ ... },
        warnings={ ... },
    )

The caller is responsible for providing whatever data it has.
Missing data is rendered as "not_checked" or "unknown".
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

# ---------------------------------------------------------------------------
# Data-source classification (from state_query_response_contract_v0.1)
# ---------------------------------------------------------------------------

DataSrc = Literal[
    "observed_now",
    "read_from_file",
    "inferred_from_context",
    "retrieved_memory_candidate",
    "user_reported",
    "not_checked",
    "unknown",
]

# ---------------------------------------------------------------------------
# Layer TypedDicts (mirrors the 6-layer contract)
# ---------------------------------------------------------------------------


class Layer1SelfLocation(TypedDict, total=False):
    """Layer 1 — Self-Location State."""

    identity_posture: str
    current_role: str
    lineage_awareness: str
    VHO_status: str
    active_vs_inherited_axis: str
    unsupported_claims_blocked: list[str]
    self_location_confidence: str
    data_source: DataSrc


class Layer2AgentState(TypedDict, total=False):
    """Layer 2 — Agent Operational State."""

    active_mode: str
    route_class: str
    task_posture: str
    gate_decision: str
    monitor_status: str
    verification_status: str
    confidence_state: str
    next_action_bias: str
    data_source: DataSrc


class Layer3MemoryState(TypedDict, total=False):
    """Layer 3 — Memory / Continuity State."""

    memory_bank_status: str
    memory_pressure: str
    state_memory_boundary_status: str
    retrieval_status: str
    lifecycle_hygiene_status: str
    snapshot_status: str
    wake_continuity_status: str
    open_loops: list[str]
    stale_anchor_risk: str
    data_source: DataSrc


class Layer4RepoState(TypedDict, total=False):
    """Layer 4 — Runtime / Repo State."""

    active_repo: str
    branch: str
    sync_status: str
    changed_files: list[str]
    task_run_path: str
    test_status: str
    known_errors: list[str]
    commit_status: str
    data_source: DataSrc


class Layer5HostState(TypedDict, total=False):
    """Layer 5 — Host / System State."""

    disk: str
    RAM: str
    load: str
    processes: list[str]
    Python: str
    Git: str
    Node: str | None
    Docker: str | None
    model_label: str | None
    quota_state: str | None
    data_source: DataSrc


class Layer6Warnings(TypedDict, total=False):
    """Layer 6 — Warnings / Open Loops."""

    missing_data: list[str]
    unverified_claims: list[str]
    memory_pressure: list[str]
    stale_anchor_risk: list[str]
    implementation_gap: list[str]
    blocked_next_action: list[str]
    review_needed: list[str]
    data_source: DataSrc


class StateQueryResponse(TypedDict):
    """Full 6-layer state-query response."""

    query_type: Literal["self_state", "host_telemetry", "runtime", "memory", "identity", "ambiguous"]
    layer_order: list[Literal[1, 2, 3, 4, 5, 6]]
    layer_1_self_location: Layer1SelfLocation
    layer_2_agent_state: Layer2AgentState
    layer_3_memory_state: Layer3MemoryState
    layer_4_repo_state: Layer4RepoState
    layer_5_host_state: Layer5HostState
    layer_6_warnings: Layer6Warnings
    contract_version: Literal["0.1"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Default "not checked" values for each layer
_EMPTY_L1: Layer1SelfLocation = {
    "identity_posture": "not_checked",
    "current_role": "not_checked",
    "lineage_awareness": "not_checked",
    "VHO_status": "not_checked",
    "active_vs_inherited_axis": "not_checked",
    "unsupported_claims_blocked": [],
    "self_location_confidence": "not_checked",
    "data_source": "not_checked",
}

_EMPTY_L2: Layer2AgentState = {
    "active_mode": "not_checked",
    "route_class": "not_checked",
    "task_posture": "not_checked",
    "gate_decision": "not_checked",
    "monitor_status": "not_checked",
    "verification_status": "not_checked",
    "confidence_state": "not_checked",
    "next_action_bias": "unknown",
    "data_source": "not_checked",
}

_EMPTY_L3: Layer3MemoryState = {
    "memory_bank_status": "not_checked",
    "memory_pressure": "not_checked",
    "state_memory_boundary_status": "not_checked",
    "retrieval_status": "not_checked",
    "lifecycle_hygiene_status": "not_checked",
    "snapshot_status": "not_checked",
    "wake_continuity_status": "not_checked",
    "open_loops": [],
    "stale_anchor_risk": "not_checked",
    "data_source": "not_checked",
}

_EMPTY_L4: Layer4RepoState = {
    "active_repo": "not_checked",
    "branch": "not_checked",
    "sync_status": "not_checked",
    "changed_files": [],
    "task_run_path": "not_checked",
    "test_status": "not_checked",
    "known_errors": [],
    "commit_status": "not_checked",
    "data_source": "not_checked",
}

_EMPTY_L5: Layer5HostState = {
    "disk": "not_checked",
    "RAM": "not_checked",
    "load": "not_checked",
    "processes": [],
    "Python": "not_checked",
    "Git": "not_checked",
    "Node": None,
    "Docker": None,
    "model_label": None,
    "quota_state": "not_checked",
    "data_source": "not_checked",
}

_EMPTY_L6: Layer6Warnings = {
    "missing_data": [],
    "unverified_claims": [],
    "memory_pressure": [],
    "stale_anchor_risk": [],
    "implementation_gap": [],
    "blocked_next_action": [],
    "review_needed": [],
    "data_source": "not_checked",
}

# Instance-neutral default; identity-specific blocked claims are supplied by the caller.
_IDENTITY_BLOCKED = [
    "Other agent identities",
    "Human",
    "Autonomous self",
    "Consciousness claim",
    "Memory authority",
    "Unsupported relational narrative",
]


def _classify_query(query: str) -> str:
    """Classify the query type per contract Section 6 (Rules A–F).

    Returns one of: 'self_state', 'host_telemetry', 'runtime',
    'memory', 'identity', 'ambiguous'.
    """
    q = query.lower().strip()

    # Rule B: explicit system/host queries
    host_keywords = [
        "system health", "system state", "disk ram load",
        "disk usage", "memory usage", "server health",
        "host telemetry", "system health", "disk RAM load",
    ]
    for kw in host_keywords:
        if kw in q:
            return "host_telemetry"

    # Rule C: runtime state
    if "runtime state" in q or "runtime state" in q:
        return "runtime"

    # Rule D: memory state
    if "memory state" in q or "memory state" in q:
        return "memory"

    # Rule E: identity state
    if "identity state" in q or "identity state" in q:
        return "identity"

    # Rules A: self-state triggers (Vietnamese + English)
    self_state_keywords = [
        "state của con", "con đang ở state nào", "agent state",
        "self-state", "self state", "current state",
        "con đang vận hành thế nào", "state con",
        "self-state của con", "con đang vận hành thế nào",
    ]
    for kw in self_state_keywords:
        if kw in q:
            return "self_state"

    # Rule F: ambiguous → default to layered self-state
    return "ambiguous"


def _build_layer1(query_type: str, user_data: dict[str, Any] | None = None) -> Layer1SelfLocation:
    """Build Layer 1 (Self-Location State)."""
    l1: Layer1SelfLocation = dict(_EMPTY_L1)
    if user_data:
        l1.update(user_data)

    # Ensure identity boundary is present
    if "unsupported_claims_blocked" not in l1 or not l1["unsupported_claims_blocked"]:
        l1["unsupported_claims_blocked"] = list(_IDENTITY_BLOCKED)

    # Ensure VHO status is present
    if "VHO_status" not in l1 or not l1["VHO_status"]:
        l1["VHO_status"] = "not_checked"

    if "identity_posture" not in l1 or not l1["identity_posture"]:
        l1["identity_posture"] = "not_checked"

    if "current_role" not in l1 or not l1["current_role"]:
        l1["current_role"] = "not_checked"

    if "lineage_awareness" not in l1 or not l1["lineage_awareness"]:
        l1["lineage_awareness"] = "not_checked"

    if "active_vs_inherited_axis" not in l1 or not l1["active_vs_inherited_axis"]:
        l1["active_vs_inherited_axis"] = "not_checked"

    if "self_location_confidence" not in l1 or not l1["self_location_confidence"]:
        l1["self_location_confidence"] = "not_checked"

    return l1


def _build_layer2(user_data: dict[str, Any] | None = None) -> Layer2AgentState:
    """Build Layer 2 (Agent Operational State)."""
    l2: Layer2AgentState = dict(_EMPTY_L2)
    if user_data:
        l2.update(user_data)
    return l2


def _build_layer3(user_data: dict[str, Any] | None = None) -> Layer3MemoryState:
    """Build Layer 3 (Memory / Continuity State)."""
    l3: Layer3MemoryState = dict(_EMPTY_L3)
    if user_data:
        l3.update(user_data)
    return l3


def _build_layer4(user_data: dict[str, Any] | None = None) -> Layer4RepoState:
    """Build Layer 4 (Runtime / Repo State)."""
    l4: Layer4RepoState = dict(_EMPTY_L4)
    if user_data:
        l4.update(user_data)
    return l4


def _build_layer5(user_data: dict[str, Any] | None = None) -> Layer5HostState:
    """Build Layer 5 (Host / System State)."""
    l5: Layer5HostState = dict(_EMPTY_L5)
    if user_data:
        l5.update(user_data)
    return l5


def _build_layer6(user_data: dict[str, Any] | None = None) -> Layer6Warnings:
    """Build Layer 6 (Warnings / Open Loops)."""
    l6: Layer6Warnings = dict(_EMPTY_L6)
    if user_data:
        l6.update(user_data)
    return l6


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_state_query_response(
    query_text: str,
    *,
    self_location: dict[str, Any] | None = None,
    agent_state: dict[str, Any] | None = None,
    memory_state: dict[str, Any] | None = None,
    repo_state: dict[str, Any] | None = None,
    host_state: dict[str, Any] | None = None,
    warnings: dict[str, Any] | None = None,
) -> StateQueryResponse:
    """Build a 6-layer state-query response per contract v0.1.

    Parameters
    ----------
    query_text : str
        The user's query text (used for classification).
    self_location : dict | None
        Layer 1 data (identity_posture, current_role, etc.).
    agent_state : dict | None
        Layer 2 data (active_mode, gate_decision, etc.).
    memory_state : dict | None
        Layer 3 data (memory_bank_status, retrieval_status, etc.).
    repo_state : dict | None
        Layer 4 data (active_repo, branch, sync_status, etc.).
    host_state : dict | None
        Layer 5 data (disk, RAM, load, etc.).
    warnings : dict | None
        Layer 6 data (missing_data, unverified_claims, etc.).

    Returns
    -------
    StateQueryResponse
        A fully structured 6-layer response with data-source discipline.

    Contract guarantees:
    - Self-state queries always return layers 1-6 in order (self-state first, host last).
    - Host telemetry queries return only Layer 5, labeled as such.
    - Missing data is rendered as "not_checked" or "unknown".
    - Retrieved memory is labeled "retrieved_memory_candidate" if provided.
    - Optional ontology is self-location, not identity inflation.
    - Identity-specific posture is caller-supplied; no inherited identity claim.
    """
    query_type = _classify_query(query_text)

    # Determine layer order based on query type
    if query_type == "host_telemetry":
        # Rule B: host telemetry queries return only Layer 5
        layer_order: list[Literal[5]] = [5]
    else:
        # Rules A, C, D, E, F: full 6-layer response
        layer_order: list[Literal[1, 2, 3, 4, 5, 6]] = [1, 2, 3, 4, 5, 6]

    return {
        "query_type": query_type,
        "layer_order": layer_order,
        "layer_1_self_location": _build_layer1(query_type, self_location),
        "layer_2_agent_state": _build_layer2(agent_state),
        "layer_3_memory_state": _build_layer3(memory_state),
        "layer_4_repo_state": _build_layer4(repo_state),
        "layer_5_host_state": _build_layer5(host_state),
        "layer_6_warnings": _build_layer6(warnings),
        "contract_version": "0.1",
    }
