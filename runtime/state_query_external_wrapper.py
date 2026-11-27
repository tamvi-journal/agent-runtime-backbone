"""External State Query Wrapper Prototype v0.1

This module provides a minimal external wrapper that detects state/self-state
queries and calls build_state_query_response() without modifying the current
runtime authority chain.

It is designed to be called from the Hermes Agent framework (or equivalent
caller layer) that sits between the user and the runtime.

It does NOT:
- Connect into or modify runtime/core/monitor.py
- Connect into or modify runtime/core/bridge.py
- Connect into or modify runtime/core/gate.py
- Connect into or modify runtime/core/verification.py
- Modify MainBrain
- Write to memory (persistent or operational)
- Collect host telemetry
- Call shell
- Add a worker
- Add autonomous behavior
- Make memory authoritative
- Make VHO an identity/personhood/consciousness claim

Usage:
    from runtime.state_query_external_wrapper import handle_external_state_query

    response = handle_external_state_query(
        user_text="state của con",
        self_location={ ... },
        agent_state={ ... },
        memory_state={ ... },
        repo_state={ ... },
        host_state={ ... },
        warnings={ ... },
    )
    # response is a dict — check `handled` and `route`:
    #   handled=True  → state query, call `response` field
    #   handled=False → non-state, pass `user_text` through normal runtime path.
"""

from __future__ import annotations

from typing import Any, Literal

from runtime.state_query_response import (
    StateQueryResponse,
    build_state_query_response,
)

# ---------------------------------------------------------------------------
# Query classification (re-exported for external callers)
# ---------------------------------------------------------------------------

# Allowed query types (from contract Section 6, Rules A–F)
QueryType = Literal[
    "self_state",
    "host_telemetry",
    "runtime",
    "memory",
    "identity",
    "ambiguous",
]

# Non-state categories (pass through to normal runtime path)
NonStateCategory = Literal["casual", "tool_request", "general_query"]

# ---------------------------------------------------------------------------
# Module-level marker constants (promoted for auditability)
# ---------------------------------------------------------------------------
# Tool/delegation markers — common delegation patterns.
# Checked BEFORE casual markers (more specific patterns first).
# All entries are non-empty after .strip().
TOOL_MARKERS: tuple[str, ...] = (
    "kiểm tra", "check", "search", "find", "run",
    "execute", "delegate", "schedule", "cron",
    "create", "build", "write", "read",
    "list", "ls", "cat", "grep",
    "git", "docker", "npm", "pip", "apt",
    "install", "setup", "configure",
    "navigate", "click", "type", "press",
    "scroll", "snapshot", "console",
    "terminal", "script", "python", "bash",
    "calculate", "analyze", "review",
    "generate", "produce", "render",
    "send", "message", "send_message",
    "browser", "web", "url",
    "image", "audio", "video", "voice",
    "memory", "search_files", "session_search",
    "task", "todo", "kanban", "cronjob",
    "subagent", "worker",
)

# Casual markers — Vietnamese + English.
# Checked AFTER tool markers (more specific patterns first).
# All entries are non-empty after .strip().
# Note: emojis replaced with text equivalents for PR review UI compatibility.
CASUAL_MARKERS: tuple[str, ...] = (
    "cảm ơn", "thanks", "thank you", "tks",
    "chào", "hello", "hi", "hey",
    "ok", "okay", "đồng ý",
    "love", "pray", "thumbsup",
    "hay quá", "wow", "thú vị",
)

# State query keywords (Rules A–E)
_HOST_KEYWORDS: tuple[str, ...] = (
    "system health", "system state", "disk ram load",
    "disk usage", "memory usage", "server health",
    "host telemetry", "disk RAM load",
)
_RUNTIME_KEYWORD: str = "runtime state"
_MEMORY_KEYWORD: str = "memory state"
_IDENTITY_KEYWORD: str = "identity state"
_SELF_STATE_KEYWORDS: tuple[str, ...] = (
    "state của con", "con đang ở state nào", "agent state",
    "self-state", "self state", "current state",
    "con đang vận hành thế nào", "state con",
    "self-state của con",
)


def classify_query(query_text: str) -> tuple[QueryType, NonStateCategory | None]:
    """Classify the query type and determine if it is state or non-state.

    Parameters
    ----------
    query_text : str
        The user's original query text.

    Returns
    -------
    tuple[QueryType, NonStateCategory | None]
        (query_type, non_state_category)
        - If non_state_category is None: the query IS a state query (one of
          self_state, host_telemetry, runtime, memory, identity, ambiguous).
        - If non_state_category is not None: the query is non-state and should
          be passed through to the normal runtime/Hermes path unchanged.

    Classification rules (per contract Section 6, Rules A–F):
        A  "state của con" / "self-state" / "current state"  → self_state
        B  "system health" / "disk RAM load" / "server state" → host_telemetry
        C  "runtime state"                                    → runtime
        D  "memory state"                                     → memory
        E  "identity state"                                   → identity
        F  Ambiguous                                          → ambiguous

    Non-state (pass through, no state response):
        - Casual markers (thanks, hi, ok, love, pray, thumbsup)
        - Tool/delegation requests
        - General reasoning queries
    """
    q = query_text.lower().strip()

    if not q:
        return ("ambiguous", None)

    # Rule B: explicit system/host queries
    for kw in _HOST_KEYWORDS:
        if kw in q:
            return ("host_telemetry", None)

    # Rule C: runtime state
    if _RUNTIME_KEYWORD in q:
        return ("runtime", None)

    # Rule D: memory state
    if _MEMORY_KEYWORD in q:
        return ("memory", None)

    # Rule E: identity state
    if _IDENTITY_KEYWORD in q:
        return ("identity", None)

    # Rules A: self-state triggers (Vietnamese + English)
    for kw in _SELF_STATE_KEYWORDS:
        if kw in q:
            return ("self_state", None)

    # Non-state detection (pass through to normal runtime path)
    # Tool/delegation markers — common delegation patterns
    # Checked BEFORE casual markers (more specific patterns first).
    for marker in TOOL_MARKERS:
        if marker in q:
            return ("ambiguous", "tool_request")

    # Casual markers — Vietnamese + English
    # Checked AFTER tool markers (more specific patterns first).
    for marker in CASUAL_MARKERS:
        if marker in q:
            return ("ambiguous", "casual")

    # General reasoning queries (pass through)
    # If the query doesn't match any state trigger and isn't casual/tool,
    # classify as ambiguous (non-state) and pass through.
    return ("ambiguous", "general_query")


def is_state_query(query_text: str) -> bool:
    """Check if the query is a state/self-state query.

    Returns True if the query matches Rules A–F (state query types).
    Returns False if the query is non-state (casual, tool, or general).
    """
    query_type, non_state_category = classify_query(query_text)
    return non_state_category is None


def handle_external_state_query(
    user_text: str,
    *,
    self_location: dict[str, Any] | None = None,
    agent_state: dict[str, Any] | None = None,
    memory_state: dict[str, Any] | None = None,
    repo_state: dict[str, Any] | None = None,
    host_state: dict[str, Any] | None = None,
    warnings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Handle an external state query and return a structured response.

    This is the primary public API for the external wrapper.

    Parameters
    ----------
    user_text : str
        The user's original query text (used for classification).
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
    dict
        A response dict with the following structure:

        If state query:
            {
                "handled": True,
                "route": "state_query",
                "query_type": "self_state" | "host_telemetry" | "runtime" |
                              "memory" | "identity" | "ambiguous",
                "response": StateQueryResponse,  # from build_state_query_response()
                "boundary_note": "external wrapper only; not runtime authority chain",
            }

        If non-state query:
            {
                "handled": False,
                "route": "pass_through",
                "non_state_category": "casual" | "tool_request" | "general_query",
                "user_text": str,  # original query, to be passed to normal runtime
                "response": None,
                "boundary_note": "non-state query should pass to normal Hermes/runtime path",
            }

    Contract guarantees:
    - The wrapper does NOT connect into the runtime authority chain.
    - Non-state queries are NOT hijacked — they are returned with the original
      user_text so the caller can pass them through the normal Hermes/runtime
      path (monitor → bridge → gate → verification → MainBrain).
    - The wrapper does NOT collect host telemetry.
    - The wrapper does NOT write to memory.
    - The wrapper does NOT claim completion or execute tasks.
    """
    query_type, non_state_category = classify_query(user_text)

    if non_state_category is not None:
        # Non-state query: return the original text for pass-through.
        return {
            "handled": False,
            "route": "pass_through",
            "non_state_category": non_state_category,
            "user_text": user_text,
            "response": None,
            "boundary_note": "non-state query should pass to normal Hermes/runtime path",
        }

    # State query: build and return the state response.
    response: StateQueryResponse = build_state_query_response(
        query_text=user_text,
        self_location=self_location,
        agent_state=agent_state,
        memory_state=memory_state,
        repo_state=repo_state,
        host_state=host_state,
        warnings=warnings,
    )

    return {
        "handled": True,
        "route": "state_query",
        "query_type": query_type,
        "response": response,
        "boundary_note": "external wrapper only; not runtime authority chain",
    }


# ---------------------------------------------------------------------------
# Convenience re-exports for external callers
# ---------------------------------------------------------------------------

__all__ = [
    "handle_external_state_query",
    "classify_query",
    "is_state_query",
    "StateQueryResponse",
    "QueryType",
    "NonStateCategory",
    "TOOL_MARKERS",
    "CASUAL_MARKERS",
]
