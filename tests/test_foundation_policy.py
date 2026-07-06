from __future__ import annotations

import unittest

from vet_manuscript_lab.domain.policies import (
    ApprovalSnapshot,
    LockSnapshot,
    PolicyViolation,
    require_approved_subject,
    require_unlocked_subject,
)


class FoundationPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.approval = ApprovalSnapshot(
            gate="protocol",
            subject_version_id="version-1",
            subject_hash="sha256:abc",
            decision="approved",
            reviewer_id="human-1",
            reviewer_role="investigator",
        )

    def test_exact_authorized_approval_passes(self) -> None:
        result = require_approved_subject(
            self.approval,
            gate="protocol",
            subject_version_id="version-1",
            subject_hash="sha256:abc",
            allowed_roles=frozenset({"investigator"}),
        )
        self.assertEqual(result, self.approval)

    def test_stale_hash_is_rejected(self) -> None:
        with self.assertRaisesRegex(PolicyViolation, "hash"):
            require_approved_subject(
                self.approval,
                gate="protocol",
                subject_version_id="version-1",
                subject_hash="sha256:different",
                allowed_roles=frozenset({"investigator"}),
            )

    def test_unauthorized_role_is_rejected(self) -> None:
        with self.assertRaisesRegex(PolicyViolation, "role"):
            require_approved_subject(
                self.approval,
                gate="protocol",
                subject_version_id="version-1",
                subject_hash="sha256:abc",
                allowed_roles=frozenset({"statistician"}),
            )

    def test_locked_version_cannot_be_changed(self) -> None:
        locks = [
            LockSnapshot(
                lock_type="protocol",
                subject_version_id="version-1",
                subject_hash="sha256:abc",
            )
        ]
        with self.assertRaisesRegex(PolicyViolation, "immutable"):
            require_unlocked_subject(locks, subject_version_id="version-1")


if __name__ == "__main__":
    unittest.main()
