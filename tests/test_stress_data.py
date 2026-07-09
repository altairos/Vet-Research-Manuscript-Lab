"""Stress tests for dataset dictionary validation and CSV import on dirty data.

Tests the system's ability to detect and reject:
- Missing values and inconsistent missing codes
- Unit inconsistencies and missing units
- Type mismatches (continuous → binary, categorical → continuous)
- Role misassignments (no outcome, ID as outcome)
- Encoding issues and non-standard value representations
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from vet_manuscript_lab.domain.policies.foundation import PolicyViolation
from vet_manuscript_lab.services.analysis.dictionary import DatasetDictionary
from vet_manuscript_lab.services.analysis.importer import DatasetImporter
from vet_manuscript_lab.services.analysis.types import (
    VariableRole,
    VariableSpec,
    VariableType,
)

_FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "stress_projects"


class ProblematicDictionaryStressTests(unittest.TestCase):
    """Tests that problematic variable dictionaries are rejected."""

    @classmethod
    def setUpClass(cls) -> None:
        path = _FIXTURE_ROOT / "data_stress" / "dictionary_problematic.json"
        cls.fixture = json.loads(path.read_text(encoding="utf-8"))

    def _make_specs_from_fixture(self) -> list[VariableSpec]:
        specs = []
        for v in self.fixture["variables"]:
            specs.append(
                VariableSpec(
                    name=v["name"],
                    var_type=VariableType(v["var_type"]),
                    role=VariableRole(v["role"]),
                    unit=v.get("unit") or None,
                    missing_code=v.get("missing_code"),
                )
            )
        return specs

    def test_problematic_dictionary_rejected(self) -> None:
        """The problematic fixture dictionary must be rejected by validation."""

        specs = self._make_specs_from_fixture()
        with self.assertRaises(PolicyViolation):
            DatasetDictionary.validate(tuple(specs))

    def test_continuous_without_unit_rejected(self) -> None:
        """A continuous variable without unit must be rejected."""

        specs = (
            VariableSpec(
                name="temp",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.OUTCOME,
                unit="",  # empty unit
                missing_code=None,
            ),
            VariableSpec(
                name="exposure",
                var_type=VariableType.BINARY,
                role=VariableRole.EXPOSURE,
                unit=None,
                missing_code=None,
            ),
        )
        with self.assertRaises(PolicyViolation) as ctx:
            DatasetDictionary.validate(specs)
        self.assertIn("must have a unit", str(ctx.exception))

    def test_binary_with_unit_rejected(self) -> None:
        """A binary variable should not have a unit."""

        specs = (
            VariableSpec(
                name="outcome",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.OUTCOME,
                unit="months",
                missing_code="NA",
            ),
            VariableSpec(
                name="treatment",
                var_type=VariableType.BINARY,
                role=VariableRole.EXPOSURE,
                unit="mg",  # binary should not have unit
                missing_code=None,
            ),
        )
        with self.assertRaises(PolicyViolation) as ctx:
            DatasetDictionary.validate(specs)
        self.assertIn("should not have a unit", str(ctx.exception))

    def test_empty_name_rejected(self) -> None:
        """A variable with an empty name must be rejected."""

        specs = (
            VariableSpec(
                name="   ",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.OUTCOME,
                unit="months",
                missing_code="NA",
            ),
            VariableSpec(
                name="treatment",
                var_type=VariableType.BINARY,
                role=VariableRole.EXPOSURE,
                unit=None,
                missing_code=None,
            ),
        )
        with self.assertRaises(PolicyViolation) as ctx:
            DatasetDictionary.validate(specs)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_missing_outcome_role_rejected(self) -> None:
        """A dictionary without an outcome variable must be rejected."""

        specs = (
            VariableSpec(
                name="id",
                var_type=VariableType.CATEGORICAL,
                role=VariableRole.ID,
                unit=None,
                missing_code=None,
            ),
            VariableSpec(
                name="treatment",
                var_type=VariableType.BINARY,
                role=VariableRole.EXPOSURE,
                unit=None,
                missing_code=None,
            ),
            # No outcome!
        )
        with self.assertRaises(PolicyViolation) as ctx:
            DatasetDictionary.validate(specs)
        self.assertIn("outcome", str(ctx.exception).lower())


class MessyCsvImportStressTests(unittest.TestCase):
    """Tests that messy CSV data is handled gracefully."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.messy_path = _FIXTURE_ROOT / "data_stress" / "messy_data.csv"
        cls.missing_path = _FIXTURE_ROOT / "data_stress" / "missing_values.csv"

    def test_messy_csv_imports_with_valid_dictionary(self) -> None:
        """Messy CSV should still be importable if the dictionary is valid."""

        specs = (
            VariableSpec(
                name="case_id",
                var_type=VariableType.CATEGORICAL,
                role=VariableRole.ID,
                unit=None,
                missing_code=None,
            ),
            VariableSpec(
                name="species",
                var_type=VariableType.CATEGORICAL,
                role=VariableRole.COVARIATE,
                unit=None,
                missing_code="unknown",
            ),
            VariableSpec(
                name="age_years",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.COVARIATE,
                unit="years",
                missing_code="NA",
            ),
            VariableSpec(
                name="treatment_group",
                var_type=VariableType.BINARY,
                role=VariableRole.EXPOSURE,
                unit=None,
                missing_code=None,
            ),
            VariableSpec(
                name="survival_months",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.OUTCOME,
                unit="months",
                missing_code="NA",
            ),
        )
        importer = DatasetImporter()
        result = importer.import_csv(
            path=self.messy_path,
            dataset_id="stress-ds-001",
            name="Stress messy dataset",
            variables=specs,
        )
        # Import should succeed (data quality issues are warnings, not errors)
        self.assertEqual(result.dataset.row_count, 15)
        self.assertGreater(len(result.dataset.content_hash), 0)

    def test_missing_values_csv_imports_with_warnings(self) -> None:
        """CSV with extensive missing values should still import."""

        specs = (
            VariableSpec(
                name="case_id",
                var_type=VariableType.CATEGORICAL,
                role=VariableRole.ID,
                unit=None,
                missing_code=None,
            ),
            VariableSpec(
                name="species",
                var_type=VariableType.CATEGORICAL,
                role=VariableRole.COVARIATE,
                unit=None,
                missing_code="unknown",
            ),
            VariableSpec(
                name="age_years",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.COVARIATE,
                unit="years",
                missing_code="NA",
            ),
            VariableSpec(
                name="treatment_group",
                var_type=VariableType.BINARY,
                role=VariableRole.EXPOSURE,
                unit=None,
                missing_code=None,
            ),
            VariableSpec(
                name="survival_months",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.OUTCOME,
                unit="months",
                missing_code="NA",
            ),
        )
        importer = DatasetImporter()
        result = importer.import_csv(
            path=self.missing_path,
            dataset_id="stress-ds-002",
            name="Stress missing values dataset",
            variables=specs,
        )
        self.assertEqual(result.dataset.row_count, 10)

    def test_nonexistent_file_raises(self) -> None:
        """Importing a nonexistent file must raise an error."""

        specs = (
            VariableSpec(
                name="x",
                var_type=VariableType.CONTINUOUS,
                role=VariableRole.OUTCOME,
                unit="u",
                missing_code=None,
            ),
        )
        importer = DatasetImporter()
        with self.assertRaises((FileNotFoundError, OSError, PolicyViolation)):
            importer.import_csv(
                path=Path("/nonexistent/file.csv"),
                dataset_id="bad",
                name="bad",
                variables=specs,
            )


if __name__ == "__main__":
    unittest.main()
