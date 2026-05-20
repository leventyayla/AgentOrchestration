"""Artifact ingestion helpers and storage."""

import hashlib
import os
from typing import Dict, Optional


DEFAULT_MAX_ARTIFACT_BODY_BYTES = 1024 * 1024


class ArtifactTooLarge(ValueError):
    """Raised when an artifact upload exceeds the configured body limit."""

    def __init__(self, size: int, limit: int):
        self.size = size
        self.limit = limit
        message = f"Artifact body is {size} bytes; limit is {limit} bytes"
        super().__init__(message)


class ArtifactStore:
    """Small in-memory artifact store used by the API service layer.

    The max-size guard lives here so every caller gets the same fail-closed
    behavior before lookup, replacement, or metadata mutation occurs.
    """

    def __init__(self):
        self._artifacts: Dict[str, Dict[str, object]] = {}

    def upload(
        self,
        artifact_id: str,
        body: bytes,
        max_body_size: Optional[int] = None,
    ) -> Dict[str, object]:
        limit = resolve_max_body_size(max_body_size)
        size = len(body)
        if size > limit:
            raise ArtifactTooLarge(size=size, limit=limit)

        digest = hashlib.sha256(body).hexdigest()
        record: Dict[str, object] = {
            "artifact_id": artifact_id,
            "size": size,
            "sha256": digest,
            "body": body,
        }
        self._artifacts[artifact_id] = record
        return self.metadata(artifact_id) or {}

    def metadata(self, artifact_id: str) -> Optional[Dict[str, object]]:
        record = self._artifacts.get(artifact_id)
        if record is None:
            return None
        return {
            "artifact_id": record["artifact_id"],
            "size": record["size"],
            "sha256": record["sha256"],
        }

    def clear(self) -> None:
        self._artifacts.clear()


def resolve_max_body_size(max_body_size: Optional[int] = None) -> int:
    if max_body_size is not None:
        return max_body_size

    raw_limit = os.getenv("AO_ARTIFACT_MAX_BODY_BYTES")
    if not raw_limit:
        return DEFAULT_MAX_ARTIFACT_BODY_BYTES

    try:
        limit = int(raw_limit)
    except ValueError:
        return DEFAULT_MAX_ARTIFACT_BODY_BYTES

    return limit if limit > 0 else DEFAULT_MAX_ARTIFACT_BODY_BYTES


artifact_store = ArtifactStore()
