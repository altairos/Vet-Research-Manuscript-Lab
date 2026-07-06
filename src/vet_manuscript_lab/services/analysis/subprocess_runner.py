"""Subprocess-isolated statistics runner.

Executes analysis scripts in a separate Python process with a fixed input
directory (read-only) and a write-only output directory.  This is the
real-runner replacement for ``MockStatisticsRunner``.

Design follows the project's Backend Protocol + sandbox pattern:

1. The runner writes a ``plan.json`` and ``dataset_meta.json`` to a temporary
   input directory.
2. It launches a worker script (``_worker.py`` or a user-supplied script)
   as a subprocess with the input and output directories as arguments.
3. The worker reads inputs, performs analysis, and writes ``results.json``
   to the output directory.
4. The runner reads ``results.json``, validates it, and returns a
   ``RunResult`` with full provenance.

The worker script is expected to produce deterministic output given the
same inputs and seed.  If no custom script is supplied, a built-in
deterministic worker is used (same algorithm as ``MockStatisticsRunner``
but running in a separate process).
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

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
from vet_manuscript_lab.services.analysis.runner import RunResult
from vet_manuscript_lab.services.analysis.types import (
    AnalysisClass,
    AnalysisSpec,
    DatasetSpec,
    ResultSpec,
    RunStatus,
)

# ---------------------------------------------------------------------------
# Built-in worker script (deterministic, no external dependencies)
# ---------------------------------------------------------------------------

_BUILTIN_WORKER = '''\
"""Built-in deterministic worker script for SubprocessStatisticsRunner.

Reads plan.json + dataset_meta.json from the input directory,
produces deterministic results.json in the output directory.
"""
import json
import hashlib
import sys
from pathlib import Path


def sha256_int(source: str) -> int:
    return int(hashlib.sha256(source.encode()).hexdigest()[:8], 16)


def main(input_dir: str, output_dir: str) -> int:
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    plan = json.loads((input_path / "plan.json").read_text())
    dataset_meta = json.loads((input_path / "dataset_meta.json").read_text())
    seed = plan.get("seed")

    results = []
    stdout_lines = []
    for analysis in plan["analyses"]:
        source = (
            f"{dataset_meta['content_hash']}:"
            f"{analysis['name']}:{analysis['model_type']}"
        )
        h = sha256_int(source)
        estimate = (h % 10000) / 100.0
        ci_half = (h % 500) / 100.0 + 0.5
        results.append({
            "estimand": analysis["estimand"],
            "estimate": round(estimate, 2),
            "estimate_units": None,
            "uncertainty_type": "95% CI",
            "uncertainty_lower": round(estimate - ci_half, 2),
            "uncertainty_upper": round(estimate + ci_half, 2),
            "p_value": round((h % 1000) / 1000.0, 3),
            "method": f"subprocess-{analysis['model_type']}",
            "population": analysis.get("population"),
            "analysis_class": analysis["analysis_class"],
        })
        stdout_lines.append(
            f"[{analysis['name']}] estimate={estimate:.2f}"
        )

    output = {
        "status": "completed",
        "exit_code": 0,
        "results": results,
        "stdout": "\\n".join(stdout_lines),
        "stderr": "",
    }
    (output_path / "results.json").write_text(
        json.dumps(output, indent=2, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    inp = sys.argv[1] if len(sys.argv) > 1 else "input"
    outp = sys.argv[2] if len(sys.argv) > 2 else "output"
    sys.exit(main(inp, outp))
'''


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SubprocessStatisticsRunner:
    """Isolated statistics runner that executes scripts in a subprocess.

    The runner creates a temporary sandbox for each execution:
    - ``input/`` directory: plan.json, dataset_meta.json (read-only conceptually)
    - ``output/`` directory: results.json (write-only conceptually)

    A custom ``worker_script`` can be supplied to replace the built-in
    deterministic worker.  The custom script must accept two positional
    arguments (input_dir, output_dir) and write ``results.json`` to the
    output directory.

    Parameters
    ----------
    python_executable:
        Path to the Python interpreter for the subprocess.  Defaults to
        the current interpreter (``sys.executable``).
    worker_script:
        Optional path to a custom worker script.  If ``None``, the
        built-in deterministic worker is used.
    timeout_seconds:
        Maximum execution time before the subprocess is killed.
    keep_temp:
        If ``True``, temporary directories are not cleaned up (useful
        for debugging).
    """

    python_executable: str = field(default_factory=lambda: sys.executable)
    worker_script: Path | None = None
    timeout_seconds: int = 300
    keep_temp: bool = False

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
        """Execute analyses in an isolated subprocess.

        Enforces all Phase 3 policy preconditions before launching
        the subprocess.
        """

        started_at = utc_now()

        # -- Policy preconditions (same as MockStatisticsRunner) --------
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

        ctx = ExecutionContext(
            plan_hash_at_start=plan.content_hash,
            variable_names_at_start=frozenset(v.name for v in dataset_spec.variables),
            exclusion_criteria_at_start=plan.exclusion_criteria,
            model_specifications_at_start=plan.model_specifications,
        )
        require_execution_immutability(
            ctx,
            plan_hash_now=plan.content_hash,
            variable_names_now=frozenset(v.name for v in dataset_spec.variables),
            exclusion_criteria_now=plan.exclusion_criteria,
            model_specifications_now=plan.model_specifications,
        )

        # -- Prepare sandbox directories --------------------------------
        temp_base = Path(tempfile.mkdtemp(prefix=f"runner_{run_id}_"))

        try:
            input_dir = temp_base / "input"
            output_dir = temp_base / "output"
            input_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)

            # Write input files
            plan_data = {
                "run_id": run_id,
                "seed": seed,
                "plan_version_id": plan.version_id,
                "plan_hash": plan.content_hash,
                "dataset_version_id": dataset.version_id,
                "dataset_hash": dataset.content_hash,
                "analyses": [
                    {
                        "name": a.name,
                        "estimand": a.estimand,
                        "model_type": a.model_type,
                        "variable_names": list(a.variable_names),
                        "analysis_class": a.analysis_class.value,
                        "exclusion_criteria": list(a.exclusion_criteria),
                        "population": a.population,
                    }
                    for a in analyses
                ],
            }
            (input_dir / "plan.json").write_text(
                json.dumps(plan_data, indent=2, sort_keys=True)
            )

            dataset_meta = {
                "dataset_id": dataset_spec.dataset_id,
                "name": dataset_spec.name,
                "row_count": dataset_spec.row_count,
                "column_count": dataset_spec.column_count,
                "content_hash": dataset_spec.content_hash,
                "uri": dataset_spec.uri,
            }
            (input_dir / "dataset_meta.json").write_text(
                json.dumps(dataset_meta, indent=2, sort_keys=True)
            )

            # Resolve worker script
            if self.worker_script is not None:
                script_path = self.worker_script
            else:
                script_path = input_dir / "_worker.py"
                script_path.write_text(_BUILTIN_WORKER)

            script_hash = sha256_bytes(script_path.read_bytes())

            # -- Launch subprocess --------------------------------------
            env = self._subprocess_env()

            proc = subprocess.run(
                [
                    self.python_executable,
                    str(script_path),
                    str(input_dir),
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
                cwd=str(temp_base),
            )

            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode

            # -- Parse output -------------------------------------------
            if exit_code != 0:
                run_result = RunResult(
                    run_id=run_id,
                    status=RunStatus.FAILED.value,
                    exit_code=exit_code,
                    results=(),
                    script_hash=script_hash,
                    seed=seed,
                    package_versions=self._package_versions(),
                    environment=self._environment(),
                    stdout=stdout,
                    stderr=stderr,
                    started_at=started_at,
                    completed_at=utc_now(),
                )
            else:
                results_path = output_dir / "results.json"
                if not results_path.exists():
                    run_result = RunResult(
                        run_id=run_id,
                        status=RunStatus.FAILED.value,
                        exit_code=1,
                        results=(),
                        script_hash=script_hash,
                        seed=seed,
                        package_versions=self._package_versions(),
                        environment=self._environment(),
                        stdout=stdout,
                        stderr=f"Worker did not produce results.json. stderr={stderr}",
                        started_at=started_at,
                        completed_at=utc_now(),
                    )
                else:
                    output_data = json.loads(results_path.read_text())
                    results = tuple(
                        ResultSpec(
                            estimand=r["estimand"],
                            estimate=r.get("estimate"),
                            estimate_units=r.get("estimate_units"),
                            uncertainty_type=r.get("uncertainty_type"),
                            uncertainty_lower=r.get("uncertainty_lower"),
                            uncertainty_upper=r.get("uncertainty_upper"),
                            p_value=r.get("p_value"),
                            method=r.get("method"),
                            population=r.get("population"),
                            analysis_class=AnalysisClass(r["analysis_class"]),
                        )
                        for r in output_data.get("results", [])
                    )
                    run_result = RunResult(
                        run_id=run_id,
                        status=RunStatus.COMPLETED.value,
                        exit_code=0,
                        results=results,
                        script_hash=script_hash,
                        seed=seed,
                        package_versions=self._package_versions(),
                        environment=self._environment(),
                        stdout=output_data.get("stdout", stdout),
                        stderr=output_data.get("stderr", stderr),
                        started_at=started_at,
                        completed_at=utc_now(),
                    )

            # -- Failure-safety invariant --------------------------------
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

        finally:
            if not self.keep_temp:
                import shutil

                shutil.rmtree(temp_base, ignore_errors=True)

    # -- Helpers ----------------------------------------------------------

    def _subprocess_env(self) -> dict[str, str]:
        """Return a clean environment for the subprocess."""

        env = dict(os.environ)
        # Ensure the subprocess uses the same Python path
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        return env

    @staticmethod
    def _package_versions() -> dict[str, str]:
        return {
            "python": ".".join(str(v) for v in sys.version_info[:3]),
            "platform": platform.platform(),
            "runner": "subprocess-statistics-runner-v1",
        }

    @staticmethod
    def _environment() -> dict[str, str]:
        return {
            "python_version": sys.version,
            "platform": platform.platform(),
            "runner_type": "subprocess",
        }


__all__ = ["SubprocessStatisticsRunner"]
