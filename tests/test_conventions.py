from __future__ import annotations

import re
import unittest
import uuid

from vet_manuscript_lab.domain.conventions import new_id, sha256_bytes, utc_now


class ConventionTests(unittest.TestCase):
    def test_new_id_is_uuid(self) -> None:
        identifier = new_id()
        self.assertEqual(str(uuid.UUID(identifier)), identifier)

    def test_hash_is_algorithm_qualified_and_stable(self) -> None:
        digest = sha256_bytes(b"veterinary")
        self.assertEqual(
            digest,
            "sha256:f4bac58953834ab574727812c35a3c9305d08602946617a679d81ab6c30ea668",
        )

    def test_utc_timestamp_is_canonical(self) -> None:
        self.assertRegex(utc_now(), re.compile(r"^\d{4}-\d{2}-\d{2}T.*Z$"))


if __name__ == "__main__":
    unittest.main()
