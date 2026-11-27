from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
APPLICATION_ID = 0x54534531  # "TSE1": Agent Skill Evolution v1
VALIDATION_OUTCOMES = {"accepted", "rejected", "blocked", "expired"}
RETRIEVAL_MODES = {"normal", "debug", "audit"}
DEFAULT_STATE_RELATIVE_PATH = Path(
    "runtime_state/skill_evolution/agent-skill-evolution.sqlite3"
)
APPEND_ONLY_TABLES = (
    "evidence_references",
    "pattern_revisions",
    "evolution_events",
    "skill_versions",
    "validation_decisions",
    "pointer_events",
    "operations",
    "operation_outcomes",
)


class IdempotencyConflict(RuntimeError):
    """An operation ID was reused with a different canonical payload."""


class ImmutableHistoryError(RuntimeError):
    """An update or delete attempted to rewrite append-only history."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _require_sha256(name: str, value: Any) -> str:
    value = _require_text(name, value)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_string_list(name: str, value: Any, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} must be a list of non-empty strings")
    if nonempty and not value:
        raise ValueError(f"{name} must not be empty")
    return list(value)


def _require_mapping(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{name} must be a non-empty mapping")
    return dict(value)


def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    for key in tuple(result):
        if key.endswith("_json"):
            result[key[:-5]] = json.loads(result.pop(key))
    return result


class SkillEvolutionStore:
    """Agent-owned immutable learning history with a single mutable pointer.

    This store is independent from the agent's identity Memory Core and from external
    Work Memory. Retrieval returns candidate procedural context, never truth or
    identity authority.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        clock: Callable[[], str] = _utc_now,
        authority_resolver: Callable[[str], Mapping[str, Any] | None] | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.clock = clock
        self.authority_resolver = authority_resolver or (lambda _receipt_id: None)

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
        except sqlite3.IntegrityError as error:
            if "append-only" in str(error):
                raise ImmutableHistoryError(str(error)) from error
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            application_id = int(conn.execute("PRAGMA application_id").fetchone()[0])
            user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            if application_id not in {0, APPLICATION_ID} or user_version > SCHEMA_VERSION:
                raise RuntimeError("foreign or newer skill-evolution database")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS evidence_references(
                    evidence_id TEXT PRIMARY KEY,
                    source_ref TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL CHECK(length(source_sha256)=64),
                    evidence_type TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pattern_revisions(
                    revision_id TEXT PRIMARY KEY,
                    pattern_id TEXT NOT NULL,
                    previous_revision_id TEXT REFERENCES pattern_revisions(revision_id),
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    proposer_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evolution_events(
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    refs_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS skill_versions(
                    version_id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    parent_version_id TEXT REFERENCES skill_versions(version_id),
                    content TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL CHECK(length(content_sha256)=64),
                    semantic_diff_json TEXT NOT NULL,
                    unified_diff TEXT NOT NULL,
                    motivating_incident_ids_json TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    proposer_json TEXT NOT NULL,
                    validation_plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS validation_decisions(
                    decision_id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    version_id TEXT NOT NULL REFERENCES skill_versions(version_id),
                    outcome TEXT NOT NULL CHECK(outcome IN ('accepted','rejected','blocked','expired')),
                    scores_json TEXT NOT NULL,
                    outputs_json TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    validator_json TEXT NOT NULL,
                    authority_receipt_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS active_pointers(
                    skill_id TEXT PRIMARY KEY,
                    active_version_id TEXT NOT NULL REFERENCES skill_versions(version_id),
                    updated_at TEXT NOT NULL,
                    authority_receipt_id TEXT NOT NULL,
                    decision_id TEXT REFERENCES validation_decisions(decision_id)
                );
                CREATE TABLE IF NOT EXISTS pointer_events(
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL CHECK(event_type IN ('promote','rollback')),
                    skill_id TEXT NOT NULL,
                    from_version_id TEXT,
                    to_version_id TEXT NOT NULL REFERENCES skill_versions(version_id),
                    decision_id TEXT,
                    reason TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    authority_receipt_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operations(
                    operation_id TEXT PRIMARY KEY,
                    operation_type TEXT NOT NULL,
                    operation_digest TEXT NOT NULL CHECK(length(operation_digest)=64),
                    result_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operation_outcomes(
                    operation_id TEXT PRIMARY KEY REFERENCES operations(operation_id),
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
    def _raise_rejected_operation(error_type: str, error_message: str) -> None:
        if error_type == "ImmutableHistoryError":
            raise ImmutableHistoryError(error_message)
        if error_type == "IdempotencyConflict":
            raise IdempotencyConflict(error_message)
        if error_type == "FileExistsError":
            raise FileExistsError(error_message)
        raise ValueError(error_message)

    def _operate(self, operation_type: str, operation_id: str, payload: dict[str, Any], action: Callable[[sqlite3.Connection], dict[str, Any]]) -> dict[str, Any]:
        _require_text("operation_id", operation_id)
        fingerprint = _digest({"operation_type": operation_type, "payload": payload})
        self.initialize()

        # Reserve the operation identity in its own committed transaction. This
        # survives a rejected action, so an operation ID can never be recycled
        # with a different payload after validation or policy failure.
        with self.connect() as conn:
            prior = conn.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            if prior:
                if prior["operation_digest"] != fingerprint:
                    raise IdempotencyConflict("operation_id already used with different content")
                outcome = conn.execute("SELECT * FROM operation_outcomes WHERE operation_id=?", (operation_id,)).fetchone()
                if not outcome:
                    raise RuntimeError("operation_id is durably reserved without a completed outcome; retry blocked")
                if outcome["status"] == "succeeded":
                    return json.loads(outcome["result_json"])
                self._raise_rejected_operation(outcome["error_type"], outcome["error_message"])
            conn.execute(
                "INSERT INTO operations VALUES(?,?,?,?,?)",
                (operation_id, operation_type, fingerprint, _canonical_json({"status": "reserved"}), self.clock()),
            )

        try:
            # The domain mutation and its success outcome commit atomically.
            with self.connect() as conn:
                result = action(conn)
                conn.execute(
                    "INSERT INTO operation_outcomes VALUES(?,?,?,?,?,?)",
                    (operation_id, "succeeded", _canonical_json(result), None, None, self.clock()),
                )
                return result
        except Exception as error:
            error_type = type(error).__name__
            error_message = str(error) or error_type
            # The failed domain transaction has rolled back. Append the durable
            # rejection separately without modifying the reservation.
            with self.connect() as conn:
                conn.execute(
                    "INSERT INTO operation_outcomes VALUES(?,?,?,?,?,?)",
                    (operation_id, "rejected", None, error_type, error_message, self.clock()),
                )
            raise

    @staticmethod
    def _ensure_evidence(conn: sqlite3.Connection, evidence_ids: list[str]) -> None:
        for evidence_id in evidence_ids:
            if not conn.execute("SELECT 1 FROM evidence_references WHERE evidence_id=?", (evidence_id,)).fetchone():
                raise ValueError(f"evidence reference not found: {evidence_id}")

    @staticmethod
    def _ensure_version(conn: sqlite3.Connection, skill_id: str, version_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM skill_versions WHERE skill_id=? AND version_id=?", (skill_id, version_id)).fetchone()
        if not row:
            raise ValueError("skill version not found")
        return row

    def _authority(self, receipt_id: str) -> dict[str, Any]:
        receipt = self.authority_resolver(_require_text("authority_receipt_id", receipt_id))
        if not receipt or receipt.get("receipt_id") != receipt_id or receipt.get("status") != "verified" or receipt.get("scope") != "agent-skill-promotion":
            raise ValueError("pointer movement requires a verified Agent authority receipt")
        return dict(receipt)

    def record_evidence_reference(self, *, operation_id: str, evidence_id: str, source_ref: str, source_sha256: str, evidence_type: str, observed_at: str, provenance: Mapping[str, Any]) -> dict[str, Any]:
        payload = {
            "evidence_id": _require_text("evidence_id", evidence_id),
            "source_ref": _require_text("source_ref", source_ref),
            "source_sha256": _require_sha256("source_sha256", source_sha256),
            "evidence_type": _require_text("evidence_type", evidence_type),
            "observed_at": _require_text("observed_at", observed_at),
            "provenance": _require_mapping("provenance", provenance),
        }
        def action(conn: sqlite3.Connection) -> dict[str, Any]:
            if conn.execute("SELECT 1 FROM evidence_references WHERE evidence_id=?", (evidence_id,)).fetchone():
                raise ValueError("evidence_id already exists and is immutable")
            stored = {**payload, "recorded_at": self.clock()}
            conn.execute("INSERT INTO evidence_references VALUES(?,?,?,?,?,?,?)", (evidence_id, source_ref, source_sha256, evidence_type, observed_at, _canonical_json(payload["provenance"]), stored["recorded_at"]))
            return stored
        return self._operate("record_evidence_reference", operation_id, payload, action)

    def record_pattern_revision(self, *, operation_id: str, pattern_id: str, revision_id: str, previous_revision_id: str | None, title: str, summary: str, evidence_ids: list[str], proposer: Mapping[str, Any]) -> dict[str, Any]:
        payload = {
            "pattern_id": _require_text("pattern_id", pattern_id), "revision_id": _require_text("revision_id", revision_id),
            "previous_revision_id": previous_revision_id, "title": _require_text("title", title), "summary": _require_text("summary", summary),
            "evidence_ids": _require_string_list("evidence_ids", evidence_ids, nonempty=True), "proposer": _require_mapping("proposer", proposer),
        }
        def action(conn: sqlite3.Connection) -> dict[str, Any]:
            self._ensure_evidence(conn, payload["evidence_ids"])
            history = conn.execute("SELECT revision_id FROM pattern_revisions WHERE pattern_id=? ORDER BY rowid", (pattern_id,)).fetchall()
            if previous_revision_id is None and history:
                raise ValueError("existing pattern requires previous_revision_id")
            if previous_revision_id is not None and (not history or history[-1]["revision_id"] != previous_revision_id):
                raise ValueError("previous pattern revision must be the latest revision")
            stored = {**payload, "recorded_at": self.clock()}
            conn.execute("INSERT INTO pattern_revisions VALUES(?,?,?,?,?,?,?,?)", (revision_id, pattern_id, previous_revision_id, title, summary, _canonical_json(payload["evidence_ids"]), _canonical_json(payload["proposer"]), stored["recorded_at"]))
            return stored
        return self._operate("record_pattern_revision", operation_id, payload, action)

    def append_evolution_event(self, *, operation_id: str, event_id: str, event_type: str, refs: list[str], summary: str, provenance: Mapping[str, Any]) -> dict[str, Any]:
        payload = {"event_id": _require_text("event_id", event_id), "event_type": _require_text("event_type", event_type), "refs": _require_string_list("refs", refs, nonempty=True), "summary": _require_text("summary", summary), "provenance": _require_mapping("provenance", provenance)}
        def action(conn: sqlite3.Connection) -> dict[str, Any]:
            stored = {**payload, "recorded_at": self.clock()}
            conn.execute("INSERT INTO evolution_events VALUES(?,?,?,?,?,?)", (event_id, event_type, _canonical_json(payload["refs"]), summary, _canonical_json(payload["provenance"]), stored["recorded_at"]))
            return stored
        return self._operate("append_evolution_event", operation_id, payload, action)

    def propose_skill_version(self, *, operation_id: str, skill_id: str, version_id: str, parent_version_id: str | None, content: str, semantic_diff: Mapping[str, Any], unified_diff: str, motivating_incident_ids: list[str], evidence_ids: list[str], proposer: Mapping[str, Any], validation_plan: Mapping[str, Any]) -> dict[str, Any]:
        payload = {
            "skill_id": _require_text("skill_id", skill_id), "version_id": _require_text("version_id", version_id), "parent_version_id": parent_version_id,
            "content": _require_text("content", content), "semantic_diff": _require_mapping("semantic_diff", semantic_diff), "unified_diff": _require_text("unified_diff", unified_diff),
            "motivating_incident_ids": _require_string_list("motivating_incident_ids", motivating_incident_ids, nonempty=True), "evidence_ids": _require_string_list("evidence_ids", evidence_ids, nonempty=True),
            "proposer": _require_mapping("proposer", proposer), "validation_plan": _require_mapping("validation_plan", validation_plan),
        }
        def action(conn: sqlite3.Connection) -> dict[str, Any]:
            self._ensure_evidence(conn, payload["evidence_ids"])
            versions = conn.execute("SELECT version_id FROM skill_versions WHERE skill_id=?", (skill_id,)).fetchall()
            if parent_version_id is None and versions:
                raise ValueError("existing skill requires parent_version_id")
            if parent_version_id is not None and not conn.execute("SELECT 1 FROM skill_versions WHERE skill_id=? AND version_id=?", (skill_id, parent_version_id)).fetchone():
                raise ValueError("parent skill version not found")
            stored = {**payload, "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(), "created_at": self.clock()}
            conn.execute("INSERT INTO skill_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (version_id, skill_id, parent_version_id, content, stored["content_sha256"], _canonical_json(payload["semantic_diff"]), unified_diff, _canonical_json(payload["motivating_incident_ids"]), _canonical_json(payload["evidence_ids"]), _canonical_json(payload["proposer"]), _canonical_json(payload["validation_plan"]), stored["created_at"]))
            return stored
        return self._operate("propose_skill_version", operation_id, payload, action)

    def record_validation_decision(self, *, operation_id: str, decision_id: str, skill_id: str, version_id: str, outcome: str, scores: Mapping[str, Any], outputs: list[Mapping[str, Any]], reason: str, validator: Mapping[str, Any], authority_receipt: Mapping[str, Any]) -> dict[str, Any]:
        if outcome not in VALIDATION_OUTCOMES:
            raise ValueError("invalid validation outcome")
        score_map = _require_mapping("scores", scores)
        for value in score_map.values():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= float(value) <= 1:
                raise ValueError("validation scores must be numbers from 0 to 1")
        output_list = [dict(item) for item in outputs]
        if not output_list or any(not item.get("ref") for item in output_list):
            raise ValueError("validation outputs require references")
        payload = {"decision_id": _require_text("decision_id", decision_id), "skill_id": _require_text("skill_id", skill_id), "version_id": _require_text("version_id", version_id), "outcome": outcome, "scores": score_map, "outputs": output_list, "reason": _require_text("reason", reason), "validator": _require_mapping("validator", validator), "authority_receipt": _require_mapping("authority_receipt", authority_receipt)}
        def action(conn: sqlite3.Connection) -> dict[str, Any]:
            self._ensure_version(conn, skill_id, version_id)
            stored = {**payload, "recorded_at": self.clock()}
            conn.execute("INSERT INTO validation_decisions VALUES(?,?,?,?,?,?,?,?,?,?)", (decision_id, skill_id, version_id, outcome, _canonical_json(score_map), _canonical_json(output_list), reason, _canonical_json(payload["validator"]), _canonical_json(payload["authority_receipt"]), stored["recorded_at"]))
            return stored
        return self._operate("record_validation_decision", operation_id, payload, action)

    def promote(self, *, operation_id: str, skill_id: str, version_id: str, expected_active_version_id: str | None, decision_id: str, authority_receipt_id: str) -> dict[str, Any]:
        payload = {"skill_id": _require_text("skill_id", skill_id), "version_id": _require_text("version_id", version_id), "expected_active_version_id": expected_active_version_id, "decision_id": _require_text("decision_id", decision_id), "authority_receipt_id": _require_text("authority_receipt_id", authority_receipt_id)}
        def action(conn: sqlite3.Connection) -> dict[str, Any]:
            receipt = self._authority(authority_receipt_id)
            version = self._ensure_version(conn, skill_id, version_id)
            decision = conn.execute("SELECT * FROM validation_decisions WHERE decision_id=? AND skill_id=? AND version_id=?", (decision_id, skill_id, version_id)).fetchone()
            if not decision or decision["outcome"] != "accepted":
                raise ValueError("promotion requires an accepted validation decision")
            current = conn.execute("SELECT * FROM active_pointers WHERE skill_id=?", (skill_id,)).fetchone()
            current_id = current["active_version_id"] if current else None
            if current_id != expected_active_version_id or version["parent_version_id"] != expected_active_version_id:
                raise ValueError("active pointer or candidate parent mismatch")
            now = self.clock()
            conn.execute("INSERT INTO active_pointers VALUES(?,?,?,?,?) ON CONFLICT(skill_id) DO UPDATE SET active_version_id=excluded.active_version_id,updated_at=excluded.updated_at,authority_receipt_id=excluded.authority_receipt_id,decision_id=excluded.decision_id", (skill_id, version_id, now, authority_receipt_id, decision_id))
            event_id = "pointer-event:" + _digest({"operation_id": operation_id})[:32]
            conn.execute("INSERT INTO pointer_events VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id, "promote", skill_id, current_id, version_id, decision_id, "accepted validation and verified authority", "[]", _canonical_json(receipt), now))
            return {"skill_id": skill_id, "active_version_id": version_id, "updated_at": now, "authority_receipt_id": authority_receipt_id, "decision_id": decision_id}
        return self._operate("promote", operation_id, payload, action)

    def rollback(self, *, operation_id: str, skill_id: str, from_version_id: str, to_version_id: str, reason: str, evidence_ids: list[str], authority_receipt_id: str) -> dict[str, Any]:
        payload = {"skill_id": _require_text("skill_id", skill_id), "from_version_id": _require_text("from_version_id", from_version_id), "to_version_id": _require_text("to_version_id", to_version_id), "reason": _require_text("reason", reason), "evidence_ids": _require_string_list("evidence_ids", evidence_ids, nonempty=True), "authority_receipt_id": _require_text("authority_receipt_id", authority_receipt_id)}
        def action(conn: sqlite3.Connection) -> dict[str, Any]:
            receipt = self._authority(authority_receipt_id)
            self._ensure_evidence(conn, payload["evidence_ids"])
            self._ensure_version(conn, skill_id, to_version_id)
            current = conn.execute("SELECT * FROM active_pointers WHERE skill_id=?", (skill_id,)).fetchone()
            if not current or current["active_version_id"] != from_version_id:
                raise ValueError("rollback source is not active")
            if not conn.execute("SELECT 1 FROM pointer_events WHERE skill_id=? AND to_version_id=?", (skill_id, to_version_id)).fetchone():
                raise ValueError("rollback target was never active")
            now = self.clock()
            conn.execute("UPDATE active_pointers SET active_version_id=?,updated_at=?,authority_receipt_id=?,decision_id=NULL WHERE skill_id=?", (to_version_id, now, authority_receipt_id, skill_id))
            event_id = "pointer-event:" + _digest({"operation_id": operation_id})[:32]
            conn.execute("INSERT INTO pointer_events VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id, "rollback", skill_id, from_version_id, to_version_id, None, reason, _canonical_json(payload["evidence_ids"]), _canonical_json(receipt), now))
            return {"skill_id": skill_id, "active_version_id": to_version_id, "updated_at": now, "authority_receipt_id": authority_receipt_id, "decision_id": None}
        return self._operate("rollback", operation_id, payload, action)

    def _rows(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        with self.connect(readonly=True) as conn:
            return [_decode(row) for row in conn.execute(query, params).fetchall()]  # type: ignore[misc]

    def pattern_history(self, pattern_id: str) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM pattern_revisions WHERE pattern_id=? ORDER BY rowid", (pattern_id,))

    def evolution_log(self) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM evolution_events ORDER BY rowid")

    def skill_history(self, skill_id: str) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM skill_versions WHERE skill_id=? ORDER BY rowid", (skill_id,))

    def validation_history(self, skill_id: str) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM validation_decisions WHERE skill_id=? ORDER BY rowid", (skill_id,))

    def pointer_history(self, skill_id: str) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM pointer_events WHERE skill_id=? ORDER BY rowid", (skill_id,))

    def retrieve(self, cue: str, *, mode: str = "normal", budget_chars: int = 6000, current_instruction: str | None = None) -> dict[str, Any]:
        if mode not in RETRIEVAL_MODES:
            raise ValueError("mode must be normal, debug, or audit")
        _require_text("cue", cue)
        if not isinstance(budget_chars, int) or budget_chars < 1:
            raise ValueError("budget_chars must be positive")
        tokens = {token for token in re.findall(r"[a-z0-9]+", cue.lower()) if len(token) > 1}
        versions = self._rows("SELECT v.*,p.active_version_id FROM skill_versions v LEFT JOIN active_pointers p ON p.skill_id=v.skill_id ORDER BY v.rowid")
        matches = [row for row in versions if tokens & set(re.findall(r"[a-z0-9]+", (row["skill_id"] + " " + row["content"]).lower()))]
        active = next((row for row in reversed(matches) if row.get("active_version_id") == row["version_id"]), None)
        result: dict[str, Any] = {
            "mode": mode,
            "cue": cue,
            "authority_note": "candidate procedural context only; retrieval is not truth or identity authority",
            "active_version": active,
        }
        if current_instruction is not None:
            result["current_instruction"] = current_instruction
            result["instruction_precedence"] = "current_instruction_supersedes_active_context"
        if mode in {"debug", "audit"}:
            result["candidate_summaries"] = [{"skill_id": row["skill_id"], "version_id": row["version_id"], "parent_version_id": row["parent_version_id"], "content_sha256": row["content_sha256"]} for row in matches]
        if mode == "audit":
            skill_ids = sorted({row["skill_id"] for row in matches})
            result["version_history"] = [row for skill_id in skill_ids for row in self.skill_history(skill_id)]
            result["validation_history"] = [row for skill_id in skill_ids for row in self.validation_history(skill_id)]
            result["pointer_history"] = [row for skill_id in skill_ids for row in self.pointer_history(skill_id)]
            result["evolution_log"] = self.evolution_log()
        if len(_canonical_json(result).encode("utf-8")) > budget_chars:
            raise ValueError("retrieval packet exceeds requested budget")
        return result

    def unsafe_update_for_test(self, table: str, key_name: str, key_value: str) -> None:
        """Exercise database immutability triggers; never used by runtime paths."""
        if table not in APPEND_ONLY_TABLES or not re.fullmatch(r"[a-z_]+", key_name):
            raise ValueError("unsafe test target")
        self.initialize()
        with self.connect() as conn:
            conn.execute(f"UPDATE {table} SET {key_name}={key_name} WHERE {key_name}=?", (key_value,))


class HermesSkillProjection:
    """Disabled-by-default, create-only projection into a supplied skill root."""

    def __init__(self, store: SkillEvolutionStore, target_root: str | Path) -> None:
        self.store = store
        self.target_root = Path(target_root)

    def project(self, *, skill_id: str, enabled: bool = False) -> dict[str, Any]:
        if not enabled:
            return {"status": "disabled", "reason": "projection requires explicit enablement after safety validation"}
        pointer_rows = self.store._rows("SELECT * FROM active_pointers WHERE skill_id=?", (skill_id,))
        if not pointer_rows:
            raise ValueError("skill has no active version")
        active_id = pointer_rows[0]["active_version_id"]
        versions = [row for row in self.store.skill_history(skill_id) if row["version_id"] == active_id]
        if not versions:
            raise ValueError("active version not found")
        name = skill_id.split(":")[-1]
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
            raise ValueError("skill_id cannot be projected safely")
        skill_dir = self.target_root / name
        skill_file = skill_dir / "SKILL.md"
        if skill_dir.exists() or skill_file.exists():
            raise FileExistsError("projection refuses to overwrite an existing skill path")
        skill_dir.mkdir(parents=True, exist_ok=False)
        content = versions[0]["content"]
        skill_file.write_text(content, encoding="utf-8")
        readback = skill_file.read_bytes()
        if hashlib.sha256(readback).hexdigest() != versions[0]["content_sha256"]:
            raise RuntimeError("projection readback hash mismatch")
        return {"status": "created", "path": str(skill_file), "version_id": active_id, "content_sha256": versions[0]["content_sha256"]}


def create_agent_skill_evolution_store(
    repo_root: str | Path,
    *,
    clock: Callable[[], str] = _utc_now,
    authority_resolver: Callable[[str], Mapping[str, Any] | None] | None = None,
) -> SkillEvolutionStore:
    """Open the agent's separate local evolution store at its canonical path.

    The default resolver authorizes no pointer movement. A caller must inject a
    verifier that returns a scoped, verified Agent authority receipt before a
    version can be promoted or rolled back.
    """

    store = SkillEvolutionStore(
        Path(repo_root) / DEFAULT_STATE_RELATIVE_PATH,
        clock=clock,
        authority_resolver=authority_resolver,
    )
    store.initialize()
    return store
