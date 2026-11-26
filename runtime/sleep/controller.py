from __future__ import annotations

from runtime.contracts.sleep_types import AgentIdentity, SleepSnapshot, WakeSanityResult
from runtime.sleep.snapshot import build_sleep_snapshot
from runtime.sleep.wake_sanity import run_wake_sanity_pass


class SleepWakeController:
    """Dormant coordinator for sleep/wake continuity checks."""

    def create_snapshot(self, **kwargs: object) -> SleepSnapshot:
        return build_sleep_snapshot(**kwargs)  # type: ignore[arg-type]

    def wake(
        self,
        snapshot: SleepSnapshot,
        *,
        expected_identity: AgentIdentity | None = None,
        expected_task_id: str | None = None,
    ) -> WakeSanityResult:
        return run_wake_sanity_pass(
            snapshot,
            expected_identity=expected_identity,
            expected_task_id=expected_task_id,
        )

    def resume_decision_for(
        self,
        snapshot: SleepSnapshot,
        *,
        expected_identity: AgentIdentity | None = None,
        expected_task_id: str | None = None,
    ) -> WakeSanityResult:
        return self.wake(
            snapshot,
            expected_identity=expected_identity,
            expected_task_id=expected_task_id,
        )
