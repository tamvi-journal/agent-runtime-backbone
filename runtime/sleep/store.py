from __future__ import annotations

from dataclasses import dataclass, field

from runtime.contracts.sleep_types import SleepSnapshot


@dataclass
class InMemorySleepSnapshotStore:
    """Small local store for dormant sleep/wake contract tests."""

    snapshots: dict[str, SleepSnapshot] = field(default_factory=dict)

    def upsert(self, snapshot: SleepSnapshot) -> SleepSnapshot:
        self.snapshots[snapshot["snapshot_id"]] = snapshot
        return snapshot

    def get(self, snapshot_id: str) -> SleepSnapshot | None:
        return self.snapshots.get(snapshot_id)

    def latest_for_task(self, task_id: str) -> SleepSnapshot | None:
        matches = [item for item in self.snapshots.values() if item["task_id"] == task_id]
        if not matches:
            return None
        return sorted(matches, key=lambda item: item["created_at"], reverse=True)[0]
