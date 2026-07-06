from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import func, select

from vet_manuscript_lab.infrastructure.artifacts import LocalArtifactStore
from vet_manuscript_lab.infrastructure.database import create_database
from vet_manuscript_lab.infrastructure.database.models import AuditEventRecord
from vet_manuscript_lab.infrastructure.database.repository import (
    FoundationRepository,
    ProjectInput,
)


class DatabaseTests(unittest.TestCase):
    def test_project_run_and_artifact_versions_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = create_database(f"sqlite:///{root / 'domain.sqlite'}")
            database.create_schema()
            repository = FoundationRepository(database.sessions)
            store = LocalArtifactStore(root / "artifacts")

            project = repository.create_project(
                ProjectInput(
                    title="Synthetic project",
                    study_type="retrospective_observational_clinical_study",
                    species_scope=["canine"],
                    owner_id="owner-1",
                )
            )
            run = repository.create_run(project.id, "thread-1")
            first_payload = store.put(b'{"version":1}')
            first = repository.create_artifact_version(
                project_id=project.id,
                artifact_type="protocol",
                logical_name="primary_protocol",
                content_hash=first_payload.content_hash,
                uri=first_payload.uri,
                media_type="application/json",
                created_by_run_id=run.id,
            )
            duplicate = repository.create_artifact_version(
                project_id=project.id,
                artifact_type="protocol",
                logical_name="primary_protocol",
                content_hash=first_payload.content_hash,
                uri=first_payload.uri,
                media_type="application/json",
                created_by_run_id=run.id,
            )
            second_payload = store.put(b'{"version":2}')
            second = repository.create_artifact_version(
                project_id=project.id,
                artifact_type="protocol",
                logical_name="primary_protocol",
                content_hash=second_payload.content_hash,
                uri=second_payload.uri,
                media_type="application/json",
                created_by_run_id=run.id,
                source_version_ids=[first.id],
            )

            self.assertEqual(first.id, duplicate.id)
            self.assertEqual(first.version, 1)
            self.assertEqual(second.version, 2)
            self.assertEqual(repository.list_projects()[0].id, project.id)
            with database.sessions() as session:
                audit_count = session.scalar(select(func.count(AuditEventRecord.id)))
            self.assertEqual(audit_count, 4)
            database.engine.dispose()


if __name__ == "__main__":
    unittest.main()
