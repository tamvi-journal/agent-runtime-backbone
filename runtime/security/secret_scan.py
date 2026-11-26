from __future__ import annotations

from dataclasses import asdict, dataclass

from runtime.security.secret_patterns import SECRET_PATTERNS

SECRET_SCAN_SCOPE_NOTE = (
    "Pattern-based secret scan checks known key formats only; a pass is not a guarantee "
    "that no secret exists and does not replace secret managers or pre-commit scanners."
)


@dataclass(frozen=True)
class SecretFinding:
    kind: str
    source: str
    line: int
    column: int
    start: int
    end: int
    redaction: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SecretScanResult:
    source: str
    findings: tuple[SecretFinding, ...]
    redacted_text: str
    scope_note: str = SECRET_SCAN_SCOPE_NOTE

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "has_findings": self.has_findings,
            "findings": [finding.to_dict() for finding in self.findings],
            "finding_count": len(self.findings),
            "scope_note": self.scope_note,
            "redacted_text": self.redacted_text,
        }


def _line_column(text: str, index: int) -> tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    line_start = text.rfind("\n", 0, index)
    column = index + 1 if line_start < 0 else index - line_start
    return line, column


def scan_text(text: str | None, *, source: str = "") -> SecretScanResult:
    """Run a pattern-limited secret scan.

    This catches known token/key formats only. A clean result is not a guarantee
    that no secret exists, and redaction cannot un-leak values already written to
    logs, disk, or git history.
    """

    value = text or ""
    findings: list[SecretFinding] = []
    redacted = value

    for kind, pattern, redaction in SECRET_PATTERNS:
        for match in pattern.finditer(value):
            line, column = _line_column(value, match.start())
            findings.append(
                SecretFinding(
                    kind=kind,
                    source=source,
                    line=line,
                    column=column,
                    start=match.start(),
                    end=match.end(),
                    redaction=redaction,
                )
            )
        redacted = pattern.sub(redaction, redacted)

    findings.sort(key=lambda item: (item.start, item.end, item.kind))
    return SecretScanResult(source=source, findings=tuple(findings), redacted_text=redacted)


def redact_text(text: str | None, *, source: str = "") -> str:
    return scan_text(text, source=source).redacted_text


__all__ = ["SECRET_SCAN_SCOPE_NOTE", "SecretFinding", "SecretScanResult", "redact_text", "scan_text"]
