"""Content-addressed local artifact storage with atomic writes."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from vet_manuscript_lab.domain.conventions import sha256_bytes


class ArtifactIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StoredPayload:
    content_hash: str
    uri: str
    size_bytes: int


class LocalArtifactStore:
    """Store immutable bytes under a path derived from their SHA-256 digest."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, payload: bytes) -> StoredPayload:
        content_hash = sha256_bytes(payload)
        digest = content_hash.partition(":")[2]
        target = self.root / digest[:2] / digest[2:4] / digest
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            existing = target.read_bytes()
            if existing != payload:
                raise ArtifactIntegrityError(
                    "Content-address collision or corrupted existing payload"
                )
            return self._stored(target, content_hash, len(payload))

        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent, prefix=f".{digest}.", suffix=".tmp"
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

        return self._stored(target, content_hash, len(payload))

    def get(self, content_hash: str) -> bytes:
        path = self.path_for(content_hash)
        payload = path.read_bytes()
        if sha256_bytes(payload) != content_hash:
            raise ArtifactIntegrityError(f"Artifact hash mismatch: {content_hash}")
        return payload

    def path_for(self, content_hash: str) -> Path:
        algorithm, separator, digest = content_hash.partition(":")
        if algorithm != "sha256" or separator != ":" or len(digest) != 64:
            raise ValueError("Expected an algorithm-qualified SHA-256 hash")
        if any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("SHA-256 digest must be lowercase hexadecimal")
        return self.root / digest[:2] / digest[2:4] / digest

    def verify(self, content_hash: str) -> bool:
        try:
            self.get(content_hash)
        except (FileNotFoundError, ArtifactIntegrityError, ValueError):
            return False
        return True

    @staticmethod
    def _stored(path: Path, content_hash: str, size: int) -> StoredPayload:
        return StoredPayload(
            content_hash=content_hash,
            uri=path.as_uri(),
            size_bytes=size,
        )

