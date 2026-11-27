from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
APPLICATION_ID = 0x54574D31  # "TWM1": Agent Work Memory v1
ROUTINE_KINDS = {
    "instruction",
    "decision",
    "progress",
    "blocker",
    "correction",
    "branch_open",
    "branch_switch",
    "branch_park",
    "synthesis",
    "handoff",
    "outcome",
}
CHECKPOINT_KINDS = ROUTINE_KINDS | {"contract_anchor"}
BRANCH_STATUSES = {"open", "exploring", "distilled", "merged", "parked"}
TASK_STATUSES = {"active", "waiting", "blocked", "complete", "abandoned"}
APPEND_ONLY_TABLES = (
    "work_events",
    "work_operations",
    "work_operation_outcomes",
)
DEFAULT_STATE_RELATIVE_PATH = Path(
    "runtime_state/work_memory/agent-work-memory.sqlite3"
)
_MISSING = object()
_DELTA_PATTERN = re.compile(
    r"<!--AGENT_WORK_DELTA\s*(\{.*?\})\s*-->",
    re.DOTALL,
)
_CONTRACT_READ_PATTERN = re.compile(
    r"\[agent-work-contract:(task:[A-Za-z0-9._:-]+)\]",
    re.IGNORECASE,
)


class WorkOperationConflict(RuntimeError):
    """An operation ID was reused with different canonical content."""


class WorkOperationIncomplete(RuntimeError):
    """An operation was reserved but has no durable terminal outcome."""


class WorkRevisionConflict(RuntimeError):
    """A writer attempted to replace a newer work projection."""

    def __init__(self, task_id: str, revision: int, status: str) -> None:
        super().__init__("work-memory revision conflict")
        self.latest = {
            "task_id": task_id,
            "revision": revision,
            "status": status,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_text(name: str, value: Any, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    if len(value) > maximum:
        raise ValueError(f"{name} must not exceed {maximum} characters")
    return value.strip()


def _require_identifier(name: str, value: Any, prefix: str | None = None) -> str:
    value = _require_text(name, value, maximum=200)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", value):
        raise ValueError(f"{name} must be an opaque identifier")
    if prefix and not value.startswith(prefix + ":"):
        raise ValueError(f"{name} must start with {prefix}:")
    return value


def _require_string_list(
    name: str,
    value: Any,
    *,
    maximum_items: int = 20,
    maximum_item_chars: int = 500,
    nonempty: bool = False,
) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum_items:
        raise ValueError(f"{name} must be a bounded list")
    cleaned = [
        _require_text(f"{name} item", item, maximum=maximum_item_chars)
        for item in value
    ]
    if nonempty and not cleaned:
        raise ValueError(f"{name} must not be empty")
    return cleaned


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 1
    }


def _decode_json_fields(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    value = dict(row)
    for key in tuple(value):
        if key.endswith("_json"):
            value[key[:-5]] = json.loads(value.pop(key))
    return value


class AgentWorkMemoryStore:
    """Agent-owned, cue-first work continuity with immutable event history.

    This store is separate from external Work Memory, the agent's identity Memory Core,
    and the agent's slow skill-evolution database. Its events are candidate work
    context, never identity or truth authority.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self.db_path = Path(db_path)
        self.clock = clock
        self.initialize()

    @contextmanager
    def connect(self, *, readonly: bool = False):
        if readonly:
            if not self.db_path.exists():
                raise FileNotFoundError(self.db_path)
            conn = sqlite3.connect(f"{self.db_path.resolve().as_uri()}?mode=ro", uri=True)
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            if readonly:
                yield conn
            else:
                with conn:
                    yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            application_id = int(conn.execute("PRAGMA application_id").fetchone()[0])
            user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            if application_id not in {0, APPLICATION_ID} or user_version > SCHEMA_VERSION:
                raise RuntimeError("foreign or newer Agent work-memory database")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS work_tasks(
                    task_id TEXT PRIMARY KEY,
                    cluster TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','waiting','blocked','complete','abandoned')),
                    revision INTEGER NOT NULL CHECK(revision > 0),
                    goal TEXT NOT NULL,
                    current_instruction TEXT,
                    cue_terms_json TEXT NOT NULL,
                    active_branch_id TEXT,
                    open_loops_json TEXT NOT NULL,
                    next_action TEXT,
                    waiting_on TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS work_branches(
                    branch_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES work_tasks(task_id),
                    label TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    cue_terms_json TEXT NOT NULL,
                    return_point TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('open','exploring','distilled','merged','parked')),
                    revision INTEGER NOT NULL,
                    last_checkpoint_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS work_events(
                    event_id TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL UNIQUE,
                    task_id TEXT NOT NULL REFERENCES work_tasks(task_id),
                    session_id TEXT NOT NULL,
                    surface TEXT NOT NULL,
                    cluster TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    branch_id TEXT,
                    contract_version INTEGER,
                    previous_contract_anchor_id TEXT,
                    provenance_refs_json TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS work_operations(
                    operation_id TEXT PRIMARY KEY,
                    operation_type TEXT NOT NULL,
                    operation_digest TEXT NOT NULL CHECK(length(operation_digest)=64),
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS work_operation_outcomes(
                    operation_id TEXT PRIMARY KEY REFERENCES work_operations(operation_id),
                    status TEXT NOT NULL CHECK(status IN ('succeeded','rejected')),
                    result_json TEXT,
                    error_type TEXT,
                    error_message TEXT,
                    recorded_at TEXT NOT NULL,
                    CHECK(
                        (status='succeeded' AND result_json IS NOT NULL AND error_type IS NULL AND error_message IS NULL)
                        OR
                        (status='rejected' AND result_json IS NULL AND error_type IS NOT NULL AND error_message IS NOT NULL)
                    )
                );
                """
            )
            for table in APPEND_ONLY_TABLES:
                conn.executescript(
                    f"""
                    CREATE TRIGGER IF NOT EXISTS {table}_no_update
                    BEFORE UPDATE ON {table}
                    BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END;
                    CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                    BEFORE DELETE ON {table}
                    BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END;
                    """
                )
            conn.execute(f"PRAGMA application_id={APPLICATION_ID}")
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @staticmethod
    def _raise_rejected(error_type: str, message: str) -> None:
        if error_type == "WorkRevisionConflict":
            raise ValueError(message)
        if error_type == "WorkOperationConflict":
            raise WorkOperationConflict(message)
        raise ValueError(message)

    def _operate(
        self,
        operation_type: str,
        operation_id: str,
        payload: dict[str, Any],
        action: Callable[[sqlite3.Connection], dict[str, Any]],
    ) -> dict[str, Any]:
        operation_id = _require_identifier("operation_id", operation_id, "operation")
        fingerprint = _digest({"operation_type": operation_type, "payload": payload})
        with self.connect() as conn:
            prior = conn.execute(
                "SELECT * FROM work_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if prior:
                if prior["operation_digest"] != fingerprint:
                    raise WorkOperationConflict(
                        "operation_id already used with different content"
                    )
                outcome = conn.execute(
                    "SELECT * FROM work_operation_outcomes WHERE operation_id=?",
                    (operation_id,),
                ).fetchone()
                if not outcome:
                    raise WorkOperationIncomplete(
                        "operation_id is reserved without a completed outcome"
                    )
                if outcome["status"] == "succeeded":
                    return json.loads(outcome["result_json"])
                self._raise_rejected(outcome["error_type"], outcome["error_message"])
            conn.execute(
                "INSERT INTO work_operations VALUES(?,?,?,?)",
                (operation_id, operation_type, fingerprint, self.clock()),
            )

        try:
            with self.connect() as conn:
                result = action(conn)
                conn.execute(
                    "INSERT INTO work_operation_outcomes VALUES(?,?,?,?,?,?)",
                    (
                        operation_id,
                        "succeeded",
                        _canonical_json(result),
                        None,
                        None,
                        self.clock(),
                    ),
                )
                return result
        except Exception as error:
            with self.connect() as conn:
                conn.execute(
                    "INSERT INTO work_operation_outcomes VALUES(?,?,?,?,?,?)",
                    (
                        operation_id,
                        "rejected",
                        None,
                        type(error).__name__,
                        str(error) or type(error).__name__,
                        self.clock(),
                    ),
                )
            raise

    @staticmethod
    def _branch_input(value: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"label", "purpose", "cue_terms", "return_point"}
        if set(value) - allowed:
            raise ValueError("branch contains unknown fields")
        return {
            "label": _require_text("branch.label", value.get("label"), maximum=160),
            "purpose": _require_text("branch.purpose", value.get("purpose"), maximum=1000),
            "cue_terms": _require_string_list(
                "branch.cue_terms",
                value.get("cue_terms"),
                maximum_items=12,
                maximum_item_chars=80,
                nonempty=True,
            ),
            "return_point": _require_text(
                "branch.return_point", value.get("return_point"), maximum=1000
            ),
        }

    @staticmethod
    def _task_projection(conn: sqlite3.Connection, task_id: str) -> dict[str, Any]:
        task = _decode_json_fields(
            conn.execute("SELECT * FROM work_tasks WHERE task_id=?", (task_id,)).fetchone()
        )
        if not task:
            raise ValueError("work-memory task not found")
        branches = [
            _decode_json_fields(row)
            for row in conn.execute(
                "SELECT * FROM work_branches WHERE task_id=? ORDER BY rowid",
                (task_id,),
            ).fetchall()
        ]
        task["branches"] = branches
        return task

    def open_work(
        self,
        *,
        operation_id: str,
        session_id: str,
        surface: str,
        cluster: str,
        goal: str,
        cue_terms: list[str],
        initial_branch: Mapping[str, Any],
        current_instruction: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "session_id": _require_identifier("session_id", session_id),
            "surface": _require_text("surface", surface, maximum=80),
            "cluster": _require_text("cluster", cluster, maximum=120),
            "goal": _require_text("goal", goal, maximum=1000),
            "cue_terms": _require_string_list(
                "cue_terms", cue_terms, maximum_items=12, maximum_item_chars=80, nonempty=True
            ),
            "initial_branch": self._branch_input(initial_branch),
            "current_instruction": (
                _require_text("current_instruction", current_instruction, maximum=2000)
                if current_instruction is not None
                else None
            ),
        }

        def action(conn: sqlite3.Connection) -> dict[str, Any]:
            now = self.clock()
            task_id = f"task:{uuid.uuid4()}"
            branch_id = f"branch:{uuid.uuid4()}"
            event_id = f"checkpoint:{uuid.uuid4()}"
            conn.execute(
                "INSERT INTO work_tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    task_id,
                    payload["cluster"],
                    "active",
                    1,
                    payload["goal"],
                    payload["current_instruction"],
                    _canonical_json(payload["cue_terms"]),
                    branch_id,
                    "[]",
                    None,
                    None,
                    now,
                    now,
                ),
            )
            branch = payload["initial_branch"]
            conn.execute(
                "INSERT INTO work_branches VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    branch_id,
                    task_id,
                    branch["label"],
                    branch["purpose"],
                    _canonical_json(branch["cue_terms"]),
                    branch["return_point"],
                    "exploring",
                    1,
                    event_id,
                    now,
                    now,
                ),
            )
            event = {
                "event_id": event_id,
                "operation_id": operation_id,
                "task_id": task_id,
                "session_id": payload["session_id"],
                "surface": payload["surface"],
                "cluster": payload["cluster"],
                "kind": "open",
                "summary": payload["goal"],
                "revision": 1,
                "branch_id": branch_id,
                "contract_version": None,
                "previous_contract_anchor_id": None,
                "provenance_refs": [],
                "details": {"branch": {"branch_id": branch_id, **branch}},
                "recorded_at": now,
            }
            self._insert_event(conn, event)
            return {"event": event, "projection": self._task_projection(conn, task_id)}

        return self._operate("open_work", operation_id, payload, action)

    @staticmethod
    def _insert_event(conn: sqlite3.Connection, event: dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO work_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                event["event_id"],
                event["operation_id"],
                event["task_id"],
                event["session_id"],
                event["surface"],
                event["cluster"],
                event["kind"],
                event["summary"],
                event["revision"],
                event.get("branch_id"),
                event.get("contract_version"),
                event.get("previous_contract_anchor_id"),
                _canonical_json(event.get("provenance_refs", [])),
                _canonical_json(event.get("details", {})),
                event["recorded_at"],
            ),
        )

    def checkpoint(
        self,
        *,
        operation_id: str,
        task_id: str,
        expected_revision: int,
        session_id: str,
        surface: str,
        kind: str,
        summary: str,
        branch_id: str | None = None,
        branch: Mapping[str, Any] | None = None,
        branch_status: str | None = None,
        provenance_refs: list[str] | None = None,
        open_loops: list[str] | object = _MISSING,
        next_action: str | None | object = _MISSING,
        waiting_on: str | None | object = _MISSING,
    ) -> dict[str, Any]:
        if kind not in CHECKPOINT_KINDS:
            raise ValueError("invalid work-memory checkpoint kind")
        maximum = 8000 if kind == "contract_anchor" else 1000
        clean_summary = _require_text("summary", summary, maximum=maximum)
        if not isinstance(expected_revision, int) or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        if branch_status is not None and branch_status not in BRANCH_STATUSES:
            raise ValueError("invalid branch status")
        refs = _require_string_list(
            "provenance_refs", provenance_refs or [], maximum_items=20, maximum_item_chars=500
        )
        if kind == "contract_anchor" and not refs:
            raise ValueError("contract_anchor requires provenance_refs")
        if kind == "outcome":
            if not refs:
                raise ValueError("outcome requires provenance_refs")
            if open_loops is _MISSING or next_action is _MISSING:
                raise ValueError("outcome requires explicit open_loops and next_action")
        if kind == "synthesis" and len([ref for ref in refs if ref.startswith("checkpoint:")]) < 2:
            raise ValueError("synthesis requires two checkpoint references")
        if kind == "branch_open" and branch is None:
            raise ValueError("branch_open requires a branch")
        if kind in {"branch_switch", "branch_park", "synthesis"} and branch_id is None:
            raise ValueError(f"{kind} requires branch_id")

        payload: dict[str, Any] = {
            "task_id": _require_identifier("task_id", task_id, "task"),
            "expected_revision": expected_revision,
            "session_id": _require_identifier("session_id", session_id),
            "surface": _require_text("surface", surface, maximum=80),
            "kind": kind,
            "summary": clean_summary,
            "branch_id": (
                _require_identifier("branch_id", branch_id, "branch")
                if branch_id is not None
                else None
            ),
            "branch": self._branch_input(branch) if branch is not None else None,
            "branch_status": branch_status,
            "provenance_refs": refs,
        }
        if open_loops is not _MISSING:
            payload["open_loops"] = _require_string_list(
                "open_loops", open_loops, maximum_items=20, maximum_item_chars=500
            )
        if next_action is not _MISSING:
            payload["next_action"] = (
                _require_text("next_action", next_action, maximum=1000)
                if next_action is not None
                else None
            )
        if waiting_on is not _MISSING:
            payload["waiting_on"] = (
                _require_text("waiting_on", waiting_on, maximum=500)
                if waiting_on is not None
                else None
            )

        def action(conn: sqlite3.Connection) -> dict[str, Any]:
            task = conn.execute("SELECT * FROM work_tasks WHERE task_id=?", (task_id,)).fetchone()
            if not task:
                raise ValueError("work-memory task not found")
            if task["revision"] != expected_revision:
                raise WorkRevisionConflict(task_id, task["revision"], task["status"])
            if task["status"] in {"complete", "abandoned"}:
                raise ValueError("terminal work-memory task cannot be checkpointed")

            prior_anchors = conn.execute(
                "SELECT * FROM work_events WHERE task_id=? AND kind='contract_anchor' ORDER BY rowid",
                (task_id,),
            ).fetchall()
            previous_anchor = prior_anchors[-1] if prior_anchors else None
            if kind == "contract_anchor" and previous_anchor and previous_anchor["event_id"] not in refs:
                raise ValueError(
                    "revised contract_anchor must reference the previous contract anchor"
                )

            now = self.clock()
            revision = expected_revision + 1
            event_id = f"checkpoint:{uuid.uuid4()}"
            selected_branch = branch_id or task["active_branch_id"]
            event_details: dict[str, Any] = {}

            if kind == "branch_open":
                selected_branch = f"branch:{uuid.uuid4()}"
                descriptor = payload["branch"]
                conn.execute(
                    "INSERT INTO work_branches VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        selected_branch,
                        task_id,
                        descriptor["label"],
                        descriptor["purpose"],
                        _canonical_json(descriptor["cue_terms"]),
                        descriptor["return_point"],
                        "exploring",
                        revision,
                        event_id,
                        now,
                        now,
                    ),
                )
                conn.execute(
                    "UPDATE work_tasks SET active_branch_id=? WHERE task_id=?",
                    (selected_branch, task_id),
                )
                event_details["branch"] = {"branch_id": selected_branch, **descriptor}
            elif selected_branch:
                selected = conn.execute(
                    "SELECT * FROM work_branches WHERE task_id=? AND branch_id=?",
                    (task_id, selected_branch),
                ).fetchone()
                if not selected:
                    raise ValueError("work-memory branch not found")
                next_branch_status = branch_status
                if kind == "branch_park":
                    next_branch_status = "parked"
                elif kind == "synthesis":
                    next_branch_status = "merged"
                elif kind == "branch_switch" and next_branch_status is None:
                    next_branch_status = "exploring"
                if kind != "contract_anchor":
                    conn.execute(
                        "UPDATE work_branches SET status=COALESCE(?,status),revision=?,last_checkpoint_id=?,updated_at=? WHERE branch_id=?",
                        (next_branch_status, revision, event_id, now, selected_branch),
                    )
                if kind == "branch_switch":
                    conn.execute(
                        "UPDATE work_tasks SET active_branch_id=? WHERE task_id=?",
                        (selected_branch, task_id),
                    )
                if kind == "branch_park" and task["active_branch_id"] == selected_branch:
                    replacement = conn.execute(
                        "SELECT branch_id FROM work_branches WHERE task_id=? AND branch_id<>? AND status NOT IN ('parked','merged') ORDER BY rowid LIMIT 1",
                        (task_id, selected_branch),
                    ).fetchone()
                    conn.execute(
                        "UPDATE work_tasks SET active_branch_id=? WHERE task_id=?",
                        (replacement["branch_id"] if replacement else None, task_id),
                    )

            assignments = ["revision=?", "updated_at=?"]
            values: list[Any] = [revision, now]
            if "open_loops" in payload:
                assignments.append("open_loops_json=?")
                values.append(_canonical_json(payload["open_loops"]))
            if "next_action" in payload:
                assignments.append("next_action=?")
                values.append(payload["next_action"])
            if "waiting_on" in payload:
                assignments.append("waiting_on=?")
                values.append(payload["waiting_on"])
            if kind == "blocker":
                assignments.append("status='blocked'")
            elif kind in {"correction", "instruction", "outcome"}:
                assignments.append("status='active'")
            if kind in {"instruction", "correction", "synthesis"}:
                assignments.append("current_instruction=?")
                values.append(clean_summary)
            values.append(task_id)
            conn.execute(
                f"UPDATE work_tasks SET {','.join(assignments)} WHERE task_id=?",
                tuple(values),
            )

            event = {
                "event_id": event_id,
                "operation_id": operation_id,
                "task_id": task_id,
                "session_id": payload["session_id"],
                "surface": payload["surface"],
                "cluster": task["cluster"],
                "kind": kind,
                "summary": clean_summary,
                "revision": revision,
                "branch_id": selected_branch,
                "contract_version": len(prior_anchors) + 1 if kind == "contract_anchor" else None,
                "previous_contract_anchor_id": previous_anchor["event_id"] if kind == "contract_anchor" and previous_anchor else None,
                "provenance_refs": refs,
                "details": event_details,
                "recorded_at": now,
            }
            self._insert_event(conn, event)
            return {"event": event, "projection": self._task_projection(conn, task_id)}

        return self._operate("checkpoint", operation_id, payload, action)

    def compact_index(self) -> list[dict[str, Any]]:
        with self.connect(readonly=True) as conn:
            tasks = conn.execute(
                "SELECT * FROM work_tasks WHERE status IN ('active','waiting','blocked') ORDER BY updated_at DESC"
            ).fetchall()
            output = []
            for task in tasks:
                branches = conn.execute(
                    "SELECT label,cue_terms_json FROM work_branches WHERE task_id=? ORDER BY rowid",
                    (task["task_id"],),
                ).fetchall()
                labels = list(json.loads(task["cue_terms_json"]))
                for branch in branches:
                    labels.extend([branch["label"], *json.loads(branch["cue_terms_json"])])
                output.append(
                    {
                        "task_id": task["task_id"],
                        "cluster": task["cluster"],
                        "status": task["status"],
                        "revision": task["revision"],
                        "updated_at": task["updated_at"],
                        "cue_labels": list(dict.fromkeys(labels))[:12],
                    }
                )
            return output

    def route(self, cue: str, *, limit: int = 3) -> list[dict[str, Any]]:
        cue = _require_text("cue", cue, maximum=8000)
        cue_tokens = _tokens(cue)
        ranked: list[tuple[int, dict[str, Any]]] = []
        for item in self.compact_index():
            labels = " ".join([item["cluster"], *item["cue_labels"]])
            score = len(cue_tokens & _tokens(labels))
            if item["task_id"] in cue:
                score += 100
            if score:
                ranked.append((score, item))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["task_id"]))
        if not ranked:
            return []
        # A generic shared label must not fan retrieval out into weaker tasks.
        # Only equally best exact cue matches are candidates for body loading.
        best_score = ranked[0][0]
        return [item for score, item in ranked if score == best_score][:limit]

    def context(
        self,
        cue: str,
        *,
        task_id: str | None = None,
        budget_chars: int | None = None,
        include_contract_anchor: bool = False,
        explicit_contract_opt_in: bool = False,
        contract_anchor_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(budget_chars, (int, type(None))) or (
            isinstance(budget_chars, int) and not 256 <= budget_chars <= 20000
        ):
            raise ValueError("budget_chars must be from 256 to 20000")
        routed = self.route(cue)
        if task_id is None:
            packet = {"candidates": routed}
        else:
            task_id = _require_identifier("task_id", task_id, "task")
            if task_id not in {item["task_id"] for item in routed}:
                raise ValueError("exact task was not selected by cue-first routing")
            if include_contract_anchor and not explicit_contract_opt_in:
                raise ValueError("contract retrieval requires explicit opt-in")
            if contract_anchor_id and not include_contract_anchor:
                raise ValueError("contract_anchor_id requires contract retrieval")
            with self.connect(readonly=True) as conn:
                projection = self._task_projection(conn, task_id)
                active_branch = next(
                    (
                        branch
                        for branch in projection["branches"]
                        if branch["branch_id"] == projection["active_branch_id"]
                    ),
                    None,
                )
                normal_event = None
                if active_branch:
                    row = conn.execute(
                        "SELECT * FROM work_events WHERE task_id=? AND branch_id=? AND kind<>'contract_anchor' ORDER BY rowid DESC LIMIT 1",
                        (task_id, active_branch["branch_id"]),
                    ).fetchone()
                    normal_event = _decode_json_fields(row)
                packet = {
                    "task_id": projection["task_id"],
                    "cluster": projection["cluster"],
                    "revision": projection["revision"],
                    "authority_note": "candidate work context only; current instruction wins",
                    "root": {
                        "goal": projection["goal"],
                        "current_instruction": projection["current_instruction"],
                        "status": projection["status"],
                        "open_loops": projection["open_loops"],
                        "next_action": projection["next_action"],
                        "waiting_on": projection["waiting_on"],
                    },
                    "branches": [
                        {
                            "branch_id": branch["branch_id"],
                            "label": branch["label"],
                            "status": branch["status"],
                            "return_point": branch["return_point"],
                            "revision": branch["revision"],
                        }
                        for branch in projection["branches"]
                    ],
                    "selected_branch": (
                        {
                            "branch_id": active_branch["branch_id"],
                            "purpose": active_branch["purpose"],
                            "last_checkpoint": normal_event,
                        }
                        if active_branch
                        else None
                    ),
                }
                if include_contract_anchor:
                    anchors = conn.execute(
                        "SELECT * FROM work_events WHERE task_id=? AND kind='contract_anchor' ORDER BY rowid",
                        (task_id,),
                    ).fetchall()
                    selected = None
                    if contract_anchor_id:
                        selected = next(
                            (row for row in anchors if row["event_id"] == contract_anchor_id),
                            None,
                        )
                        if selected is None:
                            raise ValueError("contract anchor not found for exact task")
                    elif anchors:
                        selected = anchors[-1]
                    packet["contract_anchor_index"] = [
                        {
                            "event_id": row["event_id"],
                            "contract_version": row["contract_version"],
                            "revision": row["revision"],
                            "recorded_at": row["recorded_at"],
                        }
                        for row in anchors
                    ]
                    packet["contract_anchor"] = (
                        {
                            "event_id": selected["event_id"],
                            "contract_version": selected["contract_version"],
                            "previous_contract_anchor_id": selected["previous_contract_anchor_id"],
                            "content": selected["summary"],
                            "provenance_refs": json.loads(selected["provenance_refs_json"]),
                            "recorded_at": selected["recorded_at"],
                        }
                        if selected
                        else None
                    )
        budget = budget_chars or (16000 if include_contract_anchor else 4000)
        if len(_canonical_json(packet)) > budget:
            raise ValueError("work-memory context exceeds requested budget")
        return packet

    def history(self, task_id: str) -> list[dict[str, Any]]:
        task_id = _require_identifier("task_id", task_id, "task")
        with self.connect(readonly=True) as conn:
            return [
                _decode_json_fields(row)
                for row in conn.execute(
                    "SELECT * FROM work_events WHERE task_id=? ORDER BY rowid",
                    (task_id,),
                ).fetchall()
            ]


class AgentWorkMemoryHook:
    """Hermes JSON-wire adapter that stores explicit material deltas only."""

    def __init__(self, store: AgentWorkMemoryStore) -> None:
        self.store = store

    @staticmethod
    def _marker_guidance(selected: dict[str, Any] | None) -> str:
        selected_hint = (
            f"Existing exact task is {selected['task_id']} at revision {selected['revision']}."
            if selected
            else "No exact task was selected; do not infer or bulk-load another task."
        )
        return (
            "Agent Work Memory rule: current user instruction is authoritative. "
            f"{selected_hint} If and only if this turn creates a material work-state delta "
            "(instruction, decision, durable outcome, blocker/correction, branch change, handoff, "
            "open loops, or next action), append one hidden HTML comment named AGENT_WORK_DELTA "
            "containing a JSON object with action=open or checkpoint and only the bounded delta fields. "
            "Never put transcript, hidden reasoning, prompts, commands, raw output, credentials, or "
            "unchanged conversation in that object. Ordinary summaries max 1000 characters; "
            "contract_anchor max 8000 with provenance and previous-anchor lineage. Checkpoints never "
            "modify skill patterns or versions."
        )

    def handle(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        event = payload.get("hook_event_name")
        extra = payload.get("extra") if isinstance(payload.get("extra"), Mapping) else {}
        if event == "pre_llm_call":
            user_message = str(extra.get("user_message") or "").strip()
            if not user_message:
                return {}
            routed = self.store.route(user_message)
            selected = routed[0] if len(routed) == 1 else None
            contract_match = _CONTRACT_READ_PATTERN.search(user_message)
            include_contract = bool(
                selected
                and contract_match
                and contract_match.group(1) == selected["task_id"]
            )
            context = (
                self.store.context(
                    user_message,
                    task_id=selected["task_id"],
                    include_contract_anchor=include_contract,
                    explicit_contract_opt_in=include_contract,
                    budget_chars=16000 if include_contract else 4000,
                )
                if selected
                else {"candidates": routed}
            )
            return {
                "context": "[Agent candidate work context]\n"
                + _canonical_json(context)
                + "\n\n"
                + self._marker_guidance(selected)
            }
        if event != "post_llm_call":
            return {"status": "ignored_event"}

        response = str(extra.get("assistant_response") or "")
        matches = _DELTA_PATTERN.findall(response)
        if not matches:
            return {"status": "ignored_no_material_delta"}
        if len(matches) != 1 or len(matches[0]) > 12000:
            return {"status": "rejected_invalid_delta"}
        try:
            delta = json.loads(matches[0])
        except json.JSONDecodeError:
            return {"status": "rejected_invalid_delta"}
        if not isinstance(delta, dict):
            return {"status": "rejected_invalid_delta"}

        action = delta.get("action")
        common_forbidden = {
            "transcript",
            "conversation_history",
            "raw_output",
            "prompt",
            "hidden_reasoning",
            "credential",
            "secret",
        }
        if common_forbidden & set(delta):
            return {"status": "rejected_forbidden_material"}
        session_id = str(payload.get("session_id") or extra.get("session_id") or "session:unknown")
        turn_id = str(extra.get("turn_id") or "turn:unknown")
        operation_id = "operation:hook:" + _digest(
            {"session_id": session_id, "turn_id": turn_id, "delta": delta}
        )[:32]
        surface = str(extra.get("platform") or "agent-hermes")

        if action == "open":
            allowed = {
                "action",
                "cluster",
                "goal",
                "cue_terms",
                "initial_branch",
                "current_instruction",
            }
            if set(delta) - allowed:
                return {"status": "rejected_unknown_fields"}
            result = self.store.open_work(
                operation_id=operation_id,
                session_id=session_id,
                surface=surface,
                cluster=delta.get("cluster"),
                goal=delta.get("goal"),
                cue_terms=delta.get("cue_terms"),
                initial_branch=delta.get("initial_branch"),
                current_instruction=delta.get("current_instruction"),
            )
        elif action == "checkpoint":
            allowed = {
                "action",
                "task_id",
                "expected_revision",
                "kind",
                "summary",
                "branch_id",
                "branch",
                "branch_status",
                "provenance_refs",
                "open_loops",
                "next_action",
                "waiting_on",
            }
            if set(delta) - allowed:
                return {"status": "rejected_unknown_fields"}
            kwargs = {
                key: value
                for key, value in delta.items()
                if key not in {"action"}
            }
            result = self.store.checkpoint(
                operation_id=operation_id,
                session_id=session_id,
                surface=surface,
                **kwargs,
            )
        else:
            return {"status": "rejected_unknown_action"}
        return {
            "status": "captured",
            "task_id": result["projection"]["task_id"],
            "revision": result["projection"]["revision"],
            "event_id": result["event"]["event_id"],
        }


def create_agent_work_memory_store(repo_root: str | Path) -> AgentWorkMemoryStore:
    return AgentWorkMemoryStore(Path(repo_root) / DEFAULT_STATE_RELATIVE_PATH)
