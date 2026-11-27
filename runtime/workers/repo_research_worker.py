from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import os
import re
import stat

from runtime.security.secret_patterns import is_secret_path
from runtime.security.secret_scan import scan_text
from runtime.workers.preflight_guard import validate_worker_invocation_envelope

WORKER_ID = "repo_research_worker"
WORKER_TYPE = "read_only_repo_research"
OUTPUT_TYPE = "candidate_repo_findings"
DEFAULT_MAX_FILES = 5
DEFAULT_MAX_BYTES_PER_FILE = 20_000
DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "may",
    "not",
    "of",
    "on",
    "or",
    "only",
    "the",
    "to",
    "with",
    "worker",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return {str(key): val for key, val in value.items()}
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return []


def _as_string_list(value: Any) -> list[str]:
    return [item for item in _as_list(value) if isinstance(item, str)]


def _normalize_relative_path(text: str) -> Path:
    return Path(text)


def _within_root(candidate: Path, repo_root: Path) -> bool:
    try:
        candidate.relative_to(repo_root)
        return True
    except ValueError:
        return False


def _resolved_within_root(candidate: Path, repo_root: Path) -> bool:
    try:
        resolved_candidate = candidate.resolve(strict=False)
        resolved_root = repo_root.resolve(strict=False)
        resolved_candidate.relative_to(resolved_root)
        return True
    except (OSError, ValueError):
        return False


def _private_or_linked_path(candidate: Path, repo_root: Path) -> bool:
    try:
        rel = candidate.relative_to(repo_root)
    except ValueError:
        return True
    cursor = repo_root
    for part in rel.parts:
        cursor = cursor / part
        if (is_secret_path(part) or part in {".git", "runtime_state", ".ssh"}
                or cursor.is_symlink()):
            return True
    try:
        info = candidate.stat()
        return stat.S_ISREG(info.st_mode) and info.st_nlink != 1
    except OSError:
        return False


def _resolve_scoped_path(repo_root: Path, raw_path: str) -> tuple[Path | None, str | None]:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None, "empty_path"
    if is_secret_path(raw_path):
        return None, "secret_path_blocked"

    candidate = _normalize_relative_path(raw_path.strip())
    try:
        scoped = candidate if candidate.is_absolute() else repo_root / candidate
        scoped.resolve(strict=False)
    except OSError:
        return None, "unresolvable_path"

    if not _resolved_within_root(scoped, repo_root):
        return None, "path_escapes_repo_root"
    if _private_or_linked_path(scoped, repo_root):
        return None, "private_or_linked_path_blocked"
    return scoped, None


def _is_binary_like(data: bytes) -> bool:
    if not data:
        return False
    if b"\x00" in data:
        return True
    sample = data[:4096]
    textish = sum(1 for byte in sample if 32 <= byte <= 126 or byte in {9, 10, 13})
    return (textish / max(1, len(sample))) < 0.75


def _read_text_file(path: Path, max_bytes: int) -> tuple[str | None, dict[str, Any]]:
    info: dict[str, Any] = {
        "exists": path.exists(),
        "is_file": path.is_file(),
        "bytes_read": 0,
        "truncated": False,
        "binary_like": False,
    }
    if not path.exists():
        return None, info
    if not path.is_file():
        info["reason"] = "not_a_file"
        return None, info

    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        st = os.fstat(handle.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            info["reason"] = "not_a_private_regular_file"
            return None, info
        raw = handle.read(max_bytes + 1)
    info["bytes_read"] = min(len(raw), max_bytes)
    info["truncated"] = len(raw) > max_bytes
    raw = raw[:max_bytes]
    if _is_binary_like(raw):
        info["binary_like"] = True
        return None, info
    try:
        text = raw.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        info["binary_like"] = True
        return None, info
    return text, info


def _term_candidates(question: str) -> list[str]:
    terms: list[str] = []
    for term in re.findall(r"[a-z0-9_]+", question.lower()):
        if len(term) < 3 or term in STOPWORDS:
            continue
        if term not in terms:
            terms.append(term)
    return terms[:8]


def _snippets_for_terms(text: str, terms: Sequence[str], limit: int = 3) -> list[dict[str, Any]]:
    lowered = text.lower()
    snippets: list[dict[str, Any]] = []
    for term in terms:
        start = 0
        while len(snippets) < limit:
            idx = lowered.find(term, start)
            if idx < 0:
                break
            window_start = max(0, idx - 72)
            window_end = min(len(text), idx + len(term) + 72)
            snippet = " ".join(text[window_start:window_end].split())
            scan = scan_text(snippet[:220], source="repo_research_snippet")
            item: dict[str, Any] = {"term": term, "snippet": scan.redacted_text}
            if scan.has_findings:
                item["redaction_applied"] = True
                item["secret_finding_kinds"] = sorted({finding.kind for finding in scan.findings})
            snippets.append(item)
            start = idx + len(term)
            if len(snippets) >= limit:
                break
    return snippets


def _is_under_excluded(path: Path, excluded: Sequence[Path]) -> bool:
    for entry in excluded:
        try:
            path.relative_to(entry)
            return True
        except ValueError:
            continue
    return False


def _expand_scoped_paths(repo_root: Path, input_scope: Mapping[str, Any]) -> tuple[list[Path], list[dict[str, Any]], list[str]]:
    raw_allowed = _as_string_list(input_scope.get("paths_allowed"))
    raw_excluded = _as_string_list(input_scope.get("paths_excluded"))
    max_files = int(input_scope.get("max_files") or DEFAULT_MAX_FILES)
    max_files = min(100, max(1, max_files))

    blocked_items: list[dict[str, Any]] = []
    limitations: list[str] = []

    if not raw_allowed:
        return [], blocked_items, ["paths_allowed missing or empty"]

    excluded_paths: list[Path] = []
    for raw in raw_excluded:
        resolved, error = _resolve_scoped_path(repo_root, raw)
        if error:
            blocked_items.append({"path": raw, "reason": error, "status": "excluded_path_ignored"})
            continue
        excluded_paths.append(resolved)

    collected: list[Path] = []
    seen: set[Path] = set()

    for raw in raw_allowed:
        resolved, error = _resolve_scoped_path(repo_root, raw)
        if error:
            blocked_items.append({"path": raw, "reason": error, "status": "blocked"})
            return [], blocked_items, [f"unsafe_path:{raw}"]

        if resolved in seen:
            continue
        if resolved.is_dir():
            for child in sorted((p for p in resolved.rglob("*") if p.is_file()), key=lambda p: str(p)):
                if len(collected) >= max_files:
                    limitations.append("max_files_reached")
                    return collected, blocked_items, limitations
                if not _resolved_within_root(child, repo_root):
                    blocked_items.append({
                        "path": str(child),
                        "reason": "path_escapes_repo_root",
                        "status": "blocked",
                    })
                    continue
                if _private_or_linked_path(child, repo_root):
                    blocked_items.append({"path": str(child.relative_to(repo_root)), "reason": "private_or_linked_path_blocked", "status": "skipped"})
                    continue
                if _is_under_excluded(child, excluded_paths):
                    blocked_items.append({
                        "path": str(child.relative_to(repo_root)),
                        "reason": "excluded_path",
                        "status": "skipped",
                    })
                    continue
                if child not in seen:
                    collected.append(child)
                    seen.add(child)
        else:
            if _is_under_excluded(resolved, excluded_paths):
                blocked_items.append({
                    "path": str(resolved.relative_to(repo_root)),
                    "reason": "excluded_path",
                    "status": "skipped",
                })
                continue
            collected.append(resolved)
            seen.add(resolved)
            if len(collected) >= max_files:
                limitations.append("max_files_reached")
                return collected, blocked_items, limitations

    return collected, blocked_items, limitations


def _evidence_handle(path: Path, locator: str, claim_supported: str, evidence_type: str, confidence: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "locator": locator,
        "claim_supported": claim_supported,
        "evidence_type": evidence_type,
        "confidence": confidence,
    }


def _blocked_packet(
    envelope: Mapping[str, Any] | None,
    repo_root: Path,
    preflight: Mapping[str, Any],
    blocked_items: list[dict[str, Any]] | None = None,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    data = _as_mapping(envelope) or {}
    input_scope = deepcopy(data.get("input_scope"))
    reasons = list(preflight.get("reasons", []))
    blocked_items = list(blocked_items or [])
    limitations = list(limitations or [])
    summary = "Worker blocked before repository reads."
    if blocked_items:
        summary = "Worker blocked before repository reads because the scope was unsafe or invalid."

    return {
        "worker_id": WORKER_ID,
        "worker_type": WORKER_TYPE,
        "task_id": data.get("task_id"),
        "input_scope": input_scope,
        "output_type": OUTPUT_TYPE,
        "content": {"summary": summary, "findings": []},
        "evidence_handles": [],
        "assumptions": [],
        "confidence": "low",
        "limitations": limitations or ["preflight blocked"],
        "blocked_items": blocked_items or reasons,
        "side_effect_request": None,
        "verification_needed": False,
        "memory_context_used": False,
        "candidate_status": "blocked",
        "generated_at": _utc_now(),
        "execution_surface": {
            "mode": data.get("execution_surface"),
            "tools_used": [],
            "agent_id": data.get("worker_id"),
            "model_visible": False,
            "provider_visible": False,
            "max_iterations": 0,
            "context_boundary": "none",
        },
        "security_profile": {
            "name": data.get("security_profile"),
            "network": False,
            "browser": False,
            "shell": False,
            "downloads": False,
            "package_install": False,
        },
        "preflight": {"decision": preflight.get("decision"), "reasons": reasons},
    }


def _candidate_packet(
    envelope: Mapping[str, Any],
    input_scope: Mapping[str, Any],
    findings: list[dict[str, Any]],
    evidence_handles: list[dict[str, Any]],
    blocked_items: list[dict[str, Any]],
    limitations: list[str],
    confidence: str,
    repo_root: Path,
    preflight: Mapping[str, Any],
) -> dict[str, Any]:
    data = _as_mapping(envelope) or {}
    summary = "Read scoped repo files and gathered candidate evidence for the research question."
    if not findings:
        summary = "Read scoped repo files and gathered candidate file evidence from the approved scope."

    return {
        "worker_id": WORKER_ID,
        "worker_type": WORKER_TYPE,
        "task_id": data.get("task_id"),
        "input_scope": deepcopy(dict(input_scope)),
        "output_type": OUTPUT_TYPE,
        "content": {"summary": summary, "findings": findings},
        "evidence_handles": evidence_handles,
        "assumptions": ["Search uses simple lowercase token matching inside approved files."],
        "confidence": confidence,
        "limitations": limitations,
        "blocked_items": blocked_items,
        "side_effect_request": None,
        "verification_needed": True,
        "memory_context_used": False,
        "candidate_status": "candidate",
        "generated_at": _utc_now(),
        "execution_surface": {
            "mode": data.get("execution_surface"),
            "tools_used": ["filesystem_read"],
            "agent_id": data.get("worker_id"),
            "model_visible": False,
            "provider_visible": False,
            "max_iterations": 0,
            "context_boundary": f"paths_allowed within {repo_root}",
        },
        "security_profile": {
            "name": data.get("security_profile"),
            "network": False,
            "browser": False,
            "shell": False,
            "downloads": False,
            "package_install": False,
        },
        "preflight": {"decision": preflight.get("decision"), "reasons": list(preflight.get("reasons", []))},
    }


def _collect_scoped_evidence(repo_root: Path, input_scope: Mapping[str, Any]) -> dict[str, Any]:
    max_bytes = int(input_scope.get("max_bytes_per_file") or DEFAULT_MAX_BYTES_PER_FILE)
    max_bytes = min(DEFAULT_MAX_BYTES_PER_FILE, max(1, max_bytes))
    research_question = str(input_scope.get("research_question") or "")
    terms = _term_candidates(research_question)

    files, blocked_items, limitations = _expand_scoped_paths(repo_root, input_scope)
    if limitations and limitations[0].startswith("unsafe_path:"):
        return {
            "blocked": True,
            "blocked_items": blocked_items,
            "limitations": limitations,
            "findings": [],
            "evidence_handles": [],
            "confidence": "low",
        }
    if "paths_allowed missing or empty" in limitations:
        return {
            "blocked": True,
            "blocked_items": blocked_items,
            "limitations": limitations,
            "findings": [],
            "evidence_handles": [],
            "confidence": "low",
        }

    findings: list[dict[str, Any]] = []
    evidence_handles: list[dict[str, Any]] = []
    seen_content = False
    seen_file = False

    for file_path in files:
        rel_path = str(file_path.relative_to(repo_root)) if _within_root(file_path, repo_root) else str(file_path)
        if _private_or_linked_path(file_path, repo_root) or not _resolved_within_root(file_path, repo_root):
            blocked_items.append({"path": rel_path, "reason": "private_or_linked_path_blocked", "status": "skipped"})
            continue
        try:
            text, info = _read_text_file(file_path, max_bytes)
        except OSError:
            blocked_items.append({"path": rel_path, "reason": "read_unavailable", "status": "skipped"})
            continue
        text_scan = scan_text(text or "", source=rel_path)
        evidence_handles.append(
            _evidence_handle(
                file_path,
                "exists",
                f"Path exists: {rel_path}",
                "file_existence",
                "medium" if info.get("exists") else "low",
            )
        )
        seen_file = seen_file or bool(info.get("exists"))

        if not info.get("exists"):
            findings.append(
                {
                    "path": rel_path,
                    "status": "missing",
                    "locator": "exists check",
                    "matched_terms": [],
                    "snippets": [],
                    "bytes_read": 0,
                    "truncated": False,
                }
            )
            continue

        if info.get("binary_like"):
            blocked_items.append({"path": rel_path, "reason": "binary_or_unreadable", "status": "skipped"})
            limitations.append(f"unreadable:{rel_path}")
            continue

        if text_scan.has_findings:
            blocked_items.append(
                {
                    "path": rel_path,
                    "reason": "secret_like_content_redacted",
                    "status": "redacted",
                    "finding_kinds": sorted({finding.kind for finding in text_scan.findings}),
                }
            )
            limitations.append(f"secret_like_content_redacted:{rel_path}")
            evidence_handles.append(
                _evidence_handle(
                    file_path,
                    "secret redaction",
                    f"Secret-like content was redacted before worker output for {rel_path}",
                    "secret_redaction",
                    "high",
                )
            )

        # Redact before slicing; a truncated read may bisect a credential.
        snippets = [] if info.get("truncated") else _snippets_for_terms(text_scan.redacted_text, terms)
        matched_terms = [snippet["term"] for snippet in snippets]
        if snippets:
            seen_content = True
            evidence_handles.append(
                _evidence_handle(
                    file_path,
                    "content match",
                    f"File content matches research terms in {rel_path}",
                    "file_content",
                    "high" if not info.get("truncated") else "medium",
                )
            )
        else:
            evidence_handles.append(
                _evidence_handle(
                    file_path,
                    "content sampled",
                    f"File content sampled for {rel_path}",
                    "file_content",
                    "medium",
                )
            )

        findings.append(
            {
                "path": rel_path,
                "status": "matched" if snippets else "sampled",
                "locator": "content search",
                "matched_terms": matched_terms,
                "snippets": snippets,
                "bytes_read": info.get("bytes_read", 0),
                "truncated": bool(info.get("truncated")),
            }
        )

        if info.get("truncated"):
            limitations.append(f"truncated:{rel_path}")

    if not files:
        limitations.append("no_readable_files_in_scope")

    if any(item.get("status") == "skipped" for item in blocked_items):
        limitations.append("excluded_paths_skipped")

    if limitations and "max_files_reached" in limitations and seen_content:
        confidence = "medium"
    elif seen_content and not limitations:
        confidence = "high"
    elif seen_content:
        confidence = "medium"
    elif seen_file:
        confidence = "low"
    else:
        confidence = "low"

    return {
        "blocked": False,
        "blocked_items": blocked_items,
        "limitations": limitations,
        "findings": findings,
        "evidence_handles": evidence_handles,
        "confidence": confidence,
    }


def run_repo_research_worker(envelope: Mapping[str, Any], repo_root: str | Path) -> dict[str, Any]:
    preflight = validate_worker_invocation_envelope(envelope)
    repo_root_path = Path(repo_root)

    if preflight.get("decision") != "allow":
        return _blocked_packet(envelope, repo_root_path, preflight)

    data = _as_mapping(envelope)
    if data is None:
        return _blocked_packet(envelope, repo_root_path, preflight, limitations=["input envelope not mapping-like"])

    raw_input_scope = data.get("input_scope")
    input_scope = _as_mapping(raw_input_scope)
    if input_scope is None and isinstance(raw_input_scope, list) and raw_input_scope and isinstance(raw_input_scope[0], Mapping):
        input_scope = _as_mapping(raw_input_scope[0])
    if input_scope is None:
        return _blocked_packet(envelope, repo_root_path, preflight, limitations=["missing input_scope"])

    if not repo_root_path.exists() or not repo_root_path.is_dir():
        return _blocked_packet(envelope, repo_root_path, preflight, limitations=["repo_root unavailable"])

    scoped = _collect_scoped_evidence(repo_root_path, input_scope)
    if scoped.get("blocked"):
        return _blocked_packet(
            envelope,
            repo_root_path,
            preflight,
            blocked_items=scoped.get("blocked_items", []),
            limitations=scoped.get("limitations", []),
        )

    return _candidate_packet(
        envelope=envelope,
        input_scope=input_scope,
        findings=scoped.get("findings", []),
        evidence_handles=scoped.get("evidence_handles", []),
        blocked_items=scoped.get("blocked_items", []),
        limitations=scoped.get("limitations", []),
        confidence=scoped.get("confidence", "low"),
        repo_root=repo_root_path,
        preflight=preflight,
    )


__all__ = ["run_repo_research_worker"]
