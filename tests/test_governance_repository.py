from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select

from vet_manuscript_lab.infrastructure.database import create_database
from vet_manuscript_lab.infrastructure.database.governance import GovernanceRepository
from vet_manuscript_lab.infrastructure.database.models import ApprovalRecord, LockRecord
from vet_manuscript_lab.infrastructure.database.repository import (
    FoundationRepository,
    ProjectInput,
)
from vet_manuscript_lab.workflow.state import new_workflow_state


class GovernanceRepositoryTests(unittest.TestCase):
    def test_approval_and_lock_sync_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = create_database(
                f"sqlite:///{Path(temporary) / 'governance.sqlite'}"
            )
            database.create_schema()
            foundation = FoundationRepository(database.sessions)
            governance = GovernanceRepository(database.sessions)
            project = foundation.create_project(
                ProjectInput(
                    title="Governance test",
                    study_type="retrospective_observational_clinical_study",
                    species_scope=["canine"],
                    owner_id="owner-1",
                )
            )
            run = foundation.create_run(project.id, "thread-governance")
            state = new_workflow_state(
                project_id=project.id,
                workflow_run_id=run.id,
                thread_id=run.thread_id,
                now="2026-07-06T00:00:00Z",
            )
            state["current_stage"] = "protocol_lock"
            state["run_status"] = "complete"
            state["approvals"] = {
                "protocol": {
                    "approval_id": "approval-1",
                    "gate": "protocol",
                    "subject_id": "protocol-1",
                    "subject_version_id": "protocol-v1",
                    "subject_hash": "sha256:abc",
                    "decision": "approved",
                    "reviewer_id": "investigator-1",
                    "reviewer_role": "investigator",
                    "decided_at": "2026-07-06T00:00:00Z",
                }
            }
            state["locks"] = {
                "protocol": {
                    "lock_id": "lock-1",
                    "lock_type": "protocol",
                    "subject_id": "protocol-1",
                    "subject_version_id": "protocol-v1",
                    "subject_hash": "sha256:abc",
                    "approval_id": "approval-1",
                    "locked_by": "investigator-1",
                    "locked_at": "2026-07-06T00:00:00Z",
                }
            }

            governance.sync_state(state)
            governance.sync_state(state)

            with database.sessions() as session:
                approval_count = session.scalar(select(func.count(ApprovalRecord.id)))
                lock_count = session.scalar(select(func.count(LockRecord.id)))
            self.assertEqual(approval_count, 1)
            self.assertEqual(lock_count, 1)
            database.engine.dispose()


if __name__ == "__main__":
    unittest.main()
