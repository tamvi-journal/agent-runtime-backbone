from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from runtime.security.secret_patterns import is_secret_path
from runtime.security.secret_scan import SECRET_SCAN_SCOPE_NOTE, scan_text


def guard_worker_input_scope(input_scope: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(input_scope, Mapping):
        return {"decision": "block", "reasons": ["invalid_input_scope"], "secret_paths": []}

    secret_paths: list[str] = []
    values = input_scope.get("paths_allowed") or []
    if isinstance(values, list):
        for value in values:
            if isinstance(value, str) and is_secret_path(value):
                secret_paths.append(value)

    if secret_paths:
        return {
            "decision": "block",
            "reasons": ["secret_path_in_worker_scope"],
            "secret_paths": secret_paths,
        }
    return {"decision": "allow", "reasons": [], "secret_paths": []}


def redact_worker_payload(value: Any, *, source: str = "worker_payload") -> Any:
    if isinstance(value, str):
        return scan_text(value, source=source).redacted_text
    if isinstance(value, list):
        return [redact_worker_payload(item, source=source) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_worker_payload(item, source=source) for item in value)
    if isinstance(value, Mapping):
        return {key: redact_worker_payload(item, source=f"{source}.{key}") for key, item in value.items()}
    return deepcopy(value)


def scan_worker_payload(value: Any, *, source: str = "worker_payload") -> dict[str, Any]:
    findings: list[dict[str, object]] = []

    def visit(item: Any, path: str) -> None:
        if isinstance(item, str):
            scan = scan_text(item, source=path)
            findings.extend(finding.to_dict() for finding in scan.findings)
        elif isinstance(item, Mapping):
            for key, nested in item.items():
                visit(nested, f"{path}.{key}")
        elif isinstance(item, (list, tuple)):
            for index, nested in enumerate(item):
                visit(nested, f"{path}[{index}]")

    visit(value, source)
    return {
        "decision": "block" if findings else "allow",
        "findings": findings,
        "finding_count": len(findings),
        "scope_note": SECRET_SCAN_SCOPE_NOTE,
    }


__all__ = ["guard_worker_input_scope", "redact_worker_payload", "scan_worker_payload"]
