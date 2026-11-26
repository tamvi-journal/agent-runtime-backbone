from __future__ import annotations

from runtime.security.secret_scan import scan_text


def scan_diff_text(diff_text: str, *, source: str = "git_diff") -> dict[str, object]:
    scan = scan_text(diff_text, source=source)
    return {
        "decision": "block" if scan.has_findings else "allow",
        "reason": "secret_like_content_detected" if scan.has_findings else "no_secret_like_content_detected",
        "finding_count": len(scan.findings),
        "findings": [finding.to_dict() for finding in scan.findings],
        "scope_note": scan.scope_note,
        "redacted_diff": scan.redacted_text,
    }


__all__ = ["scan_diff_text"]
