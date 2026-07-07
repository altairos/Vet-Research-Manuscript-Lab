"""Transactional Foundation repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from vet_manuscript_lab.domain.conventions import new_id
from vet_manuscript_lab.infrastructure.database.base import Base
from vet_manuscript_lab.infrastructure.database.models import (
    ApprovalRecord,
    ArtifactRecord,
    ArtifactVersionRecord,
    AuditEventRecord,
    LockRecord,
    ProjectRecord,
    WorkflowRunRecord,
)


def now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ProjectInput:
    title: str
    study_type: str
    species_scope: list[str]
    owner_id: str


class FoundationRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def create_project(self, data: ProjectInput) -> ProjectRecord:
        if not data.title.strip() or not data.owner_id.strip():
            raise ValueError("Project title and owner are required")
        timestamp = now_utc()
        project = ProjectRecord(
            id=new_id(),
            title=data.title.strip(),
            study_type=data.study_type,
            species_scope=data.species_scope,
            status="active",
            owner_id=data.owner_id.strip(),
            created_at=timestamp,
            updated_at=timestamp,
        )
        with self.sessions.begin() as session:
            session.add(project)
            session.flush()
            self._audit(
                session,
                project_id=project.id,
                actor_type="human",
                actor_id=project.owner_id,
                action="project.created",
                target_type="project",
                target_id=project.id,
                outcome="success",
            )
        return project

    def list_projects(self) -> list[ProjectRecord]:
        with self.sessions() as session:
            return list(
                session.scalars(
                    select(ProjectRecord).order_by(ProjectRecord.created_at)
                )
            )

    def rename_project(self, project_id: str, new_title: str) -> ProjectRecord:
        """Update the project title, raising on empty/duplicate conditions."""

        title = new_title.strip()
        if not title:
            raise ValueError("Project title must not be empty")
        with self.sessions.begin() as session:
            project = session.scalar(
                select(ProjectRecord).where(ProjectRecord.id == project_id)
            )
            if project is None:
                raise ValueError(f"Project {project_id} not found")
            project.title = title
            project.updated_at = now_utc()
            session.flush()
            self._audit(
                session,
                project_id=project.id,
                actor_type="human",
                actor_id=project.owner_id,
                action="project.renamed",
                target_type="project",
                target_id=project.id,
                outcome="success",
            )
            return project

    def delete_project(self, project_id: str) -> None:
        """Delete a project and all its dependent records.

        Iterates every table that has a ``project_id`` foreign key and
        removes matching rows, then deletes the project row itself.
        For SQLite the PRAGMA is used to relax FK ordering; on other
        backends the reversed topological order suffices.
        """

        with self.sessions.begin() as session:
            bind = session.bind
            dialect = bind.dialect.name if bind is not None else "sqlite"
            if dialect == "sqlite":
                session.execute(text("PRAGMA foreign_keys = OFF"))
            for table in reversed(Base.metadata.sorted_tables):
                if "project_id" in table.columns:
                    session.execute(
                        table.delete().where(table.c.project_id == project_id)
                    )
            session.execute(
                ProjectRecord.__table__.delete().where(
                    ProjectRecord.__table__.c.id == project_id
                )
            )
            if dialect == "sqlite":
                session.execute(text("PRAGMA foreign_keys = ON"))

    def create_run(self, project_id: str, thread_id: str) -> WorkflowRunRecord:
        timestamp = now_utc()
        run = WorkflowRunRecord(
            id=new_id(),
            project_id=project_id,
            thread_id=thread_id,
            status="pending",
            current_stage="project_init",
            created_at=timestamp,
            updated_at=timestamp,
        )
        with self.sessions.begin() as session:
            session.add(run)
            session.flush()
            self._audit(
                session,
                project_id=project_id,
                workflow_run_id=run.id,
                actor_type="human",
                actor_id="system-user",
                action="workflow_run.created",
                target_type="workflow_run",
                target_id=run.id,
                outcome="success",
            )
        return run

    def create_artifact_version(
        self,
        *,
        project_id: str,
        artifact_type: str,
        logical_name: str,
        content_hash: str,
        uri: str,
        media_type: str,
        created_by_run_id: str | None,
        source_version_ids: list[str] | None = None,
    ) -> ArtifactVersionRecord:
        with self.sessions.begin() as session:
            artifact = session.scalar(
                select(ArtifactRecord).where(
                    ArtifactRecord.project_id == project_id,
                    ArtifactRecord.artifact_type == artifact_type,
                    ArtifactRecord.logical_name == logical_name,
                )
            )
            if artifact is None:
                artifact = ArtifactRecord(
                    id=new_id(),
                    project_id=project_id,
                    artifact_type=artifact_type,
                    logical_name=logical_name,
                    created_at=now_utc(),
                )
                session.add(artifact)
                session.flush()

            existing = session.scalar(
                select(ArtifactVersionRecord).where(
                    ArtifactVersionRecord.artifact_id == artifact.id,
                    ArtifactVersionRecord.content_hash == content_hash,
                )
            )
            if existing is not None:
                return existing

            latest = session.scalar(
                select(ArtifactVersionRecord.version)
                .where(ArtifactVersionRecord.artifact_id == artifact.id)
                .order_by(ArtifactVersionRecord.version.desc())
                .limit(1)
            )
            version = ArtifactVersionRecord(
                id=new_id(),
                artifact_id=artifact.id,
                version=(latest or 0) + 1,
                status="draft",
                content_hash=content_hash,
                uri=uri,
                media_type=media_type,
                created_by_run_id=created_by_run_id,
                source_version_ids=source_version_ids or [],
                is_formal=False,
                created_at=now_utc(),
            )
            session.add(version)
            self._audit(
                session,
                project_id=project_id,
                workflow_run_id=created_by_run_id,
                actor_type="agent",
                actor_id="foundation-mock-agent",
                action="artifact_version.created",
                target_type="artifact_version",
                target_id=version.id,
                outcome="success",
                metadata={"content_hash": content_hash},
            )
        return version

    @staticmethod
    def _audit(
        session: Session,
        *,
        project_id: str,
        actor_type: str,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
        outcome: str,
        workflow_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        session.add(
            AuditEventRecord(
                id=new_id(),
                project_id=project_id,
                workflow_run_id=workflow_run_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                outcome=outcome,
                event_metadata=metadata or {},
                occurred_at=now_utc(),
            )
        )


__all__ = [
    "ApprovalRecord",
    "ArtifactRecord",
    "ArtifactVersionRecord",
    "AuditEventRecord",
    "FoundationRepository",
    "LockRecord",
    "ProjectInput",
    "ProjectRecord",
    "WorkflowRunRecord",
]
