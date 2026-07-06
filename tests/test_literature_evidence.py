"""Tests for the literature and evidence aggregate (migration 0002)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from vet_manuscript_lab.domain.conventions import sha256_bytes
from vet_manuscript_lab.domain.policies import (
    EvidenceCandidate,
    PolicyViolation,
    ScreeningSummary,
    SearchGateSnapshot,
    require_non_duplicate_reference,
    require_screening_complete,
    require_search_approved,
    require_source_span_for_evidence,
)
from vet_manuscript_lab.infrastructure.database import create_database
from vet_manuscript_lab.infrastructure.database.literature import (
    AttachmentInput,
    EvidenceInput,
    LiteratureInput,
    LiteratureRepository,
    ProvenanceLinkInput,
    ScreeningInput,
    SourceSpanInput,
)
from vet_manuscript_lab.infrastructure.database.repository import (
    FoundationRepository,
    ProjectInput,
)


class LiteratureRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.database = create_database(f"sqlite:///{root / 'domain.sqlite'}")
        self.database.create_schema()

        self.foundation = FoundationRepository(self.database.sessions)
        self.repo = LiteratureRepository(self.database.sessions)

        self.project = self.foundation.create_project(
            ProjectInput(
                title="Test project",
                study_type="retrospective_observational_clinical_study",
                species_scope=["canine"],
                owner_id="owner-1",
            )
        )
        self.run = self.foundation.create_run(self.project.id, "thread-lit")

    def tearDown(self) -> None:
        self.database.engine.dispose()

    # -- literature records ------------------------------------------------

    def test_create_and_list_literature_record(self) -> None:
        record = self.repo.create_literature_record(
            project_id=self.project.id,
            data=LiteratureInput(
                title="Feline CKD progression markers",
                doi="10.1000/test1",
                pmid="12345678",
                creators=[{"family": "Smith", "given": "J"}],
                publication_year=2024,
                journal="J Vet Intern Med",
            ),
        )
        self.assertEqual(record.doi, "10.1000/test1")
        self.assertEqual(record.pmid, "12345678")

        records = self.repo.list_literature_records(self.project.id)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].id, record.id)

    def test_duplicate_doi_is_rejected(self) -> None:
        self.repo.create_literature_record(
            project_id=self.project.id,
            data=LiteratureInput(title="Paper A", doi="10.1000/dup"),
        )
        with self.assertRaises(PolicyViolation):
            self.repo.create_literature_record(
                project_id=self.project.id,
                data=LiteratureInput(title="Paper B", doi="10.1000/dup"),
            )

    def test_duplicate_pmid_is_rejected(self) -> None:
        self.repo.create_literature_record(
            project_id=self.project.id,
            data=LiteratureInput(title="Paper A", pmid="999"),
        )
        with self.assertRaises(PolicyViolation):
            self.repo.create_literature_record(
                project_id=self.project.id,
                data=LiteratureInput(title="Paper B", pmid="999"),
            )

    def test_same_doi_in_different_projects_is_allowed(self) -> None:
        project2 = self.foundation.create_project(
            ProjectInput(
                title="Project 2",
                study_type="retrospective_observational_clinical_study",
                species_scope=["feline"],
                owner_id="owner-2",
            )
        )
        self.repo.create_literature_record(
            project_id=self.project.id,
            data=LiteratureInput(title="A", doi="10.1000/shared"),
        )
        record2 = self.repo.create_literature_record(
            project_id=project2.id,
            data=LiteratureInput(title="B", doi="10.1000/shared"),
        )
        self.assertEqual(record2.doi, "10.1000/shared")

    # -- attachment versions -----------------------------------------------

    def test_create_attachment_version_increments(self) -> None:
        record = self._create_record()
        payload_hash = sha256_bytes(b"pdf content v1")

        att1 = self.repo.create_attachment_version(
            project_id=self.project.id,
            data=AttachmentInput(
                literature_record_id=record.id,
                attachment_key="full_text",
                content_hash=payload_hash,
                uri=f"artifact://{payload_hash}",
                media_type="application/pdf",
                created_by_run_id=self.run.id,
            ),
        )
        self.assertEqual(att1.version, 1)

        payload_hash2 = sha256_bytes(b"pdf content v2")
        att2 = self.repo.create_attachment_version(
            project_id=self.project.id,
            data=AttachmentInput(
                literature_record_id=record.id,
                attachment_key="full_text",
                content_hash=payload_hash2,
                uri=f"artifact://{payload_hash2}",
                media_type="application/pdf",
                created_by_run_id=self.run.id,
            ),
        )
        self.assertEqual(att2.version, 2)

    # -- source spans + evidence -------------------------------------------

    def test_evidence_without_source_span_is_rejected(self) -> None:
        record = self._create_record()
        with self.assertRaises(PolicyViolation):
            self.repo.create_evidence_item(
                data=EvidenceInput(
                    project_id=self.project.id,
                    concept="sample_size",
                    literature_record_id=record.id,
                    source_span_ids=[],
                )
            )

    def test_create_evidence_with_source_span(self) -> None:
        record = self._create_record()
        span = self.repo.create_source_span(
            data=SourceSpanInput(
                project_id=self.project.id,
                literature_record_id=record.id,
                quote_hash=sha256_bytes(b"quoted text"),
                page=5,
                section_label="Results",
                char_start=100,
                char_end=250,
            )
        )
        evidence = self.repo.create_evidence_item(
            data=EvidenceInput(
                project_id=self.project.id,
                concept="sample_size",
                value="42",
                units="dogs",
                literature_record_id=record.id,
                source_span_ids=[span.id],
            )
        )
        self.assertEqual(evidence.source_span_ids, [span.id])
        self.assertEqual(evidence.value, "42")

        items = self.repo.list_evidence_items(self.project.id)
        self.assertEqual(len(items), 1)

    # -- screening ---------------------------------------------------------

    def test_create_screening_decision(self) -> None:
        record = self._create_record()
        decision = self.repo.create_screening_decision(
            data=ScreeningInput(
                project_id=self.project.id,
                literature_record_id=record.id,
                stage="title_abstract",
                decision="included",
                reviewer_id="reviewer-1",
            )
        )
        self.assertEqual(decision.decision, "included")

        total, included, excluded = self.repo.screening_counts(self.project.id)
        self.assertEqual(total, 1)
        self.assertEqual(included, 1)
        self.assertEqual(excluded, 0)

    def test_duplicate_screening_decision_raises(self) -> None:
        record = self._create_record()
        self.repo.create_screening_decision(
            data=ScreeningInput(
                project_id=self.project.id,
                literature_record_id=record.id,
                stage="title_abstract",
                decision="included",
                reviewer_id="reviewer-1",
            )
        )
        with self.assertRaises(ValueError):
            self.repo.create_screening_decision(
                data=ScreeningInput(
                    project_id=self.project.id,
                    literature_record_id=record.id,
                    stage="title_abstract",
                    decision="excluded",
                    reviewer_id="reviewer-1",
                )
            )

    # -- provenance links --------------------------------------------------

    def test_create_provenance_link_idempotent(self) -> None:
        link1 = self.repo.create_provenance_link(
            data=ProvenanceLinkInput(
                project_id=self.project.id,
                source_version_id="search-v1",
                source_type="search_strategy",
                target_version_id="evidence-ledger-v1",
                target_type="evidence_ledger",
                relation="derived_from",
            )
        )
        link2 = self.repo.create_provenance_link(
            data=ProvenanceLinkInput(
                project_id=self.project.id,
                source_version_id="search-v1",
                source_type="search_strategy",
                target_version_id="evidence-ledger-v1",
                target_type="evidence_ledger",
                relation="derived_from",
            )
        )
        self.assertEqual(link1.id, link2.id)

    # -- helpers -----------------------------------------------------------

    def _create_record(self):
        return self.repo.create_literature_record(
            project_id=self.project.id,
            data=LiteratureInput(title="Test reference", doi="10.1000/test-ref"),
        )


class EvidencePolicyTests(unittest.TestCase):
    def test_require_source_span_passes_with_spans(self) -> None:
        evidence = EvidenceCandidate(
            concept="sample_size",
            source_span_ids=["span-1"],
            literature_record_id="lit-1",
            extraction_status="draft",
            requires_human_review=False,
        )
        require_source_span_for_evidence(evidence)

    def test_require_source_span_fails_without_spans(self) -> None:
        evidence = EvidenceCandidate(
            concept="sample_size",
            source_span_ids=[],
            literature_record_id="lit-1",
            extraction_status="draft",
            requires_human_review=False,
        )
        with self.assertRaises(PolicyViolation):
            require_source_span_for_evidence(evidence)

    def test_require_search_approved_passes(self) -> None:
        gate = SearchGateSnapshot(approved=True, subject_version_id="search-v1")
        result = require_search_approved(gate)
        self.assertEqual(result.subject_version_id, "search-v1")

    def test_require_search_approved_fails_when_missing(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_search_approved(None)

    def test_require_search_approved_fails_when_not_approved(self) -> None:
        gate = SearchGateSnapshot(approved=False, subject_version_id="search-v1")
        with self.assertRaises(PolicyViolation):
            require_search_approved(gate)

    def test_require_screening_complete_passes(self) -> None:
        summary = ScreeningSummary(total_records=5, included_count=3, excluded_count=2)
        require_screening_complete(summary)

    def test_require_screening_complete_fails_on_mismatch(self) -> None:
        summary = ScreeningSummary(total_records=5, included_count=3, excluded_count=1)
        with self.assertRaises(PolicyViolation):
            require_screening_complete(summary)

    def test_require_non_duplicate_reference_passes(self) -> None:
        require_non_duplicate_reference(
            doi="10.1000/new",
            pmid=None,
            existing_dois=frozenset({"10.1000/old"}),
            existing_pmids=frozenset(),
        )

    def test_require_non_duplicate_reference_fails_on_doi(self) -> None:
        with self.assertRaises(PolicyViolation):
            require_non_duplicate_reference(
                doi="10.1000/dup",
                pmid=None,
                existing_dois=frozenset({"10.1000/dup"}),
                existing_pmids=frozenset(),
            )


class Migration0002Tests(unittest.TestCase):
    def test_literature_migration_adds_all_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "migrated.sqlite"
            config = Config("alembic.ini")
            config.set_main_option("sqlalchemy.url", f"sqlite:///{path}")
            command.upgrade(config, "head")

            engine = create_engine(f"sqlite:///{path}")
            tables = set(inspect(engine).get_table_names())
            engine.dispose()

            expected = {
                "literature_records",
                "attachment_versions",
                "source_spans",
                "evidence_items",
                "screening_decisions",
                "provenance_links",
            }
            self.assertTrue(expected.issubset(tables))


if __name__ == "__main__":
    unittest.main()
