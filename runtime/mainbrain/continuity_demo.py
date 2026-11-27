from __future__ import annotations

from typing import TypedDict

from runtime.contracts.sleep_types import AgentIdentity, SleepSnapshot, WakeSanityResult
from runtime.sleep.controller import SleepWakeController


class MainBrainResumeDemo(TypedDict):
    resume_mode: str
    required_action: str
    held_claims: list[str]
    reasons: list[str]
    message: str
    snapshot_id: str | None


RESUME_ACTIONS = {
    "resume_full": "resume permitted",
    "resume_with_refresh": "refresh required before continuing",
    "resume_with_clarification": "clarification required before continuing",
    "resume_read_only": "read-only resume only",
    "restart_required": "restart required before continuing",
}


def consume_wake_decision(wake_result: WakeSanityResult | None, *, snapshot_id: str | None = None) -> MainBrainResumeDemo:
    if wake_result is None:
        return {
            "resume_mode": "restart_required",
            "required_action": "wake sanity required before continuing",
            "held_claims": ["cannot_claim_full_continuity"],
            "reasons": ["wake_sanity_missing"],
            "message": "wake sanity required before continuing",
            "snapshot_id": snapshot_id,
        }

    resume_mode = wake_result["resume_decision"]
    message = RESUME_ACTIONS[resume_mode]
    if resume_mode == "resume_full":
        message = "resume allowed under current wake checks"

    return {
        "resume_mode": resume_mode,
        "required_action": RESUME_ACTIONS[resume_mode],
        "held_claims": list(wake_result.get("held_claims", [])),
        "reasons": list(wake_result.get("reasons", [])),
        "message": message,
        "snapshot_id": snapshot_id,
    }


def resume_from_snapshot(
    snapshot: SleepSnapshot,
    *,
    expected_identity: AgentIdentity | None = None,
    expected_task_id: str | None = None,
    controller: SleepWakeController | None = None,
) -> MainBrainResumeDemo:
    active_controller = controller or SleepWakeController()
    wake_result = active_controller.wake(
        snapshot,
        expected_identity=expected_identity,
        expected_task_id=expected_task_id,
    )
    return consume_wake_decision(wake_result, snapshot_id=snapshot["snapshot_id"])
