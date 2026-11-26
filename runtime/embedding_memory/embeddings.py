from __future__ import annotations

import hashlib
import math
from typing import Iterable

DEFAULT_EMBEDDING_MODEL = "local-agent-local-hash-embedding-v0.1"
DEFAULT_DIMENSIONS = 64


def _tokens(text: str) -> list[str]:
    return [token for token in text.lower().replace("\n", " ").split(" ") if token]


def embed_text(
    text: str,
    *,
    dimensions: int = DEFAULT_DIMENSIONS,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> list[float]:
    """Return a deterministic local embedding placeholder.

    This is intentionally not a production semantic embedding model.
    It gives ExampleAgent a testable vector-shaped contract without network calls,
    API keys, or hidden external dependency.

    Replace this adapter later with OpenAI, local sentence-transformer,
    Qwen embedding, or another provider while preserving the same contract.
    """
    if dimensions <= 0:
        raise ValueError("dimensions must be positive")

    vector = [0.0 for _ in range(dimensions)]
    namespace = model_name.encode("utf-8")

    for token in _tokens(text):
        digest = hashlib.sha256(namespace + b":" + token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 1.0 + (digest[5] / 255.0)
        vector[index] += sign * weight

    return normalize(vector)


def normalize(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        return values
    return [value / norm for value in values]


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = [float(value) for value in left]
    right_values = [float(value) for value in right]
    if len(left_values) != len(right_values):
        raise ValueError("vectors must have the same dimensions")
    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(left_values, right_values)) / (left_norm * right_norm)
