"""Statistics runner: Protocol + MockStatisticsRunner.

The runner executes a locked analysis plan against a locked dataset and
returns typed results.  In MVP the ``MockStatisticsRunner`` produces
deterministic output based on the analysis specs — it does not call any
real statistical software.

Design follows the project's Backend Protocol + mock-first pattern:

1. ``StatisticsRunner`` is a Protocol so real Python/R runners can be
   substituted without changing graph nodes.
2. ``MockStatisticsRunner`` is deterministic: same plan + same dataset +
   same seed → same results.  This is critical for reproducibility tests.
3. The runner captures full execution provenance: script_hash, seed,
   package versions, environment, stdout/stderr, and exit code.
4. A failed run produces logs but never ``approved`` results.

A real runner adapter will read from a fixed input directory and write
to a fixed output directory (sandbox isolation).
"""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass
from typing import Protocol

from vet_manuscript_lab.domain.conventions import sha256_bytes, utc_now
from vet_manuscript_lab.domain.policies import (
    AnalysisPlanSnapshot,
    AnalysisRunSnapshot,
    AnalysisSpecSnapshot,
    DatasetVersionSnapshot,
    ExecutionContext,
    ExecutionInput,
    require_execution_immutability,
    require_exploratory_marking,
    require_locked_dataset,
    require_locked_plan,
    require_no_approved_result_on_failure,
    require_plan_variables_in_dataset,
)
from vet_manuscript_lab.services.analysis.types import (
    AnalysisClass,
    AnalysisSpec,
    DatasetSpec,
    ResultSpec,
    RunStatus,
)

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunResult:
    """Complete output of a single analysis run.

    Carries the typed results, execution provenance, and status.  When
    ``exit_code != 0`` the ``status`` is ``failed`` and ``results`` is
    empty — the run retains logs but produces no approved result.
    """

    run_id: str
    status: str  # RunStatus value
    exit_code: int
    results: tuple[ResultSpec, ...]
    script_hash: str
    seed: int | None
    package_versions: dict[str, str]
    environment: dict[str, str]
    stdout: str
    stderr: str
    started_at: str
    completed_at: str

    @property
    def has_approved_result(self) -> bool:
        return self.status == RunStatus.COMPLETED.value and len(self.results) > 0

    @property
    def is_exploratory(self) -> bool:
        return all(r.analysis_class == AnalysisClass.EXPLORATORY for r in self.results)


@dataclass(frozen=True, slots=True)
class AnalysisRunResult:
    """Bundles the run result with the plan/dataset hashes for auditing."""

    run: RunResult
    plan_version_id: str
    plan_hash: str
    dataset_version_id: str
    dataset_hash: str


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class StatisticsRunner(Protocol):
    """Protocol every statistics runner must satisfy."""

    def execute(
        self,
        *,
        plan: AnalysisPlanSnapshot,
        dataset: DatasetVersionSnapshot,
        analyses: tuple[AnalysisSpec, ...],
        dataset_spec: DatasetSpec,
        available_variables: frozenset[str],
        run_id: str,
        seed: int | None = None,
    ) -> RunResult:
        """Execute the locked plan against the locked dataset.

        Raises ``PolicyViolation`` if preconditions are not met.
        """
        ...


# ---------------------------------------------------------------------------
# Mock runner (deterministic, offline-safe)
# ---------------------------------------------------------------------------


_DEFAULT_PACKAGES = {
    "python": ".".join(str(v) for v in sys.version_info[:3]),
    "platform": platform.platform(),
    "runner": "mock-statistics-runner-v1",
}


@dataclass(slots=True)
class MockStatisticsRunner:
    """Deterministic mock statistics runner for offline development.

    Produces fixed results derived from the analysis spec names and
    dataset hash so that identical inputs always produce identical
    outputs.  The mock does not perform real statistical computation.

    Set ``fail_on_analysis`` to force a failure when a specific analysis
    name is encountered (for testing failure-handling paths).
    """

    fail_on_analysis: str | None = None

    def execute(
        self,
        *,
        plan: AnalysisPlanSnapshot,
        dataset: DatasetVersionSnapshot,
        analyses: tuple[AnalysisSpec, ...],
        dataset_spec: DatasetSpec,
        available_variables: frozenset[str],
        run_id: str,
        seed: int | None = None,
    ) -> RunResult:
        """Execute analyses deterministically, enforcing all policies."""

        started_at = utc_now()

        # -- Policy preconditions ----------------------------------------
        require_locked_plan(plan)
        require_locked_dataset(dataset)

        exec_input = ExecutionInput(
            plan=plan,
            dataset=dataset,
            requested_variable_names=frozenset(
                name for a in analyses for name in a.variable_names
            ),
        )
        require_plan_variables_in_dataset(
            exec_input, available_variables=available_variables
        )

        # Check exploratory marking for each analysis
        plan_var_set = plan.variable_names
        for analysis in analyses:
            is_in_plan = frozenset(analysis.variable_names).issubset(plan_var_set)
            spec = AnalysisSpecSnapshot(
                name=analysis.name,
                variable_names=frozenset(analysis.variable_names),
                is_exploratory=analysis.analysis_class == AnalysisClass.EXPLORATORY,
                is_in_locked_plan=is_in_plan,
            )
            require_exploratory_marking(spec)

        # Capture execution context for immutability check
        ctx = ExecutionContext(
            plan_hash_at_start=plan.content_hash,
            variable_names_at_start=frozenset(v.name for v in dataset_spec.variables),
            exclusion_criteria_at_start=plan.exclusion_criteria,
            model_specifications_at_start=plan.model_specifications,
        )

        # Verify immutability (trivially true in mock, but exercises the path)
        require_execution_immutability(
            ctx,
            plan_hash_now=plan.content_hash,
            variable_names_now=frozenset(v.name for v in dataset_spec.variables),
            exclusion_criteria_now=plan.exclusion_criteria,
            model_specifications_now=plan.model_specifications,
        )

        # -- Simulated failure -------------------------------------------
        if self.fail_on_analysis is not None:
            for a in analyses:
                if a.name == self.fail_on_analysis:
                    return RunResult(
                        run_id=run_id,
                        status=RunStatus.FAILED.value,
                        exit_code=1,
                        results=(),
                        script_hash=self._script_hash(analyses),
                        seed=seed,
                        package_versions=dict(_DEFAULT_PACKAGES),
                        environment=self._environment(),
                        stdout="",
                        stderr=f"Mock failure triggered for analysis: {a.name}",
                        started_at=started_at,
                        completed_at=utc_now(),
                    )

        # -- Deterministic result generation -----------------------------
        results: list[ResultSpec] = []
        stdout_lines: list[str] = []

        for analysis in analyses:
            result = self._generate_result(analysis, dataset_spec, seed)
            results.append(result)
            stdout_lines.append(
                f"[{analysis.name}] estimand='{analysis.estimand}' "
                f"estimate={result.estimate} method={result.method}"
            )

        run_result = RunResult(
            run_id=run_id,
            status=RunStatus.COMPLETED.value,
            exit_code=0,
            results=tuple(results),
            script_hash=self._script_hash(analyses),
            seed=seed,
            package_versions=dict(_DEFAULT_PACKAGES),
            environment=self._environment(),
            stdout="\n".join(stdout_lines),
            stderr="",
            started_at=started_at,
            completed_at=utc_now(),
        )

        # Verify failure-safety invariant (trivially passes on success)
        require_no_approved_result_on_failure(
            AnalysisRunSnapshot(
                run_id=run_id,
                plan_version_id=plan.version_id,
                plan_hash=plan.content_hash,
                dataset_version_id=dataset.version_id,
                dataset_hash=dataset.content_hash,
                exit_code=run_result.exit_code,
                status=run_result.status,
                has_approved_result=run_result.has_approved_result,
            )
        )

        return run_result

    def _generate_result(
        self,
        analysis: AnalysisSpec,
        dataset: DatasetSpec,
        seed: int | None,
    ) -> ResultSpec:
        """Produce a deterministic result from the analysis spec.

        The estimate is derived from the dataset hash and analysis name
        so it is reproducible but not meaningful.
        """

        source = f"{dataset.content_hash}:{analysis.name}:{analysis.model_type}"
        h = int(sha256_bytes(source.encode()).split(":")[1][:8], 16)
        estimate = (h % 10000) / 100.0  # 0.00 to 99.99
        ci_half = (h % 500) / 100.0 + 0.5
        lower = round(estimate - ci_half, 2)
        upper = round(estimate + ci_half, 2)
        p_val = round((h % 1000) / 1000.0, 3)

        return ResultSpec(
            estimand=analysis.estimand,
            estimate=round(estimate, 2),
            estimate_units=None,
            uncertainty_type="95% CI",
            uncertainty_lower=lower,
            uncertainty_upper=upper,
            p_value=p_val,
            method=f"mock-{analysis.model_type}",
            population=analysis.population,
            analysis_class=analysis.analysis_class,
        )

    @staticmethod
    def _script_hash(analyses: tuple[AnalysisSpec, ...]) -> str:
        """Deterministic hash of the analysis script content."""

        content = json.dumps(
            [
                {
                    "name": a.name,
                    "model": a.model_type,
                    "vars": list(a.variable_names),
                }
                for a in analyses
            ],
            sort_keys=True,
        )
        return sha256_bytes(content.encode())

    @staticmethod
    def _environment() -> dict[str, str]:
        return {
            "python_version": sys.version,
            "platform": platform.platform(),
            "runner_type": "mock",
        }


__all__ = [
    "AnalysisRunResult",
    "MockStatisticsRunner",
    "RunResult",
    "StatisticsRunner",
]
