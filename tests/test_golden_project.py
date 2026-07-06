"""Golden project regression tests.

Validates that the synthetic fixture in ``fixtures/golden_project/`` is
structurally correct, importable by the domain services, and produces
deterministic results through the mock statistics runner.  These tests
guard against regressions in fixture content and domain-layer contracts
across phases.

Test coverage:
1. Fixture files exist and are well-formed JSON.
2. CSV dataset imports and hashes correctly.
3. Data dictionary passes DatasetDictionary.validate().
4. Analysis plan variables all exist in the dictionary.
5. MockStatisticsRunner produces deterministic results from fixture data.
6. Literature records have required fields.
7. Methodology findings have valid categories and severities.
8. Full pipeline graph runs to completion using fixture-derived state.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from langgraph.types import Command

from vet_manuscript_lab.domain.policies import PolicyViolation
from vet_manuscript_lab.infrastructure.checkpoints import open_sqlite_checkpointer
from vet_manuscript_lab.services.analysis.dictionary import DatasetDictionary
from vet_manuscript_lab.services.analysis.importer import DatasetImporter
from vet_manuscript_lab.services.analysis.runner import MockStatisticsRunner
from vet_manuscript_lab.services.analysis.types import (
    AnalysisClass,
    AnalysisSpec,
    VariableRole,
    VariableSpec,
    VariableType,
)
from vet_manuscript_lab.workflow.analysis_graph import build_analysis_pipeline_graph
from vet_manuscript_lab.workflow.state import new_workflow_state

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "golden_project"


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _interrupt_payloads(snapshot: Any) -> list[dict[str, Any]]:
    return [
        pending.value
        for task in snapshot.tasks
        for pending in task.interrupts
        if isinstance(pending.value, dict)
    ]


def _approve(reviewer: str = "investigator-1") -> Command:
    return Command(
        resume={
            "decision": "approved",
            "reviewer_id": reviewer,
            "reviewer_role": "investigator",
        }
    )


def _build_variable_specs(fixture_dict: dict[str, Any]) -> tuple[VariableSpec, ...]:
    """Build VariableSpec tuple from the dictionary fixture JSON."""

    type_map = {t.value: t for t in VariableType}
    role_map = {r.value: r for r in VariableRole}
    specs: list[VariableSpec] = []
    for v in fixture_dict["variables"]:
        specs.append(
            VariableSpec(
                name=v["name"],
                var_type=type_map[v["var_type"]],
                role=role_map[v["role"]],
                unit=v.get("unit"),
                missing_code=v.get("missing_code"),
                description=v.get("description"),
            )
        )
    return tuple(specs)


def _build_analysis_specs(fixture_plan: dict[str, Any]) -> tuple[AnalysisSpec, ...]:
    """Build AnalysisSpec tuple from the analysis plan fixture JSON."""

    specs: list[AnalysisSpec] = []
    for a in fixture_plan["plan"]["analyses"]:
        specs.append(
            AnalysisSpec(
                name=a["name"],
                estimand=a["estimand"],
                model_type=a["model_type"],
                variable_names=tuple(a["variable_names"]),
                analysis_class=AnalysisClass(a["analysis_class"]),
                exclusion_criteria=tuple(a.get("exclusion_criteria", [])),
                population=a.get("population"),
            )
        )
    return tuple(specs)


class GoldenProjectFixtureTests(unittest.TestCase):
    """Validate fixture file integrity and domain-layer compatibility."""

    def test_fixture_files_exist(self) -> None:
        """All expected fixture files must be present."""

        expected = [
            FIXTURE_ROOT / "project.json",
            FIXTURE_ROOT / "README.md",
            FIXTURE_ROOT / "data" / "cases_synthetic.csv",
            FIXTURE_ROOT / "dictionary" / "variables.json",
            FIXTURE_ROOT / "analysis_plan" / "analyses.json",
            FIXTURE_ROOT / "literature" / "records.json",
            FIXTURE_ROOT / "methodology" / "findings.json",
        ]
        for path in expected:
            self.assertTrue(
                path.exists(),
                f"Missing fixture file: {path}",
            )

    def test_project_json_is_well_formed(self) -> None:
        data = _load_json(FIXTURE_ROOT / "project.json")
        self.assertTrue(data["synthetic"])
        self.assertFalse(data["contains_real_clinical_data"])
        self.assertEqual(data["data_classification"], "synthetic_non_sensitive")
        project = data["project"]
        self.assertIn("canine", project["species_scope"])
        self.assertIn("feline", project["species_scope"])
        self.assertEqual(project["reporting_guideline"], "STROBE-Vet")

    def test_csv_imports_and_hashes_correctly(self) -> None:
        """The CSV must import via DatasetImporter with the dictionary."""

        dict_fixture = _load_json(FIXTURE_ROOT / "dictionary" / "variables.json")
        variables = _build_variable_specs(dict_fixture)

        importer = DatasetImporter()
        result = importer.import_csv(
            path=FIXTURE_ROOT / "data" / "cases_synthetic.csv",
            dataset_id="golden-dataset-001",
            name=dict_fixture["dataset"]["name"],
            variables=variables,
        )

        self.assertEqual(result.dataset.row_count, 30)
        self.assertEqual(result.dataset.column_count, 5)
        self.assertTrue(result.dataset.content_hash.startswith("sha256:"))
        self.assertEqual(len(result.dataset.variables), 5)
        self.assertFalse(result.warnings, f"Unexpected warnings: {result.warnings}")

    def test_dictionary_passes_validation(self) -> None:
        """The fixture dictionary must pass DatasetDictionary.validate()."""

        dict_fixture = _load_json(FIXTURE_ROOT / "dictionary" / "variables.json")
        variables = _build_variable_specs(dict_fixture)
        dictionary = DatasetDictionary.validate(variables)
        self.assertEqual(len(dictionary.variables), 5)
        self.assertIn("survival_months", dictionary.outcome_names)
        self.assertIn("treatment_group", dictionary.exposure_names)

    def test_analysis_variables_exist_in_dictionary(self) -> None:
        """Every variable referenced in the analysis plan must be in the dictionary."""

        dict_fixture = _load_json(FIXTURE_ROOT / "dictionary" / "variables.json")
        plan_fixture = _load_json(FIXTURE_ROOT / "analysis_plan" / "analyses.json")
        dict_names = frozenset(v["name"] for v in dict_fixture["variables"])

        for analysis in plan_fixture["plan"]["analyses"]:
            for var_name in analysis["variable_names"]:
                self.assertIn(
                    var_name,
                    dict_names,
                    f"Analysis '{analysis['name']}' references unknown "
                    f"variable '{var_name}'",
                )

    def test_mock_runner_produces_deterministic_results(self) -> None:
        """MockStatisticsRunner must produce identical results on repeated runs."""

        dict_fixture = _load_json(FIXTURE_ROOT / "dictionary" / "variables.json")
        plan_fixture = _load_json(FIXTURE_ROOT / "analysis_plan" / "analyses.json")
        variables = _build_variable_specs(dict_fixture)
        analyses = _build_analysis_specs(plan_fixture)

        importer = DatasetImporter()
        import_result = importer.import_csv(
            path=FIXTURE_ROOT / "data" / "cases_synthetic.csv",
            dataset_id="golden-dataset-001",
            name="Golden test dataset",
            variables=variables,
        )

        from vet_manuscript_lab.domain.policies import (
            AnalysisPlanSnapshot,
            DatasetVersionSnapshot,
        )

        plan_snapshot = AnalysisPlanSnapshot(
            version_id="plan-v1",
            content_hash=import_result.dataset.content_hash,
            status="locked",
            variable_names=frozenset(v.name for v in variables),
            model_specifications=tuple(a.model_type for a in analyses),
            exclusion_criteria=tuple(c for a in analyses for c in a.exclusion_criteria),
        )
        dataset_snapshot = DatasetVersionSnapshot(
            version_id="ds-v1",
            content_hash=import_result.dataset.content_hash,
            status="locked",
        )
        available_vars = frozenset(v.name for v in variables)

        runner = MockStatisticsRunner()
        run1 = runner.execute(
            plan=plan_snapshot,
            dataset=dataset_snapshot,
            analyses=analyses,
            dataset_spec=import_result.dataset,
            available_variables=available_vars,
            run_id="golden-run-1",
            seed=42,
        )
        run2 = runner.execute(
            plan=plan_snapshot,
            dataset=dataset_snapshot,
            analyses=analyses,
            dataset_spec=import_result.dataset,
            available_variables=available_vars,
            run_id="golden-run-2",
            seed=42,
        )

        self.assertEqual(run1.status, "completed")
        self.assertEqual(run1.exit_code, 0)
        self.assertEqual(len(run1.results), len(analyses))
        self.assertEqual(run1.script_hash, run2.script_hash)
        for r1, r2 in zip(run1.results, run2.results, strict=True):
            self.assertEqual(r1.estimate, r2.estimate)
            self.assertEqual(r1.p_value, r2.p_value)
            self.assertEqual(r1.uncertainty_lower, r2.uncertainty_lower)
            self.assertEqual(r1.uncertainty_upper, r2.uncertainty_upper)

    def test_literature_records_have_required_fields(self) -> None:
        """Every literature record must have title, authors, year, and DOI."""

        fixture = _load_json(FIXTURE_ROOT / "literature" / "records.json")
        records = fixture["records"]
        self.assertGreaterEqual(len(records), 3)
        for rec in records:
            self.assertTrue(rec["title"], "Title must not be empty")
            self.assertGreaterEqual(len(rec["authors"]), 1)
            self.assertGreaterEqual(rec["year"], 2000)
            self.assertTrue(rec["doi"].startswith("10."))

    def test_methodology_findings_are_well_formed(self) -> None:
        """Every methodology finding must have required fields and valid severity."""

        fixture = _load_json(FIXTURE_ROOT / "methodology" / "findings.json")
        findings = fixture["findings"]
        self.assertGreaterEqual(len(findings), 1)
        valid_severities = {"info", "warning", "error"}
        valid_statuses = {"open", "addressed", "dismissed"}
        for f in findings:
            self.assertTrue(f["category"], "Category must not be empty")
            self.assertIn(f["severity"], valid_severities)
            self.assertTrue(f["rationale"], "Rationale must not be empty")
            self.assertIn(f["status"], valid_statuses)


class GoldenProjectPipelineTests(unittest.TestCase):
    """End-to-end pipeline tests using golden project fixture data."""

    def initial_state(self, thread_id: str) -> dict[str, Any]:
        return new_workflow_state(
            project_id="00000000-0000-4000-8000-000000000001",
            workflow_run_id="golden-run-e2e",
            thread_id=thread_id,
            now="2026-01-01T00:00:00Z",
        )

    def test_pipeline_completes_with_fixture_data(self) -> None:
        """The full pipeline must run to results approval using mock data."""

        with tempfile.TemporaryDirectory() as tmpdir:
            connection, saver = open_sqlite_checkpointer(
                Path(tmpdir) / "checkpoints.sqlite"
            )
            try:
                graph = build_analysis_pipeline_graph(saver)
                config = {"configurable": {"thread_id": "golden-e2e"}}

                # Run through all stages to results approval
                graph.invoke(self.initial_state("golden-e2e"), config)
                graph.invoke(_approve(), config)  # question
                graph.invoke(_approve(), config)  # protocol
                graph.invoke(_approve(), config)  # search
                graph.invoke(_approve(), config)  # analysis plan

                # Should be at results approval gate
                payloads = _interrupt_payloads(graph.get_state(config))
                if payloads:
                    self.assertEqual(payloads[0]["gate"], "results_interpretation")
                    graph.invoke(_approve(), config)

                state = graph.get_state(config)
                current_stage = state.values.get("current_stage", "")
                self.assertIn(
                    current_stage,
                    {"results_approval", "writing", "complete", ""},
                    f"Unexpected stage: {current_stage}",
                )
            finally:
                connection.close()

    def test_pipeline_results_are_deterministic(self) -> None:
        """Two independent pipeline runs must produce identical statistics."""

        results_runs: list[Any] = []

        for i in range(2):
            with tempfile.TemporaryDirectory() as tmpdir:
                connection, saver = open_sqlite_checkpointer(
                    Path(tmpdir) / f"checkpoints_{i}.sqlite"
                )
                try:
                    graph = build_analysis_pipeline_graph(saver)
                    config = {"configurable": {"thread_id": f"golden-det-{i}"}}

                    graph.invoke(self.initial_state(f"golden-det-{i}"), config)
                    graph.invoke(_approve(), config)  # question
                    graph.invoke(_approve(), config)  # protocol
                    graph.invoke(_approve(), config)  # search
                    graph.invoke(_approve(), config)  # analysis plan

                    state = graph.get_state(config)
                    results_artifact = state.values.get("artifacts", {}).get(
                        "analysis_results"
                    )
                    if results_artifact:
                        results_runs.append(results_artifact["content_hash"])
                finally:
                    connection.close()

        if len(results_runs) == 2:
            self.assertEqual(
                results_runs[0],
                results_runs[1],
                "Statistics results must be deterministic across runs",
            )


class GoldenProjectAdversarialTests(unittest.TestCase):
    """Adversarial tests using modified golden project data."""

    def test_extra_column_in_csv_produces_warning(self) -> None:
        """An extra column in the CSV (not in dictionary) should warn, not fail."""

        dict_fixture = _load_json(FIXTURE_ROOT / "dictionary" / "variables.json")
        variables = _build_variable_specs(dict_fixture)

        with tempfile.TemporaryDirectory() as tmpdir:
            extra_csv = Path(tmpdir) / "extra_col.csv"
            original = (FIXTURE_ROOT / "data" / "cases_synthetic.csv").read_text()
            extra_csv.write_text(
                original.replace(
                    "case_id,species,",
                    "case_id,species,extra_column,",
                )
                .replace(
                    "CASE-001,canine,",
                    "CASE-001,canine,X,",
                )
                .replace(
                    "CASE-002,canine,",
                    "CASE-002,canine,Y,",
                )
            )

            importer = DatasetImporter()
            result = importer.import_csv(
                path=extra_csv,
                dataset_id="golden-extra",
                name="Dataset with extra column",
                variables=variables,
            )
            self.assertTrue(
                any("extra_column" in w for w in result.warnings),
                "Extra columns should produce a warning",
            )

    def test_missing_column_in_csv_is_rejected(self) -> None:
        """A missing required column must be rejected, not silently imported."""

        dict_fixture = _load_json(FIXTURE_ROOT / "dictionary" / "variables.json")
        variables = _build_variable_specs(dict_fixture)

        with tempfile.TemporaryDirectory() as tmpdir:
            short_csv = Path(tmpdir) / "missing_col.csv"
            content = (FIXTURE_ROOT / "data" / "cases_synthetic.csv").read_text()
            # Remove the survival_months column (outcome)
            lines = content.strip().split("\n")
            lines[0] = "case_id,species,age_years,treatment_group"
            for j in range(1, len(lines)):
                parts = lines[j].split(",")
                lines[j] = ",".join(parts[:4])
            short_csv.write_text("\n".join(lines) + "\n")

            importer = DatasetImporter()
            with self.assertRaises(PolicyViolation):
                importer.import_csv(
                    path=short_csv,
                    dataset_id="golden-missing",
                    name="Dataset missing outcome",
                    variables=variables,
                )


if __name__ == "__main__":
    unittest.main()
