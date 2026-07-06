"""Methodology and statistics pipeline extending the Evidence graph.

Implements the ``METHODOLOGY_CRITIC -> ANALYSIS_PLAN_APPROVAL ->
ANALYSIS_PLAN_LOCK -> STATISTICS_EXECUTION -> RESULTS_APPROVAL`` vertical
slice.  Every policy invariant (locked dataset + locked plan preconditions,
exploratory marking, execution immutability, failure safety) is enforced
inside the nodes.

The Methodology Critic routes through the Model Gateway
(``TaskKind.METHODOLOGY_CRITIC``) to produce structured findings.  When
no gateway is supplied, a deterministic mock findings generator is used
so the pipeline remains runnable in offline development.

The statistics runner is injected via ``StatisticsRunner`` Protocol.
When ``None``, the deterministic ``MockStatisticsRunner`` is used.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from vet_manuscript_lab.domain.conventions import sha256_bytes, utc_now
from vet_manuscript_lab.domain.policies import (
    AnalysisPlanSnapshot,
    DatasetVersionSnapshot,
    PolicyViolation,
)
from vet_manuscript_lab.infrastructure.model_gateway.gateway import (
    GatewayResult,
    ModelGateway,
)
from vet_manuscript_lab.infrastructure.model_gateway.types import (
    AgentTaskSpec,
    TaskKind,
)
from vet_manuscript_lab.services.analysis.runner import (
    MockStatisticsRunner,
    RunResult,
    StatisticsRunner,
)
from vet_manuscript_lab.services.analysis.types import (
    AnalysisClass,
    AnalysisSpec,
    RunStatus,
    VariableRole,
    VariableSpec,
    VariableType,
)
from vet_manuscript_lab.workflow.foundation_graph import (
    _DECISIONS,
    _event,
    _parse_resume,
    _stable_id,
    guideline_mapping_node,
    project_init_node,
    protocol_approval_node,
    protocol_lock_node,
    question_approval_node,
    research_question_node,
    route_protocol_decision,
    route_question_decision,
)
from vet_manuscript_lab.workflow.literature_graph import (
    _make_artifact,
    evidence_audit_node,
    evidence_extraction_node,
    literature_search_node,
    route_search_decision,
    screening_node,
    search_approval_node,
)
from vet_manuscript_lab.workflow.state import (
    AnalysisPlanSummary,
    AnalysisRunSummary,
    AnalysisSpecDraft,
    DatasetSummary,
    LockRef,
    MethodologyFinding,
    ResultDraft,
    VariableSpecDraft,
    WorkflowStage,
    WorkflowState,
    require_approved_gate,
)
from vet_manuscript_lab.workflow.state import (
    RunStatus as WorkflowRunStatus,
)

# ---------------------------------------------------------------------------
# AI usage tracking helpers
# ---------------------------------------------------------------------------


def _extract_usage(
    gateway: ModelGateway | None,
) -> dict[str, Any]:
    """Extract a compact usage summary from the gateway if available."""

    if gateway is None:
        return {}
    log = gateway.usage_log
    return {
        "ai_usage": {
            "total_invocations": len(log.invocations),
            "total_cost_cents": log.total_cost_cents,
            "total_input_tokens": log.total_input_tokens,
            "total_output_tokens": log.total_output_tokens,
            "fallback_count": log.fallback_count,
            "failure_count": log.failure_count,
            "cost_by_stage": log.cost_report_by_stage(),
        }
    }


# ---------------------------------------------------------------------------
# Mock data generators (offline fallback)
# ---------------------------------------------------------------------------


def _mock_variable_specs() -> list[VariableSpecDraft]:
    """Deterministic fixture variables for a canine/feline clinical study."""

    return [
        VariableSpecDraft(
            name="case_id",
            var_type=VariableType.CATEGORICAL.value,
            role=VariableRole.ID.value,
            unit=None,
            missing_code=None,
        ),
        VariableSpecDraft(
            name="species",
            var_type=VariableType.CATEGORICAL.value,
            role=VariableRole.COVARIATE.value,
            unit=None,
            missing_code="unknown",
        ),
        VariableSpecDraft(
            name="age_years",
            var_type=VariableType.CONTINUOUS.value,
            role=VariableRole.COVARIATE.value,
            unit="years",
            missing_code="NA",
        ),
        VariableSpecDraft(
            name="treatment_group",
            var_type=VariableType.BINARY.value,
            role=VariableRole.EXPOSURE.value,
            unit=None,
            missing_code=None,
        ),
        VariableSpecDraft(
            name="survival_months",
            var_type=VariableType.CONTINUOUS.value,
            role=VariableRole.OUTCOME.value,
            unit="months",
            missing_code="NA",
        ),
    ]


def _mock_analysis_specs() -> list[AnalysisSpecDraft]:
    """Deterministic fixture analyses for the mock pipeline."""

    return [
        AnalysisSpecDraft(
            name="primary_survival",
            estimand="Median survival time difference",
            model_type="log_rank",
            variable_names=["survival_months", "treatment_group", "age_years"],
            analysis_class=AnalysisClass.PRIMARY.value,
            exclusion_criteria=["Exclude cases with < 7 days follow-up"],
            population="All enrolled canine/feline cases",
        ),
        AnalysisSpecDraft(
            name="age_adjusted",
            estimand="Age-adjusted treatment effect",
            model_type="cox",
            variable_names=[
                "survival_months",
                "treatment_group",
                "age_years",
                "species",
            ],
            analysis_class=AnalysisClass.SECONDARY.value,
            exclusion_criteria=[],
            population="All enrolled canine/feline cases",
        ),
    ]


def _mock_methodology_findings(state: WorkflowState) -> list[MethodologyFinding]:
    """Deterministic fixture findings for the mock Methodology Critic."""

    project = state["project_id"]
    return [
        MethodologyFinding(
            finding_id=_stable_id(project, "finding", "confounders"),
            category="confounding",
            severity="warning",
            rationale=(
                "Age distribution differs between treatment groups; "
                "consider age-adjusted models."
            ),
            recommendation="Include age_years as a covariate in survival models.",
            status="open",
        ),
        MethodologyFinding(
            finding_id=_stable_id(project, "finding", "missing_data"),
            category="missing_data",
            severity="info",
            rationale="Missing data pattern should be documented.",
            recommendation="Report missingness rates per variable in results.",
            status="open",
        ),
    ]


def _mock_dataset_summary(state: WorkflowState) -> DatasetSummary:
    """Deterministic fixture dataset for offline mode."""

    project = state["project_id"]
    dataset_id = _stable_id(project, "dataset")
    content = json.dumps({"project": project, "mock": True}, sort_keys=True).encode()
    return DatasetSummary(
        dataset_id=dataset_id,
        dataset_version_id=_stable_id(dataset_id, "v1"),
        name="Mock canine/feline clinical dataset",
        row_count=150,
        variable_count=5,
        content_hash=sha256_bytes(content),
        locked=False,
    )


# ---------------------------------------------------------------------------
# Stage nodes
# ---------------------------------------------------------------------------


def _parse_gateway_findings(
    text: str,
    project_id: str,
    invocation_id: str,
) -> list[MethodologyFinding]:
    """Parse structured findings from gateway output.

    The gateway is prompted to return JSON of the form::

        {"findings": [{"category": ..., "severity": ..., "rationale": ...,
                        "recommendation": ...}, ...]}

    If JSON parsing fails the raw text is wrapped as a single
    unstructured finding so the pipeline never crashes on malformed LLM
    output.
    """

    import json as _json

    valid_severities = {"info", "warning", "error"}
    valid_categories = {
        "confounding",
        "missing_data",
        "selection_bias",
        "measurement_bias",
        "sample_size",
        "population_heterogeneity",
        "model_assumptions",
        "multiplicity",
        "other",
    }

    try:
        data = _json.loads(text)
        raw_findings = data.get("findings", [])
    except (ValueError, TypeError):
        raw_findings = []

    findings: list[MethodologyFinding] = []
    for i, rf in enumerate(raw_findings):
        if not isinstance(rf, dict):
            continue
        severity = str(rf.get("severity", "info")).lower()
        if severity not in valid_severities:
            severity = "info"
        category = str(rf.get("category", "other")).lower()
        if category not in valid_categories:
            category = "other"
        findings.append(
            MethodologyFinding(
                finding_id=_stable_id(
                    project_id, "finding", "gateway", invocation_id, str(i)
                ),
                category=category,
                severity=severity,
                rationale=str(rf.get("rationale", "")),
                recommendation=str(rf.get("recommendation", "")),
                status="open",
            )
        )

    if not findings:
        findings.append(
            MethodologyFinding(
                finding_id=_stable_id(project_id, "finding", "gateway", invocation_id),
                category="other",
                severity="info",
                rationale=text[:500] if text else "Gateway returned no output.",
                recommendation="Review gateway output and address findings manually.",
                status="open",
            )
        )
    return findings


def methodology_critic_node(
    state: WorkflowState,
    *,
    gateway: ModelGateway | None = None,
) -> dict[str, Any]:
    """Produce structured methodology findings via the Model Gateway.

    When a ``gateway`` is supplied the critic routes through the
    ``METHODOLOGY_CRITIC`` task kind.  The gateway is prompted to return
    structured JSON findings; if parsing fails the raw text is wrapped
    as a single unstructured finding.

    Otherwise deterministic mock findings are generated so the pipeline
    remains runnable offline.
    """

    evidence = state.get("evidence_summary")
    if evidence is None:
        raise PolicyViolation("Methodology Critic requires completed evidence audit")

    if gateway is not None:
        spec = AgentTaskSpec(
            task_kind=TaskKind.METHODOLOGY_CRITIC,
            estimated_input_tokens=2000,
            estimated_output_tokens=1000,
            risk_level=2,
            project_id=state["project_id"],
            run_id=state["workflow_run_id"],
            stage=WorkflowStage.METHODOLOGY_CRITIC.value,
        )
        prompt = (
            "Review the study methodology and return structured findings as JSON. "
            "Categories: confounding, missing_data, selection_bias, "
            "measurement_bias, sample_size, population_heterogeneity, "
            "model_assumptions, multiplicity, other. "
            "Severities: info, warning, error. "
            'Format: {"findings": [{"category": "...", '
            '"severity": "...", "rationale": "...", '
            '"recommendation": "..."}]}'
        )
        result: GatewayResult = gateway.invoke(spec, prompt=prompt)
        findings = _parse_gateway_findings(
            result.text,
            state["project_id"],
            result.invocation.invocation_id,
        )
    else:
        findings = _mock_methodology_findings(state)

    findings_artifact = _make_artifact(
        state,
        role="methodology_findings",
        artifact_type="methodology_findings",
        gate="analysis_plan",
        payload={
            "findings": [
                {
                    "finding_id": f["finding_id"],
                    "category": f.get("category", ""),
                    "severity": f.get("severity", ""),
                    "rationale": f.get("rationale", ""),
                    "recommendation": f.get("recommendation", ""),
                    "status": f.get("status", "open"),
                }
                for f in findings
            ],
            "total_findings": len(findings),
            "source": "model_gateway" if gateway is not None else "mock",
        },
    )
    artifacts = dict(state.get("artifacts", {}))
    artifacts["methodology_findings"] = findings_artifact

    return {
        "artifacts": artifacts,
        "methodology_findings": findings,
        "current_stage": WorkflowStage.METHODOLOGY_CRITIC.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(
                state,
                "methodology.critic_completed",
                WorkflowStage.METHODOLOGY_CRITIC,
            )
        ],
        **_extract_usage(gateway),
    }


def analysis_plan_node(state: WorkflowState) -> dict[str, Any]:
    """Generate an analysis plan draft based on methodology findings.

    The plan references variables from the dataset dictionary and
    incorporates recommendations from the Methodology Critic.
    """

    findings = state.get("methodology_findings", [])

    # Generate or reuse variable specs
    variables = state.get("variable_spec_drafts") or _mock_variable_specs()

    # Generate analysis specs
    analyses = state.get("analysis_spec_drafts") or _mock_analysis_specs()

    # Dataset summary (used for locking)
    dataset_summary = state.get("dataset_summary") or _mock_dataset_summary(state)

    artifacts = state.get("artifacts", {})
    methodology_artifact = artifacts.get("methodology_findings")
    protocol_artifact = artifacts.get("protocol")
    plan_content = {
        "version": 1,
        "methodology_version_id": methodology_artifact.get("version_id")
        if methodology_artifact
        else None,
        "protocol_version_id": protocol_artifact.get("version_id")
        if protocol_artifact
        else None,
        "dataset_version_id": dataset_summary.get("dataset_version_id", ""),
        "dataset_hash": dataset_summary.get("content_hash", ""),
        "is_exploratory": False,
        "variables": [
            {
                "name": v["name"],
                "var_type": v.get("var_type", ""),
                "role": v.get("role", ""),
                "unit": v.get("unit"),
                "missing_code": v.get("missing_code"),
            }
            for v in variables
        ],
        "analyses": [
            {
                "name": a["name"],
                "estimand": a.get("estimand", ""),
                "model_type": a.get("model_type", ""),
                "variable_names": a.get("variable_names", []),
                "analysis_class": a.get("analysis_class", "primary"),
                "exclusion_criteria": a.get("exclusion_criteria", []),
                "population": a.get("population"),
            }
            for a in analyses
        ],
        "methodology_findings_addressed": len(findings),
    }

    plan_artifact = _make_artifact(
        state,
        role="analysis_plan",
        artifact_type="analysis_plan",
        gate="analysis_plan",
        payload=plan_content,
    )
    artifacts = dict(state.get("artifacts", {}))
    artifacts["analysis_plan"] = plan_artifact

    plan_summary: AnalysisPlanSummary = {
        "plan_version_id": plan_artifact["version_id"],
        "content_hash": plan_artifact["content_hash"],
        "version": plan_artifact["version"],
        "is_exploratory": False,
        "locked": False,
        "findings_count": len(findings),
        "analysis_count": len(analyses),
    }

    return {
        "artifacts": artifacts,
        "variable_spec_drafts": variables,
        "analysis_spec_drafts": analyses,
        "dataset_summary": dataset_summary,
        "analysis_plan_summary": plan_summary,
        "current_stage": WorkflowStage.METHODOLOGY_CRITIC.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(state, "analysis_plan.drafted", WorkflowStage.METHODOLOGY_CRITIC)
        ],
    }


def analysis_plan_approval_node(state: WorkflowState) -> dict[str, Any]:
    """Interrupt for human approval of the analysis plan."""

    subject = state["artifacts"]["analysis_plan"]
    resume = interrupt(
        {
            "gate": "analysis_plan",
            "subject_id": subject["artifact_id"],
            "subject_version_id": subject["version_id"],
            "subject_hash": subject["content_hash"],
            "title": "Approve analysis plan and dataset lock",
            "summary": "Review analyses, variable mappings, models, and "
            "exclusion criteria before locking the plan and dataset.",
            "proposed_next_stage": WorkflowStage.ANALYSIS_PLAN_LOCK.value,
            "allowed_decisions": sorted(_DECISIONS),
            "required_reviewer_role": "investigator",
            "warning_codes": ["PLAN_AND_DATASET_WILL_BE_LOCKED"],
        }
    )
    approval = _parse_resume(resume, gate="analysis_plan", subject=subject)
    approvals = dict(state.get("approvals", {}))
    approvals["analysis_plan"] = approval
    return {
        "approvals": approvals,
        "current_stage": WorkflowStage.ANALYSIS_PLAN_APPROVAL.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(
                state,
                "analysis_plan.reviewed",
                WorkflowStage.ANALYSIS_PLAN_APPROVAL,
            )
        ],
    }


def route_analysis_plan_decision(state: WorkflowState) -> str:
    decision = state["approvals"]["analysis_plan"]["decision"]
    return "analysis_plan_lock" if decision == "approved" else "methodology_critic"


def analysis_plan_lock_node(state: WorkflowState) -> dict[str, Any]:
    """Lock the analysis plan and dataset version.

    Creates two LockRef entries (``analysis_plan`` and ``dataset``) and
    marks the corresponding artifacts as locked.  After this point the
    plan's models, variables, and exclusion criteria are immutable.
    """

    approval = require_approved_gate(state, "analysis_plan")
    plan = state["artifacts"]["analysis_plan"]
    dataset_summary = state.get("dataset_summary")
    if dataset_summary is None:
        raise PolicyViolation("Dataset summary is missing — cannot lock")

    if approval["subject_version_id"] != plan["version_id"]:
        raise PermissionError("Analysis plan approval belongs to another version")
    if approval["subject_hash"] != plan["content_hash"]:
        raise PermissionError("Analysis plan approval hash is stale")

    plan_lock: LockRef = {
        "lock_id": _stable_id("plan_lock", plan["version_id"]),
        "lock_type": "analysis_plan",
        "subject_id": plan["artifact_id"],
        "subject_version_id": plan["version_id"],
        "subject_hash": plan["content_hash"],
        "approval_id": approval["approval_id"],
        "locked_by": approval["reviewer_id"],
        "locked_at": utc_now(),
    }

    dataset_lock: LockRef = {
        "lock_id": _stable_id("dataset_lock", dataset_summary["dataset_version_id"]),
        "lock_type": "dataset",
        "subject_id": dataset_summary["dataset_id"],
        "subject_version_id": dataset_summary["dataset_version_id"],
        "subject_hash": dataset_summary["content_hash"],
        "approval_id": approval["approval_id"],
        "locked_by": approval["reviewer_id"],
        "locked_at": utc_now(),
    }

    locks = dict(state.get("locks", {}))
    locks["analysis_plan"] = plan_lock
    locks["dataset"] = dataset_lock

    artifacts = dict(state["artifacts"])
    artifacts["analysis_plan"] = {**plan, "status": "locked"}

    locked_dataset: DatasetSummary = {**dataset_summary, "locked": True}

    plan_summary: AnalysisPlanSummary = {
        **(
            state.get("analysis_plan_summary")
            or {
                "plan_version_id": "",
                "content_hash": "",
                "version": 0,
                "is_exploratory": False,
                "locked": False,
                "findings_count": 0,
                "analysis_count": 0,
            }
        ),
        "locked": True,
    }

    return {
        "locks": locks,
        "artifacts": artifacts,
        "dataset_summary": locked_dataset,
        "analysis_plan_summary": plan_summary,
        "current_stage": WorkflowStage.ANALYSIS_PLAN_LOCK.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(state, "analysis_plan.locked", WorkflowStage.ANALYSIS_PLAN_LOCK)
        ],
    }


def _build_plan_snapshot(state: WorkflowState) -> AnalysisPlanSnapshot:
    """Build an AnalysisPlanSnapshot from the locked plan + dataset."""

    plan = state["artifacts"]["analysis_plan"]
    raw_plan_summary = state.get("analysis_plan_summary")
    variables = state.get("variable_spec_drafts", [])
    analyses = state.get("analysis_spec_drafts", [])

    return AnalysisPlanSnapshot(
        version_id=plan["version_id"],
        content_hash=plan["content_hash"],
        status=plan["status"],
        is_exploratory=raw_plan_summary.get("is_exploratory", False)
        if raw_plan_summary
        else False,
        variable_names=frozenset(v["name"] for v in variables),
        model_specifications=tuple(a.get("model_type", "") for a in analyses),
        exclusion_criteria=tuple(
            crit for a in analyses for crit in a.get("exclusion_criteria", [])
        ),
    )


def _build_dataset_snapshot(state: WorkflowState) -> DatasetVersionSnapshot:
    """Build a DatasetVersionSnapshot from the locked dataset."""

    ds = state["dataset_summary"]
    if ds is None:
        raise PolicyViolation("Dataset summary is missing")
    return DatasetVersionSnapshot(
        version_id=ds["dataset_version_id"],
        content_hash=ds["content_hash"],
        status="locked" if ds.get("locked") else "draft",
    )


def _build_analysis_specs(state: WorkflowState) -> tuple[AnalysisSpec, ...]:
    """Convert AnalysisSpecDraft list to AnalysisSpec dataclasses."""

    drafts = state.get("analysis_spec_drafts", [])
    specs: list[AnalysisSpec] = []
    for d in drafts:
        specs.append(
            AnalysisSpec(
                name=d["name"],
                estimand=d.get("estimand", ""),
                model_type=d.get("model_type", ""),
                variable_names=tuple(d.get("variable_names", [])),
                analysis_class=AnalysisClass(d.get("analysis_class", "primary")),
                exclusion_criteria=tuple(d.get("exclusion_criteria", [])),
                population=d.get("population"),
            )
        )
    return tuple(specs)


def statistics_execution_node(
    state: WorkflowState,
    *,
    runner: StatisticsRunner | None = None,
) -> dict[str, Any]:
    """Execute the locked analysis plan against the locked dataset.

    Enforces all Phase 3 preconditions via the injected runner:
    locked plan + locked dataset, valid variables, exploratory marking,
    and execution immutability.  Records full provenance including
    script hash, seed, package versions, and stdout/stderr.
    """

    plan_snapshot = _build_plan_snapshot(state)
    dataset_snapshot = _build_dataset_snapshot(state)
    analyses = _build_analysis_specs(state)

    variables = state.get("variable_spec_drafts", [])
    available_variables = frozenset(v["name"] for v in variables)

    # Build DatasetSpec for the runner
    from vet_manuscript_lab.services.analysis.types import DatasetSpec

    ds_summary = state.get("dataset_summary")
    if ds_summary is None:
        raise PolicyViolation("Dataset summary is missing")
    dataset_spec = DatasetSpec(
        dataset_id=ds_summary["dataset_id"],
        name=ds_summary.get("name", ""),
        row_count=ds_summary.get("row_count", 0),
        column_count=ds_summary.get("variable_count", 0),
        content_hash=ds_summary["content_hash"],
        uri=f"mock://{ds_summary['dataset_id']}",
        media_type="application/json",
        variables=tuple(
            VariableSpec(
                name=v["name"],
                var_type=VariableType(v.get("var_type", "continuous")),
                role=VariableRole(v.get("role", "covariate")),
                unit=v.get("unit"),
                missing_code=v.get("missing_code"),
            )
            for v in variables
        ),
    )

    actual_runner = runner or MockStatisticsRunner()
    run_id = _stable_id(state["project_id"], "analysis_run")

    run_result: RunResult = actual_runner.execute(
        plan=plan_snapshot,
        dataset=dataset_snapshot,
        analyses=analyses,
        dataset_spec=dataset_spec,
        available_variables=available_variables,
        run_id=run_id,
        seed=42,
    )

    # Convert results to drafts
    result_drafts: list[ResultDraft] = []
    for i, r in enumerate(run_result.results):
        result_drafts.append(
            ResultDraft(
                result_id=_stable_id(run_id, "result", str(i)),
                estimand=r.estimand,
                estimate=r.estimate,
                estimate_units=r.estimate_units,
                uncertainty_type=r.uncertainty_type,
                uncertainty_lower=r.uncertainty_lower,
                uncertainty_upper=r.uncertainty_upper,
                p_value=r.p_value,
                method=r.method,
                population=r.population,
                analysis_class=r.analysis_class.value,
            )
        )

    results_artifact = _make_artifact(
        state,
        role="analysis_results",
        artifact_type="analysis_result",
        gate="analysis_plan",
        payload={
            "run_id": run_id,
            "run_status": run_result.status,
            "exit_code": run_result.exit_code,
            "script_hash": run_result.script_hash,
            "seed": run_result.seed,
            "plan_version_id": plan_snapshot.version_id,
            "plan_hash": plan_snapshot.content_hash,
            "dataset_version_id": dataset_snapshot.version_id,
            "dataset_hash": dataset_snapshot.content_hash,
            "package_versions": run_result.package_versions,
            "environment": run_result.environment,
            "results": [
                {
                    "result_id": rd["result_id"],
                    "estimand": rd["estimand"],
                    "estimate": rd["estimate"],
                    "uncertainty_lower": rd["uncertainty_lower"],
                    "uncertainty_upper": rd["uncertainty_upper"],
                    "p_value": rd["p_value"],
                    "method": rd["method"],
                    "analysis_class": rd["analysis_class"],
                }
                for rd in result_drafts
            ],
            "stdout": run_result.stdout,
            "stderr": run_result.stderr,
        },
    )
    artifacts = dict(state.get("artifacts", {}))
    artifacts["analysis_results"] = results_artifact

    run_summary: AnalysisRunSummary = {
        "run_id": run_id,
        "status": run_result.status,
        "result_count": len(result_drafts),
        "is_reproducible": run_result.status == RunStatus.COMPLETED.value,
        "exit_code": run_result.exit_code,
    }

    # On failure, don't proceed to results approval
    new_status = (
        WorkflowRunStatus.RUNNING.value
        if run_result.status == RunStatus.COMPLETED.value
        else WorkflowRunStatus.FAILED.value
    )

    return {
        "artifacts": artifacts,
        "result_drafts": result_drafts,
        "analysis_run_summary": run_summary,
        "current_stage": WorkflowStage.STATISTICS_EXECUTION.value,
        "run_status": new_status,
        "updated_at": utc_now(),
        "audit_events": [
            _event(state, "statistics.executed", WorkflowStage.STATISTICS_EXECUTION)
        ],
    }


def results_approval_node(state: WorkflowState) -> dict[str, Any]:
    """Interrupt for human review of statistical results.

    On approval the pipeline continues to the writing stage.  On
    rejection it returns to statistics execution for re-running.
    """

    subject = state["artifacts"]["analysis_results"]
    resume = interrupt(
        {
            "gate": "results_interpretation",
            "subject_id": subject["artifact_id"],
            "subject_version_id": subject["version_id"],
            "subject_hash": subject["content_hash"],
            "title": "Review statistical results",
            "summary": "Review estimates, confidence intervals, and p-values "
            "before proceeding to manuscript writing.",
            "proposed_next_stage": WorkflowStage.WRITING.value,
            "allowed_decisions": sorted(_DECISIONS),
            "required_reviewer_role": "investigator",
            "warning_codes": [],
        }
    )
    approval = _parse_resume(resume, gate="results_interpretation", subject=subject)
    approvals = dict(state.get("approvals", {}))
    approvals["results_interpretation"] = approval
    return {
        "approvals": approvals,
        "current_stage": WorkflowStage.RESULTS_APPROVAL.value,
        "run_status": WorkflowRunStatus.COMPLETE.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(state, "results.reviewed", WorkflowStage.RESULTS_APPROVAL)
        ],
    }


def route_results_decision(state: WorkflowState) -> str:
    decision = state["approvals"]["results_interpretation"]["decision"]
    return END if decision == "approved" else "statistics_execution"


# ---------------------------------------------------------------------------
# Wrapper for evidence_audit to keep running
# ---------------------------------------------------------------------------


def _evidence_audit_running(state: WorkflowState) -> dict[str, Any]:
    """Evidence audit that keeps the run active for analysis stages."""

    result = evidence_audit_node(state)
    result["run_status"] = WorkflowRunStatus.RUNNING.value
    return result


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AnalysisPipeline:
    """Optional injection point for analysis-stage dependencies."""

    gateway: ModelGateway | None = None
    runner: StatisticsRunner | None = None


def build_analysis_pipeline_graph(
    checkpointer: BaseCheckpointSaver[Any],
    *,
    synchroniser: Any = None,
    evidence_pipeline: Any = None,
    analysis_pipeline: AnalysisPipeline | None = None,
) -> Any:
    """Compile the full pipeline from ``PROJECT_INIT`` to ``RESULTS_APPROVAL``.

    Extends the evidence pipeline graph with the methodology and
    statistics stages.  The foundation and literature stages are reused
    unchanged.

    Parameters
    ----------
    checkpointer : LangGraph checkpoint saver
    synchroniser : optional ZoteroSynchroniser (passed to evidence pipeline)
    evidence_pipeline : optional EvidencePipeline (passed to evidence pipeline)
    analysis_pipeline : optional AnalysisPipeline bundling gateway + runner
    """

    gateway = analysis_pipeline.gateway if analysis_pipeline else None
    runner = analysis_pipeline.runner if analysis_pipeline else None

    builder = StateGraph(WorkflowState)

    # Foundation stage (reused)
    builder.add_node("project_init", project_init_node)
    builder.add_node("research_question", research_question_node)
    builder.add_node("question_approval", question_approval_node)
    builder.add_node("guideline_mapping", guideline_mapping_node)
    builder.add_node("protocol_approval", protocol_approval_node)
    builder.add_node("protocol_lock", _protocol_lock_running)

    # Literature + evidence stage (reused)
    builder.add_node(
        "literature_search",
        literature_search_node
        if synchroniser is None
        else lambda s: literature_search_node(s, synchroniser=synchroniser),
    )
    builder.add_node("search_approval", search_approval_node)
    builder.add_node("screening", screening_node)
    builder.add_node(
        "evidence_extraction",
        evidence_extraction_node
        if evidence_pipeline is None
        else lambda s: evidence_extraction_node(s, pipeline=evidence_pipeline),
    )
    builder.add_node("evidence_audit", _evidence_audit_running)

    # Methodology + statistics stage (new)
    builder.add_node(
        "methodology_critic",
        methodology_critic_node
        if gateway is None
        else lambda s: methodology_critic_node(s, gateway=gateway),
    )
    builder.add_node("analysis_plan", analysis_plan_node)
    builder.add_node("analysis_plan_approval", analysis_plan_approval_node)
    builder.add_node("analysis_plan_lock", analysis_plan_lock_node)
    builder.add_node(
        "statistics_execution",
        statistics_execution_node
        if runner is None
        else lambda s: statistics_execution_node(s, runner=runner),
    )
    builder.add_node("results_approval", results_approval_node)

    # Edges: foundation
    builder.add_edge(START, "project_init")
    builder.add_edge("project_init", "research_question")
    builder.add_edge("research_question", "question_approval")
    builder.add_conditional_edges("question_approval", route_question_decision)
    builder.add_edge("guideline_mapping", "protocol_approval")
    builder.add_conditional_edges("protocol_approval", route_protocol_decision)

    # Edges: literature + evidence
    builder.add_edge("protocol_lock", "literature_search")
    builder.add_edge("literature_search", "search_approval")
    builder.add_conditional_edges("search_approval", route_search_decision)
    builder.add_edge("screening", "evidence_extraction")
    builder.add_edge("evidence_extraction", "evidence_audit")

    # Edges: methodology + statistics
    builder.add_edge("evidence_audit", "methodology_critic")
    builder.add_edge("methodology_critic", "analysis_plan")
    builder.add_edge("analysis_plan", "analysis_plan_approval")
    builder.add_conditional_edges(
        "analysis_plan_approval", route_analysis_plan_decision
    )
    builder.add_edge("analysis_plan_lock", "statistics_execution")
    builder.add_edge("statistics_execution", "results_approval")
    builder.add_conditional_edges("results_approval", route_results_decision)

    return builder.compile(checkpointer=checkpointer)


def _protocol_lock_running(state: WorkflowState) -> dict[str, Any]:
    """Protocol lock wrapper that keeps the run active."""

    result = protocol_lock_node(state)
    result["run_status"] = WorkflowRunStatus.RUNNING.value
    return result


__all__ = [
    "AnalysisPipeline",
    "analysis_plan_approval_node",
    "analysis_plan_lock_node",
    "analysis_plan_node",
    "build_analysis_pipeline_graph",
    "methodology_critic_node",
    "results_approval_node",
    "route_analysis_plan_decision",
    "route_results_decision",
    "statistics_execution_node",
]
