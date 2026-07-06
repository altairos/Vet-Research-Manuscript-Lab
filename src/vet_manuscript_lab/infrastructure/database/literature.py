"""Transactional repository for the literature and evidence aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from vet_manuscript_lab.domain.conventions import new_id
from vet_manuscript_lab.domain.policies import (
    EvidenceCandidate,
    require_non_duplicate_reference,
    require_source_span_for_evidence,
)
from vet_manuscript_lab.infrastructure.database.models import (
    AttachmentVersionRecord,
    AuditEventRecord,
    EvidenceItemRecord,
    LiteratureRecord,
    ProvenanceLinkRecord,
    ScreeningDecisionRecord,
    SourceSpanRecord,
)
from vet_manuscript_lab.infrastructure.database.repository import now_utc


@dataclass(frozen=True, slots=True)
class LiteratureInput:
    title: str
    doi: str | None = None
    pmid: str | None = None
    zotero_item_key: str | None = None
    zotero_library_id: str | None = None
    bibtex_key: str | None = None
    creators: list[dict[str, Any]] | None = None
    publication_year: int | None = None
    journal: str | None = None
    metadata_json: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class AttachmentInput:
    literature_record_id: str
    attachment_key: str
    content_hash: str
    uri: str
    media_type: str
    created_by_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class SourceSpanInput:
    project_id: str
    literature_record_id: str
    quote_hash: str
    attachment_version_id: str | None = None
    page: int | None = None
    section_label: str | None = None
    chunk_index: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    created_by_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    project_id: str
    concept: str
    literature_record_id: str
    source_span_ids: list[str]
    value: str | None = None
    units: str | None = None
    population: str | None = None
    certainty: str = "unspecified"
    extraction_status: str = "draft"
    requires_human_review: bool = False
    created_by_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class ScreeningInput:
    project_id: str
    literature_record_id: str
    stage: str
    decision: str
    reviewer_id: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ProvenanceLinkInput:
    project_id: str
    source_version_id: str
    source_type: str
    target_version_id: str
    target_type: str
    relation: str
    created_by_run_id: str | None = None


class LiteratureRepository:
    """CRUD + dedup for literature records, attachments, spans, and evidence."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    # -- literature records ------------------------------------------------

    def create_literature_record(
        self, *, project_id: str, data: LiteratureInput
    ) -> LiteratureRecord:
        if not data.title.strip():
            raise ValueError("Literature title is required")

        with self.sessions.begin() as session:
            existing_dois = frozenset(
                doi
                for doi in session.scalars(
                    select(LiteratureRecord.doi).where(
                        LiteratureRecord.project_id == project_id,
                        LiteratureRecord.doi.is_not(None),
                    )
                )
                if doi is not None
            )
            existing_pmids = frozenset(
                pmid
                for pmid in session.scalars(
                    select(LiteratureRecord.pmid).where(
                        LiteratureRecord.project_id == project_id,
                        LiteratureRecord.pmid.is_not(None),
                    )
                )
                if pmid is not None
            )
            require_non_duplicate_reference(
                doi=data.doi,
                pmid=data.pmid,
                existing_dois=existing_dois,
                existing_pmids=existing_pmids,
            )

            timestamp = now_utc()
            record = LiteratureRecord(
                id=new_id(),
                project_id=project_id,
                title=data.title.strip(),
                doi=data.doi,
                pmid=data.pmid,
                zotero_item_key=data.zotero_item_key,
                zotero_library_id=data.zotero_library_id,
                bibtex_key=data.bibtex_key,
                creators=data.creators or [],
                publication_year=data.publication_year,
                journal=data.journal,
                metadata_json=data.metadata_json or {},
                sync_status="local",
                created_at=timestamp,
                updated_at=timestamp,
            )
            session.add(record)
            session.flush()
            self._audit(
                session,
                project_id=project_id,
                action="literature_record.created",
                target_type="literature_record",
                target_id=record.id,
            )
        return record

    def list_literature_records(self, project_id: str) -> list[LiteratureRecord]:
        with self.sessions() as session:
            return list(
                session.scalars(
                    select(LiteratureRecord)
                    .where(LiteratureRecord.project_id == project_id)
                    .order_by(LiteratureRecord.created_at)
                )
            )

    def find_by_doi(self, project_id: str, doi: str) -> LiteratureRecord | None:
        with self.sessions() as session:
            return session.scalar(
                select(LiteratureRecord).where(
                    LiteratureRecord.project_id == project_id,
                    LiteratureRecord.doi == doi,
                )
            )

    # -- attachment versions -----------------------------------------------

    def create_attachment_version(
        self, *, project_id: str, data: AttachmentInput
    ) -> AttachmentVersionRecord:
        with self.sessions.begin() as session:
            latest = session.scalar(
                select(AttachmentVersionRecord.version)
                .where(
                    AttachmentVersionRecord.literature_record_id
                    == data.literature_record_id
                )
                .order_by(AttachmentVersionRecord.version.desc())
                .limit(1)
            )
            version = AttachmentVersionRecord(
                id=new_id(),
                literature_record_id=data.literature_record_id,
                attachment_key=data.attachment_key,
                version=(latest or 0) + 1,
                content_hash=data.content_hash,
                uri=data.uri,
                media_type=data.media_type,
                created_by_run_id=data.created_by_run_id,
                created_at=now_utc(),
            )
            session.add(version)
            session.flush()
            self._audit(
                session,
                project_id=project_id,
                action="attachment_version.created",
                target_type="attachment_version",
                target_id=version.id,
                workflow_run_id=data.created_by_run_id,
            )
        return version

    # -- source spans ------------------------------------------------------

    def create_source_span(self, *, data: SourceSpanInput) -> SourceSpanRecord:
        with self.sessions.begin() as session:
            record = SourceSpanRecord(
                id=new_id(),
                project_id=data.project_id,
                literature_record_id=data.literature_record_id,
                attachment_version_id=data.attachment_version_id,
                page=data.page,
                section_label=data.section_label,
                chunk_index=data.chunk_index,
                char_start=data.char_start,
                char_end=data.char_end,
                quote_hash=data.quote_hash,
                created_by_run_id=data.created_by_run_id,
                created_at=now_utc(),
            )
            session.add(record)
            session.flush()
            self._audit(
                session,
                project_id=data.project_id,
                action="source_span.created",
                target_type="source_span",
                target_id=record.id,
                workflow_run_id=data.created_by_run_id,
            )
        return record

    # -- evidence items ----------------------------------------------------

    def create_evidence_item(self, *, data: EvidenceInput) -> EvidenceItemRecord:
        candidate = EvidenceCandidate(
            concept=data.concept,
            source_span_ids=data.source_span_ids,
            literature_record_id=data.literature_record_id,
            extraction_status=data.extraction_status,
            requires_human_review=data.requires_human_review,
        )
        require_source_span_for_evidence(candidate)

        with self.sessions.begin() as session:
            record = EvidenceItemRecord(
                id=new_id(),
                project_id=data.project_id,
                concept=data.concept,
                value=data.value,
                units=data.units,
                population=data.population,
                certainty=data.certainty,
                extraction_status=data.extraction_status,
                source_span_ids=list(data.source_span_ids),
                literature_record_id=data.literature_record_id,
                created_by_run_id=data.created_by_run_id,
                created_at=now_utc(),
                requires_human_review=data.requires_human_review,
            )
            session.add(record)
            session.flush()
            self._audit(
                session,
                project_id=data.project_id,
                action="evidence_item.created",
                target_type="evidence_item",
                target_id=record.id,
                workflow_run_id=data.created_by_run_id,
            )
        return record

    def list_evidence_items(self, project_id: str) -> list[EvidenceItemRecord]:
        with self.sessions() as session:
            return list(
                session.scalars(
                    select(EvidenceItemRecord)
                    .where(EvidenceItemRecord.project_id == project_id)
                    .order_by(EvidenceItemRecord.created_at)
                )
            )

    # -- screening decisions -----------------------------------------------

    def create_screening_decision(
        self, *, data: ScreeningInput
    ) -> ScreeningDecisionRecord:
        with self.sessions.begin() as session:
            existing = session.scalar(
                select(ScreeningDecisionRecord).where(
                    ScreeningDecisionRecord.literature_record_id
                    == data.literature_record_id,
                    ScreeningDecisionRecord.stage == data.stage,
                )
            )
            if existing is not None:
                raise ValueError(
                    "Screening decision already exists for this record and stage"
                )

            record = ScreeningDecisionRecord(
                id=new_id(),
                project_id=data.project_id,
                literature_record_id=data.literature_record_id,
                stage=data.stage,
                decision=data.decision,
                reason=data.reason,
                reviewer_id=data.reviewer_id,
                decided_at=now_utc(),
            )
            session.add(record)
            session.flush()
            self._audit(
                session,
                project_id=data.project_id,
                actor_id=data.reviewer_id,
                action="screening_decision.created",
                target_type="screening_decision",
                target_id=record.id,
            )
        return record

    def screening_counts(self, project_id: str) -> tuple[int, int, int]:
        """Return (total, included, excluded) for a project's latest screening stage."""

        with self.sessions() as session:
            total = (
                session.scalar(
                    select(func.count(LiteratureRecord.id)).where(
                        LiteratureRecord.project_id == project_id
                    )
                )
                or 0
            )
            included = (
                session.scalar(
                    select(func.count(ScreeningDecisionRecord.id)).where(
                        ScreeningDecisionRecord.project_id == project_id,
                        ScreeningDecisionRecord.decision == "included",
                    )
                )
                or 0
            )
            excluded = (
                session.scalar(
                    select(func.count(ScreeningDecisionRecord.id)).where(
                        ScreeningDecisionRecord.project_id == project_id,
                        ScreeningDecisionRecord.decision == "excluded",
                    )
                )
                or 0
            )
        return total, included, excluded

    # -- provenance links --------------------------------------------------

    def create_provenance_link(
        self, *, data: ProvenanceLinkInput
    ) -> ProvenanceLinkRecord:
        with self.sessions.begin() as session:
            existing = session.scalar(
                select(ProvenanceLinkRecord).where(
                    ProvenanceLinkRecord.source_version_id == data.source_version_id,
                    ProvenanceLinkRecord.target_version_id == data.target_version_id,
                    ProvenanceLinkRecord.relation == data.relation,
                )
            )
            if existing is not None:
                return existing

            record = ProvenanceLinkRecord(
                id=new_id(),
                project_id=data.project_id,
                source_version_id=data.source_version_id,
                source_type=data.source_type,
                target_version_id=data.target_version_id,
                target_type=data.target_type,
                relation=data.relation,
                created_by_run_id=data.created_by_run_id,
                created_at=now_utc(),
            )
            session.add(record)
            session.flush()
            self._audit(
                session,
                project_id=data.project_id,
                action="provenance_link.created",
                target_type="provenance_link",
                target_id=record.id,
                workflow_run_id=data.created_by_run_id,
            )
        return record

    # -- shared ------------------------------------------------------------

    @staticmethod
    def _audit(
        session: Session,
        *,
        project_id: str,
        action: str,
        target_type: str,
        target_id: str,
        actor_type: str = "agent",
        actor_id: str = "literature-agent",
        workflow_run_id: str | None = None,
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
                outcome="success",
                event_metadata={},
                occurred_at=now_utc(),
            )
        )


__all__ = [
    "AttachmentInput",
    "EvidenceInput",
    "LiteratureInput",
    "LiteratureRepository",
    "ProvenanceLinkInput",
    "ScreeningInput",
    "SourceSpanInput",
]
