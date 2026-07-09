"""Tests for Phase C — Evidence Type Schema (typed evidence classification).

Covers:
- EvidenceType enum completeness and values
- TypedEvidenceCandidate dataclass
- Type-specific required-field validation (require_valid_evidence_type)
- get_required_metadata_fields helper
- Database persistence of evidence_type + evidence_metadata
- Migration 0006 adds the new columns
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from vet_manuscript_lab.domain.conventions import EvidenceType, sha256_bytes
from vet_manuscript_lab.domain.policies import (
    PolicyViolation,
    TypedEvidenceCandidate,
    get_required_metadata_fields,
    require_valid_evidence_type,
)
from vet_manuscript_lab.infrastructure.database import create_database
from vet_manuscript_lab.infrastructure.database.literature import (
    EvidenceInput,
    LiteratureInput,
    LiteratureRepository,
    SourceSpanInput,
)
from vet_manuscript_lab.infrastructure.database.repository import (
    FoundationRepository,
    ProjectInput,
)

# ──────────────────────────────────────────────────────────────────────────────
# EvidenceType enum tests
# ──────────────────────────────────────────────────────────────────────────────


class EvidenceTypeEnumTests(unittest.TestCase):
    """Verify the EvidenceType enum has all 10 expected members."""

    EXPECTED_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "sample_characteristic",
            "diagnostic_criterion",
            "exposure_or_intervention",
            "outcome_definition",
            "statistical_result",
            "adverse_event",
            "limitation",
            "mechanistic_hypothesis",
            "guideline_requirement",
            "background_claim",
        }
    )

    def test_enum_has_all_ten_members(self) -> None:
        values = {t.value for t in EvidenceType}
        self.assertEqual(values, self.EXPECTED_TYPES)

    def test_enum_member_count(self) -> None:
        self.assertEqual(len(list(EvidenceType)), 10)

    def test_enum_is_str_enum(self) -> None:
        self.assertEqual(EvidenceType.BACKGROUND_CLAIM, "background_claim")
        self.assertEqual(str(EvidenceType.STATISTICAL_RESULT), "statistical_result")

    def test_enum_lookup_by_value(self) -> None:
        et = EvidenceType("adverse_event")
        self.assertIs(et, EvidenceType.ADVERSE_EVENT)


# ──────────────────────────────────────────────────────────────────────────────
# TypedEvidenceCandidate dataclass tests
# ──────────────────────────────────────────────────────────────────────────────


class TypedEvidenceCandidateTests(unittest.TestCase):
    def test_basic_construction(self) -> None:
        c = TypedEvidenceCandidate(
            concept="sample_size",
            evidence_type=EvidenceType.SAMPLE_CHARACTERISTIC,
            source_span_ids=["span-1"],
            literature_record_id="rec-1",
            extraction_status="draft",
            requires_human_review=False,
        )
        self.assertEqual(c.concept, "sample_size")
        self.assertEqual(c.evidence_type, EvidenceType.SAMPLE_CHARACTERISTIC)

    def test_is_frozen(self) -> None:
        c = TypedEvidenceCandidate(
            concept="x",
            evidence_type=EvidenceType.BACKGROUND_CLAIM,
            source_span_ids=["s"],
            literature_record_id="r",
            extraction_status="draft",
            requires_human_review=False,
        )
        with self.assertRaises((AttributeError, Exception)):
            c.concept = "changed"  # type: ignore[misc]

    def test_optional_fields_default_to_none(self) -> None:
        c = TypedEvidenceCandidate(
            concept="x",
            evidence_type=EvidenceType.BACKGROUND_CLAIM,
            source_span_ids=["s"],
            literature_record_id="r",
            extraction_status="draft",
            requires_human_review=False,
        )
        self.assertIsNone(c.value)
        self.assertIsNone(c.units)
        self.assertIsNone(c.population)
        self.assertIsNone(c.metadata)


# ──────────────────────────────────────────────────────────────────────────────
# require_valid_evidence_type tests
# ──────────────────────────────────────────────────────────────────────────────


class RequireValidEvidenceTypeTests(unittest.TestCase):
    """Verify type-specific validation rules."""

    def _make(
        self,
        evidence_type: EvidenceType,
        metadata: dict[str, str] | None = None,
    ) -> TypedEvidenceCandidate:
        return TypedEvidenceCandidate(
            concept="test_concept",
            evidence_type=evidence_type,
            source_span_ids=["span-1"],
            literature_record_id="rec-1",
            extraction_status="draft",
            requires_human_review=False,
            metadata=metadata,
        )

    # -- types with no required metadata ----------------------------------

    def test_background_claim_no_metadata_required(self) -> None:
        """background_claim has no required metadata — should pass."""
        require_valid_evidence_type(self._make(EvidenceType.BACKGROUND_CLAIM))

    def test_background_claim_with_empty_metadata(self) -> None:
        require_valid_evidence_type(
            self._make(EvidenceType.BACKGROUND_CLAIM, metadata={})
        )

    def test_background_claim_with_none_metadata(self) -> None:
        require_valid_evidence_type(
            self._make(EvidenceType.BACKGROUND_CLAIM, metadata=None)
        )

    def test_sample_characteristic_no_metadata_required(self) -> None:
        require_valid_evidence_type(self._make(EvidenceType.SAMPLE_CHARACTERISTIC))

    def test_diagnostic_criterion_no_metadata_required(self) -> None:
        require_valid_evidence_type(self._make(EvidenceType.DIAGNOSTIC_CRITERION))

    def test_exposure_or_intervention_no_metadata_required(self) -> None:
        require_valid_evidence_type(self._make(EvidenceType.EXPOSURE_OR_INTERVENTION))

    def test_outcome_definition_no_metadata_required(self) -> None:
        require_valid_evidence_type(self._make(EvidenceType.OUTCOME_DEFINITION))

    def test_limitation_no_metadata_required(self) -> None:
        require_valid_evidence_type(self._make(EvidenceType.LIMITATION))

    def test_mechanistic_hypothesis_no_metadata_required(self) -> None:
        require_valid_evidence_type(self._make(EvidenceType.MECHANISTIC_HYPOTHESIS))

    # -- STATISTICAL_RESULT requires variable, groups, effect_size --------

    def test_statistical_result_valid(self) -> None:
        require_valid_evidence_type(
            self._make(
                EvidenceType.STATISTICAL_RESULT,
                metadata={
                    "variable": "mortality_rate",
                    "groups": "treatment vs control",
                    "effect_size": "RR=0.5",
                },
            )
        )

    def test_statistical_result_missing_variable(self) -> None:
        with self.assertRaises(PolicyViolation) as ctx:
            require_valid_evidence_type(
                self._make(
                    EvidenceType.STATISTICAL_RESULT,
                    metadata={
                        "groups": "treatment vs control",
                        "effect_size": "RR=0.5",
                    },
                )
            )
        self.assertIn("variable", str(ctx.exception))

    def test_statistical_result_missing_all_metadata(self) -> None:
        with self.assertRaises(PolicyViolation) as ctx:
            require_valid_evidence_type(self._make(EvidenceType.STATISTICAL_RESULT))
        msg = str(ctx.exception)
        self.assertIn("variable", msg)
        self.assertIn("groups", msg)
        self.assertIn("effect_size", msg)

    def test_statistical_result_empty_string_values(self) -> None:
        """Empty string values should be treated as missing."""
        with self.assertRaises(PolicyViolation):
            require_valid_evidence_type(
                self._make(
                    EvidenceType.STATISTICAL_RESULT,
                    metadata={
                        "variable": "",
                        "groups": "treatment vs control",
                        "effect_size": "RR=0.5",
                    },
                )
            )

    def test_statistical_result_whitespace_only_values(self) -> None:
        """Whitespace-only values should be treated as missing."""
        with self.assertRaises(PolicyViolation):
            require_valid_evidence_type(
                self._make(
                    EvidenceType.STATISTICAL_RESULT,
                    metadata={
                        "variable": "   ",
                        "groups": "treatment vs control",
                        "effect_size": "RR=0.5",
                    },
                )
            )

    # -- ADVERSE_EVENT requires event -------------------------------------

    def test_adverse_event_valid(self) -> None:
        require_valid_evidence_type(
            self._make(
                EvidenceType.ADVERSE_EVENT,
                metadata={"event": "anaphylactic_shock"},
            )
        )

    def test_adverse_event_missing_event(self) -> None:
        with self.assertRaises(PolicyViolation) as ctx:
            require_valid_evidence_type(self._make(EvidenceType.ADVERSE_EVENT))
        self.assertIn("event", str(ctx.exception))

    # -- GUIDELINE_REQUIREMENT requires guideline -------------------------

    def test_guideline_requirement_valid(self) -> None:
        require_valid_evidence_type(
            self._make(
                EvidenceType.GUIDELINE_REQUIREMENT,
                metadata={"guideline": "STROBE"},
            )
        )

    def test_guideline_requirement_missing_guideline(self) -> None:
        with self.assertRaises(PolicyViolation) as ctx:
            require_valid_evidence_type(self._make(EvidenceType.GUIDELINE_REQUIREMENT))
        self.assertIn("guideline", str(ctx.exception))

    # -- error message includes concept and type --------------------------

    def test_error_message_includes_concept(self) -> None:
        with self.assertRaises(PolicyViolation) as ctx:
            require_valid_evidence_type(
                TypedEvidenceCandidate(
                    concept="my_special_concept",
                    evidence_type=EvidenceType.ADVERSE_EVENT,
                    source_span_ids=["s"],
                    literature_record_id="r",
                    extraction_status="draft",
                    requires_human_review=False,
                )
            )
        self.assertIn("my_special_concept", str(ctx.exception))

    def test_error_message_includes_type_value(self) -> None:
        with self.assertRaises(PolicyViolation) as ctx:
            require_valid_evidence_type(self._make(EvidenceType.ADVERSE_EVENT))
        self.assertIn("adverse_event", str(ctx.exception))


# ──────────────────────────────────────────────────────────────────────────────
# get_required_metadata_fields tests
# ──────────────────────────────────────────────────────────────────────────────


class GetRequiredMetadataFieldsTests(unittest.TestCase):
    def test_statistical_result_fields(self) -> None:
        fields = get_required_metadata_fields(EvidenceType.STATISTICAL_RESULT)
        self.assertIn("variable", fields)
        self.assertIn("groups", fields)
        self.assertIn("effect_size", fields)
        self.assertEqual(len(fields), 3)

    def test_adverse_event_fields(self) -> None:
        fields = get_required_metadata_fields(EvidenceType.ADVERSE_EVENT)
        self.assertEqual(fields, ("event",))

    def test_guideline_requirement_fields(self) -> None:
        fields = get_required_metadata_fields(EvidenceType.GUIDELINE_REQUIREMENT)
        self.assertEqual(fields, ("guideline",))

    def test_background_claim_no_fields(self) -> None:
        fields = get_required_metadata_fields(EvidenceType.BACKGROUND_CLAIM)
        self.assertEqual(fields, ())

    def test_all_types_return_tuple(self) -> None:
        for et in EvidenceType:
            result = get_required_metadata_fields(et)
            self.assertIsInstance(result, tuple)


# ──────────────────────────────────────────────────────────────────────────────
# Database persistence tests
# ──────────────────────────────────────────────────────────────────────────────


class EvidenceTypeDatabaseTests(unittest.TestCase):
    """Verify evidence_type and evidence_metadata persist in the database."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.database = create_database(f"sqlite:///{root / 'test.sqlite'}")
        self.database.create_schema()

        self.foundation = FoundationRepository(self.database.sessions)
        self.repo = LiteratureRepository(self.database.sessions)

        self.project = self.foundation.create_project(
            ProjectInput(
                title="Evidence type test",
                study_type="retrospective_observational_clinical_study",
                species_scope=["canine"],
                owner_id="owner-1",
            )
        )
        self.run = self.foundation.create_run(self.project.id, "thread-evtype")

        self.record = self.repo.create_literature_record(
            project_id=self.project.id,
            data=LiteratureInput(
                title="Test paper",
                doi="10.1234/test",
            ),
        )

        self.span = self.repo.create_source_span(
            data=SourceSpanInput(
                project_id=self.project.id,
                literature_record_id=self.record.id,
                quote_hash=sha256_bytes(b"quoted evidence"),
                page=3,
                section_label="Results",
            )
        )

    def tearDown(self) -> None:
        self.database.engine.dispose()

    def test_default_evidence_type_is_background_claim(self) -> None:
        """EvidenceInput without evidence_type defaults to background_claim."""
        evidence = self.repo.create_evidence_item(
            data=EvidenceInput(
                project_id=self.project.id,
                concept="finding",
                literature_record_id=self.record.id,
                source_span_ids=[self.span.id],
            )
        )
        self.assertEqual(evidence.evidence_type, "background_claim")

    def test_persist_custom_evidence_type(self) -> None:
        evidence = self.repo.create_evidence_item(
            data=EvidenceInput(
                project_id=self.project.id,
                concept="mortality",
                literature_record_id=self.record.id,
                source_span_ids=[self.span.id],
                evidence_type="statistical_result",
            )
        )
        self.assertEqual(evidence.evidence_type, "statistical_result")

    def test_persist_evidence_metadata(self) -> None:
        meta = {
            "variable": "mortality_rate",
            "groups": "treatment vs control",
            "effect_size": "RR=0.5",
        }
        evidence = self.repo.create_evidence_item(
            data=EvidenceInput(
                project_id=self.project.id,
                concept="mortality",
                literature_record_id=self.record.id,
                source_span_ids=[self.span.id],
                evidence_type="statistical_result",
                evidence_metadata=meta,
            )
        )
        self.assertEqual(evidence.evidence_metadata["variable"], "mortality_rate")
        self.assertEqual(evidence.evidence_metadata["effect_size"], "RR=0.5")

    def test_default_evidence_metadata_is_empty_dict(self) -> None:
        evidence = self.repo.create_evidence_item(
            data=EvidenceInput(
                project_id=self.project.id,
                concept="background",
                literature_record_id=self.record.id,
                source_span_ids=[self.span.id],
            )
        )
        self.assertEqual(evidence.evidence_metadata, {})

    def test_list_evidence_returns_typed_fields(self) -> None:
        self.repo.create_evidence_item(
            data=EvidenceInput(
                project_id=self.project.id,
                concept="adverse",
                literature_record_id=self.record.id,
                source_span_ids=[self.span.id],
                evidence_type="adverse_event",
                evidence_metadata={"event": "fever"},
            )
        )
        items = self.repo.list_evidence_items(self.project.id)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].evidence_type, "adverse_event")
        self.assertEqual(items[0].evidence_metadata["event"], "fever")

    def test_none_evidence_metadata_defaults_to_empty(self) -> None:
        """EvidenceInput with evidence_metadata=None should persist as {}."""
        evidence = self.repo.create_evidence_item(
            data=EvidenceInput(
                project_id=self.project.id,
                concept="bg",
                literature_record_id=self.record.id,
                source_span_ids=[self.span.id],
                evidence_metadata=None,
            )
        )
        self.assertEqual(evidence.evidence_metadata, {})


# ──────────────────────────────────────────────────────────────────────────────
# Migration 0006 tests
# ──────────────────────────────────────────────────────────────────────────────


class Migration0006Tests(unittest.TestCase):
    """Verify migration 0006 adds evidence_type and evidence_metadata."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.db_path = self.root / "migration_test.sqlite"

    def test_migration_adds_columns(self) -> None:
        # Create schema up to migration 0005
        engine = create_engine(f"sqlite:///{self.db_path}")
        with engine.begin() as conn:
            # Run migrations 0001 through 0005
            for rev in [
                "0001_foundation",
                "0002_literature_evidence",
                "0003_methodology_statistics",
                "0004_writing_review_revision",
                "0005_compliance_export",
            ]:
                _run_migration_up(rev, conn, str(self.root))

        # Verify columns don't exist yet
        inspector = inspect(engine)
        cols_before = {c["name"] for c in inspector.get_columns("evidence_items")}
        self.assertNotIn("evidence_type", cols_before)
        self.assertNotIn("evidence_metadata", cols_before)

        # Run migration 0006
        _run_migration_up("0006_evidence_type_schema", None, str(self.root))

        # Verify columns now exist
        engine2 = create_engine(f"sqlite:///{self.db_path}")
        inspector2 = inspect(engine2)
        cols_after = {c["name"] for c in inspector2.get_columns("evidence_items")}
        self.assertIn("evidence_type", cols_after)
        self.assertIn("evidence_metadata", cols_after)
        engine.dispose()
        engine2.dispose()

    def test_migration_type_column_has_default(self) -> None:
        _run_migration_up("0006_evidence_type_schema", None, str(self.root))
        engine = create_engine(f"sqlite:///{self.db_path}")
        inspector = inspect(engine)
        col = next(
            c
            for c in inspector.get_columns("evidence_items")
            if c["name"] == "evidence_type"
        )
        # server_default may be stored as SQL literal (e.g. "'background_claim'")
        default_val = str(col.get("default") or "")
        self.assertIn("background_claim", default_val)
        engine.dispose()

    def test_migration_downgrade_removes_columns(self) -> None:
        _run_migration_up("0006_evidence_type_schema", None, str(self.root))
        _run_migration_down("0006_evidence_type_schema", None, str(self.root))
        engine = create_engine(f"sqlite:///{self.db_path}")
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("evidence_items")}
        self.assertNotIn("evidence_type", cols)
        self.assertNotIn("evidence_metadata", cols)
        engine.dispose()


def _run_migration_up(revision: str, conn, root: str) -> None:
    """Helper: run a single migration upgrade."""
    cfg = Config()
    migrations_dir = Path(__file__).parent.parent / "migrations"
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{root}/migration_test.sqlite")
    command.upgrade(cfg, revision)


def _run_migration_down(revision: str, conn, root: str) -> None:
    """Helper: run a single migration downgrade."""
    cfg = Config()
    migrations_dir = Path(__file__).parent.parent / "migrations"
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{root}/migration_test.sqlite")
    command.downgrade(cfg, "0005_compliance_export")


if __name__ == "__main__":
    unittest.main()
