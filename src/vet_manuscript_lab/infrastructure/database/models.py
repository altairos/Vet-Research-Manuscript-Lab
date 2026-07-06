"""Foundation persistence models.

Payload content remains in the artifact store. These tables keep identities,
version metadata, approvals, locks, workflow runs, and append-only audit events.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vet_manuscript_lab.infrastructure.database.base import Base


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    study_type: Mapped[str] = mapped_column(String(100))
    species_scope: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active")
    owner_id: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    runs: Mapped[list[WorkflowRunRecord]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class WorkflowRunRecord(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    thread_id: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(32))
    current_stage: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    project: Mapped[ProjectRecord] = relationship(back_populates="runs")


class ArtifactRecord(Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("project_id", "artifact_type", "logical_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(100))
    logical_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    versions: Mapped[list[ArtifactVersionRecord]] = relationship(
        back_populates="artifact", cascade="all, delete-orphan"
    )


class ArtifactVersionRecord(Base):
    __tablename__ = "artifact_versions"
    __table_args__ = (
        UniqueConstraint("artifact_id", "version"),
        UniqueConstraint("artifact_id", "content_hash"),
        Index("ix_artifact_versions_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("artifacts.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32))
    content_hash: Mapped[str] = mapped_column(String(80))
    uri: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(100))
    created_by_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id"), nullable=True
    )
    source_version_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_formal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    artifact: Mapped[ArtifactRecord] = relationship(back_populates="versions")


class ApprovalRecord(Base):
    __tablename__ = "approvals"
    __table_args__ = (UniqueConstraint("gate", "subject_version_id", "reviewer_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    gate: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[str] = mapped_column(String(36))
    subject_version_id: Mapped[str] = mapped_column(String(36))
    subject_hash: Mapped[str] = mapped_column(String(80))
    decision: Mapped[str] = mapped_column(String(32))
    reviewer_id: Mapped[str] = mapped_column(String(100))
    reviewer_role: Mapped[str] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LockRecord(Base):
    __tablename__ = "locks"
    __table_args__ = (UniqueConstraint("lock_type", "subject_version_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    lock_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[str] = mapped_column(String(36))
    subject_version_id: Mapped[str] = mapped_column(String(36))
    subject_hash: Mapped[str] = mapped_column(String(80))
    approval_id: Mapped[str] = mapped_column(ForeignKey("approvals.id"))
    locked_by: Mapped[str] = mapped_column(String(100))
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    workflow_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id"), nullable=True, index=True
    )
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(32))
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Literature and evidence aggregate (migration 0002)
# ---------------------------------------------------------------------------


class LiteratureRecord(Base):
    """Local bibliographic identity for a reference.

    Zotero is a synchronisation source, not the source of truth; the local
    record owns DOI/PMID uniqueness within a project.
    """

    __tablename__ = "literature_records"
    __table_args__ = (
        UniqueConstraint("project_id", "doi", name="uq_literature_records_project_doi"),
        UniqueConstraint(
            "project_id", "pmid", name="uq_literature_records_project_pmid"
        ),
        Index("ix_literature_records_doi", "doi"),
        Index("ix_literature_records_pmid", "pmid"),
        Index("ix_literature_records_zotero_item_key", "zotero_item_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(600))
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pmid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    zotero_item_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    zotero_library_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bibtex_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    creators: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    journal: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sync_status: Mapped[str] = mapped_column(String(32), default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    attachments: Mapped[list[AttachmentVersionRecord]] = relationship(
        back_populates="literature_record", cascade="all, delete-orphan"
    )


class AttachmentVersionRecord(Base):
    """Immutable version of a source file attached to a literature record."""

    __tablename__ = "attachment_versions"
    __table_args__ = (
        UniqueConstraint("literature_record_id", "version"),
        UniqueConstraint("literature_record_id", "content_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    literature_record_id: Mapped[str] = mapped_column(
        ForeignKey("literature_records.id"), index=True
    )
    attachment_key: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(80))
    uri: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(100))
    created_by_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    literature_record: Mapped[LiteratureRecord] = relationship(
        back_populates="attachments"
    )


class SourceSpanRecord(Base):
    """Exact source location within an attachment (page, section, offsets)."""

    __tablename__ = "source_spans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    literature_record_id: Mapped[str] = mapped_column(
        ForeignKey("literature_records.id"), index=True
    )
    attachment_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("attachment_versions.id"), nullable=True
    )
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote_hash: Mapped[str] = mapped_column(String(80))
    created_by_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvidenceItemRecord(Base):
    """Validatable extracted evidence linked to at least one source span.

    An EvidenceItem represents what a source *reports*; a Claim represents
    what the manuscript *asserts*. They must remain separate.
    """

    __tablename__ = "evidence_items"
    __table_args__ = (
        Index("ix_evidence_items_literature_record_id", "literature_record_id"),
        Index("ix_evidence_items_concept", "concept"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    concept: Mapped[str] = mapped_column(String(300))
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    units: Mapped[str | None] = mapped_column(String(128), nullable=True)
    population: Mapped[str | None] = mapped_column(String(300), nullable=True)
    certainty: Mapped[str] = mapped_column(String(64), default="unspecified")
    extraction_status: Mapped[str] = mapped_column(String(32), default="draft")
    source_span_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    literature_record_id: Mapped[str] = mapped_column(
        ForeignKey("literature_records.id"), nullable=False
    )
    created_by_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)


class ScreeningDecisionRecord(Base):
    """Inclusion / exclusion decision for a literature record at a stage."""

    __tablename__ = "screening_decisions"
    __table_args__ = (
        UniqueConstraint(
            "literature_record_id", "stage", name="uq_screening_record_stage"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    literature_record_id: Mapped[str] = mapped_column(
        ForeignKey("literature_records.id"), index=True
    )
    stage: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[str] = mapped_column(String(100))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProvenanceLinkRecord(Base):
    """Typed directed derivation edge between versioned domain objects."""

    __tablename__ = "provenance_links"
    __table_args__ = (
        UniqueConstraint(
            "source_version_id",
            "target_version_id",
            "relation",
            name="uq_provenance_link_edge",
        ),
        Index("ix_provenance_links_target_version_id", "target_version_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    source_version_id: Mapped[str] = mapped_column(String(36))
    source_type: Mapped[str] = mapped_column(String(64))
    target_version_id: Mapped[str] = mapped_column(String(36))
    target_type: Mapped[str] = mapped_column(String(64))
    relation: Mapped[str] = mapped_column(String(64))
    created_by_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
