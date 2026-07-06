from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vet_manuscript_lab.infrastructure.artifacts import (
    ArtifactIntegrityError,
    LocalArtifactStore,
)


class LocalArtifactStoreTests(unittest.TestCase):
    def test_put_is_content_addressed_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = LocalArtifactStore(Path(temporary))
            first = store.put(b"immutable payload")
            second = store.put(b"immutable payload")
            self.assertEqual(first, second)
            self.assertEqual(store.get(first.content_hash), b"immutable payload")
            self.assertTrue(store.verify(first.content_hash))

    def test_corruption_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = LocalArtifactStore(Path(temporary))
            stored = store.put(b"original")
            store.path_for(stored.content_hash).write_bytes(b"tampered")
            with self.assertRaises(ArtifactIntegrityError):
                store.get(stored.content_hash)
            self.assertFalse(store.verify(stored.content_hash))

    def test_invalid_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = LocalArtifactStore(Path(temporary))
            with self.assertRaises(ValueError):
                store.path_for("md5:not-allowed")


if __name__ == "__main__":
    unittest.main()
