from __future__ import annotations

from pathlib import PurePosixPath
import re


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "openai_api_key",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
        "[REDACTED_OPENAI_API_KEY]",
    ),
    (
        "trustmrr_api_key",
        re.compile(r"\btmrr_[A-Za-z0-9_-]{8,}\b"),
        "[REDACTED_TRUSTMRR_API_KEY]",
    ),
    (
        "github_token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    (
        "aws_access_key_id",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_ACCESS_KEY_ID]",
    ),
    (
        "bearer_token",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{24,}\b", re.IGNORECASE),
        "Bearer [REDACTED_TOKEN]",
    ),
    (
        "database_dsn",
        re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s'\"<>]+", re.IGNORECASE),
        "[REDACTED_DATABASE_DSN]",
    ),
    (
        "private_key_block",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PRIVATE )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH |DSA |PRIVATE )?PRIVATE KEY-----",
            re.DOTALL,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
)

SECRET_PATH_BASENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "credentials.json",
    "token.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
}

SECRET_PATH_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
)


def is_secret_path(path: str) -> bool:
    normalized = str(path).replace("\\", "/").strip()
    if not normalized:
        return False
    name = PurePosixPath(normalized).name.lower()
    if name in SECRET_PATH_BASENAMES:
        return True
    if name.startswith(".env."):
        return True
    return any(name.endswith(suffix) for suffix in SECRET_PATH_SUFFIXES)


__all__ = ["SECRET_PATTERNS", "is_secret_path"]
