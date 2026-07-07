"""Strictly serializable workflow state and deterministic transition rules."""

from __future__ import annotations

import json
import operator
from enum import StrEnum
from typing import Annotated, Any, Literal, NotRequired, Required, TypedDict

from vet_manuscript_lab.domain.conventions import SCHEMA_VERSION


class WorkflowStage(StrEnum):
    PROJECT_INIT = "project_init"
    RESEARCH_QUESTION = "research_question"
    QUESTION_APPROVAL = "question_approval"
    GUIDELINE_MAPPING = "guideline_mapping"
    PROTOCOL_APPROVAL = "protocol_approval"
    PROTOCOL_LOCK = "protocol_lock"
    LITERATURE_SEARCH = "literature_search"
    SEARCH_APPROVAL = "search_approval"
    SCREENING = "screening"
    EVIDENCE_EXTRACTION = "evidence_extraction"
    EVIDENCE_AUDIT = "evidence_audit"
    METHODOLOGY_CRITIC = "methodology_critic"
    ANALYSIS_PLAN_APPROVAL = "analysis_plan_approval"
    ANALYSIS_PLAN_LOCK = "analysis_plan_lock"
    STATISTICS_EXECUTION = "statistics_execution"
    RESULTS_APPROVAL = "results_approval"
    WRITING = "writing"
    CLAIM_AUDIT = "claim_audit"
    REVIEW = "review"
    REVISION = "revision"
    FINAL_COMPLIANCE_AUDIT = "final_compliance_audit"
    FINAL_SIGN_OFF = "final_sign_off"
    EXPORT = "export"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    FAILED = "failed"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    BLOCKED = "blocked"
    FAILED = "failed"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


GateType = Literal[
    "question",
    "protocol",
    "search_strategy",
    "analysis_plan",
    "results_interpretation",
    "final_sign_off",
]


class ArtifactRef(TypedDict):
    artifact_id: str
    version_id: str
    artifact_type: str
    version: int
    status: str
    content_hash: str
    uri: str
    media_type: str
    created_at: str
    created_by_run_id: NotRequired[str]


class ApprovalRef(TypedDict):
    approval_id: str
    gate: GateType
    subject_id: str
    subject_version_id: str
    subject_hash: str
    decision: str
    reviewer_id: str
    reviewer_role: str
    decided_at: str
    comment: NotRequired[str]


class LockRef(TypedDict):
    lock_id: str
    lock_type: Literal["protocol", "analysis_plan", "dataset"]
    subject_id: str
    subject_version_id: str
    subject_hash: str
    locked_by: str
    locked_at: str
    approval_id: NotRequired[str]


class InterruptPayload(TypedDict):
    gate: GateType
    subject_id: str
    subject_version_id: str
    subject_hash: str
    title: str
    summary: str
    proposed_next_stage: str
    allowed_decisions: list[str]
    required_reviewer_role: str
    warning_codes: list[str]


class EventRecord(TypedDict):
    event_id: str
    event_type: str
    stage: str
    message: str
    occurred_at: str
    metadata: NotRequired[dict[str, Any]]


class LiteratureSummary(TypedDict):
    """Compact literature/search summary kept in state (references only)."""

    total_records: int
    included_count: int
    excluded_count: int
    search_strategy_version_id: NotRequired[str]
    evidence_ledger_version_id: NotRequired[str]


class EvidenceSummary(TypedDict):
    """Compact evidence extraction summary kept in state (references only)."""

    total_evidence_items: int
    items_requiring_review: int
    evidence_ledger_version_id: NotRequired[str]


class DatasetSummary(TypedDict):
    """Compact dataset version summary kept in state."""

    dataset_id: str
    dataset_version_id: str
    name: str
    row_count: int
    variable_count: int
    content_hash: str
    locked: bool


class MethodologyFinding(TypedDict, total=False):
    """Structured finding from the Methodology Critic."""

    finding_id: Required[str]
    category: str
    severity: str  # "info", "warning", "critical"
    rationale: str
    recommendation: str
    status: str  # "open", "addressed"


class AnalysisPlanSummary(TypedDict):
    """Compact analysis plan version summary kept in state."""

    plan_version_id: str
    content_hash: str
    version: int
    is_exploratory: bool
    locked: bool
    findings_count: int
    analysis_count: int


class AnalysisRunSummary(TypedDict):
    """Compact analysis run summary kept in state."""

    run_id: str
    status: str
    result_count: int
    is_reproducible: bool
    exit_code: int


class VariableSpecDraft(TypedDict, total=False):
    """Mock variable spec passed between graph nodes."""

    name: Required[str]
    var_type: str
    role: str
    unit: str | None
    missing_code: str | None


class AnalysisSpecDraft(TypedDict, total=False):
    """Mock analysis spec passed between graph nodes."""

    name: Required[str]
    estimand: str
    model_type: str
    variable_names: list[str]
    analysis_class: str
    exclusion_criteria: list[str]
    population: str | None


class ResultDraft(TypedDict, total=False):
    """Mock statistical result passed between graph nodes."""

    result_id: Required[str]
    estimand: str
    estimate: float | None
    estimate_units: str | None
    uncertainty_type: str | None
    uncertainty_lower: float | None
    uncertainty_upper: float | None
    p_value: float | None
    method: str | None
    population: str | None
    analysis_class: str


class LiteratureRecordDraft(TypedDict, total=False):
    """Mock literature record passed between graph nodes.

    In the production pipeline these rows live in the database via
    ``LiteratureRepository``; the mock pipeline keeps a compact draft in state
    so that downstream nodes can exercise the full evidence chain without an
    external Zotero / PDF integration.
    """

    record_id: Required[str]
    title: str
    doi: str | None
    pmid: str | None
    journal: str | None
    publication_year: int | None
    screening_decision: str


class SourceSpanDraft(TypedDict, total=False):
    """Mock source span carrying an attachment hash for audit verification."""

    span_id: Required[str]
    literature_record_id: str
    attachment_version_id: str
    page: int | None
    section_label: str | None
    quote_hash: str


class EvidenceDraft(TypedDict, total=False):
    """Mock evidence item with explicit source-span linkage for auditing."""

    evidence_id: Required[str]
    concept: str
    value: str | None
    units: str | None
    population: str | None
    literature_record_id: str
    source_span_ids: list[str]
    requires_human_review: bool
    extraction_status: str


class AIUsageSummary(TypedDict):
    """Compact AI model usage summary for UI display and cost tracking."""

    total_invocations: int
    total_cost_cents: int
    total_input_tokens: int
    total_output_tokens: int
    fallback_count: int
    failure_count: int
    cost_by_stage: dict[str, dict[str, int]]


class ManuscriptSummary(TypedDict):
    """Compact manuscript version summary kept in state."""

    manuscript_id: str
    version_id: str
    version: int
    content_hash: str
    section_count: int
    claim_count: int
    status: str


class ManuscriptSectionDraft(TypedDict, total=False):
    """Mock section draft passed between writing graph nodes."""

    section_id: Required[str]
    section_type: str
    content: str
    content_hash: str
    order: int
    word_count: int
    claim_ids: list[str]


class ManuscriptClaimDraft(TypedDict, total=False):
    """Mock claim draft passed between writing graph nodes."""

    claim_id: Required[str]
    claim_type: str
    text: str
    certainty: str
    section_id: str
    has_support: bool
    support_count: int
    referenced_numbers: list[float]


class ManuscriptSupportDraft(TypedDict, total=False):
    """Mock claim-support link passed between writing graph nodes."""

    claim_id: Required[str]
    support_type: str
    source_id: str
    relation: str
    audit_status: str


class ManuscriptCitationDraft(TypedDict, total=False):
    """Mock citation passed between writing graph nodes."""

    citation_key: Required[str]
    literature_record_id: str
    section_id: str
    claim_id: str
    locator: str


class ReviewFindingEntry(TypedDict, total=False):
    """Review finding produced by the Reviewer Agent."""

    finding_id: Required[str]
    category: str
    severity: str
    location: str
    rationale: str
    recommendation: str
    status: str


class RevisionDecisionEntry(TypedDict, total=False):
    """Human disposition of a review finding."""

    finding_id: Required[str]
    decision: str
    reason: str
    reviewer_id: str


class RevisionSummary(TypedDict):
    """Summary of a revision round."""

    round: int
    accepted_count: int
    rejected_count: int
    deferred_count: int
    section_diffs: list[dict[str, Any]]


class ComplianceFindingEntry(TypedDict, total=False):
    """Compliance finding produced by the Final Compliance Audit."""

    finding_id: Required[str]
    rule_id: str
    category: str
    severity: str
    status: str
    evidence: str
    recommendation: str


class ChecklistSummary(TypedDict):
    """Aggregate summary of checklist pass/fail counts."""

    total_items: int
    passed: int
    failed: int
    not_applicable: int
    needs_review: int


class ExportPackageSummary(TypedDict, total=False):
    """Summary of an immutable export package."""

    package_id: Required[str]
    manifest_hash: str
    component_count: int
    status: str
    package_uri: str
    sign_off_id: str


class SignOffBinding(TypedDict):
    """Artifact version hashes captured at final sign-off."""

    approval_id: str
    artifact_hashes: dict[str, str]
    signed_at: str


class WorkflowState(TypedDict, total=False):
    """LangGraph state containing references and compact decisions only."""

    project_id: Required[str]
    workflow_run_id: Required[str]
    thread_id: Required[str]
    schema_version: Required[str]
    current_stage: Required[str]
    run_status: Required[str]
    created_at: Required[str]
    updated_at: Required[str]

    study_type: str
    species_scope: list[str]
    research_question_input: NotRequired[dict[str, str]]
    search_strategy_input: NotRequired[dict[str, Any]]
    next_stage: str
    active_agent: str
    retry_count: int
    revision_round: int
    max_revision_rounds: int
    artifacts: dict[str, ArtifactRef]
    approvals: dict[str, ApprovalRef]
    locks: dict[str, LockRef]
    literature_summary: NotRequired[LiteratureSummary | None]
    evidence_summary: NotRequired[EvidenceSummary | None]
    literature_record_drafts: NotRequired[list[LiteratureRecordDraft]]
    source_span_drafts: NotRequired[list[SourceSpanDraft]]
    evidence_drafts: NotRequired[list[EvidenceDraft]]
    dataset_summary: NotRequired[DatasetSummary | None]
    analysis_plan_summary: NotRequired[AnalysisPlanSummary | None]
    analysis_run_summary: NotRequired[AnalysisRunSummary | None]
    methodology_findings: NotRequired[list[MethodologyFinding]]
    variable_spec_drafts: NotRequired[list[VariableSpecDraft]]
    analysis_spec_drafts: NotRequired[list[AnalysisSpecDraft]]
    result_drafts: NotRequired[list[ResultDraft]]
    ai_usage: NotRequired[AIUsageSummary | None]
    manuscript_summary: NotRequired[ManuscriptSummary | None]
    section_drafts: NotRequired[list[ManuscriptSectionDraft]]
    claim_drafts: NotRequired[list[ManuscriptClaimDraft]]
    support_drafts: NotRequired[list[ManuscriptSupportDraft]]
    citation_drafts: NotRequired[list[ManuscriptCitationDraft]]
    review_findings: NotRequired[list[ReviewFindingEntry]]
    revision_decisions: NotRequired[list[RevisionDecisionEntry]]
    revision_summary: NotRequired[RevisionSummary | None]
    compliance_findings: NotRequired[list[ComplianceFindingEntry]]
    checklist_summary: NotRequired[ChecklistSummary | None]
    export_readiness: NotRequired[str | None]
    sign_off_binding: NotRequired[SignOffBinding | None]
    export_package: NotRequired[ExportPackageSummary | None]
    pending_interrupt: InterruptPayload | None
    resume_decision: ApprovalRef | None
    errors: Annotated[list[EventRecord], operator.add]
    warnings: Annotated[list[EventRecord], operator.add]
    audit_events: Annotated[list[EventRecord], operator.add]
    tags: list[str]
    metrics: dict[str, int | float | str | bool | None]


TERMINAL_STAGES = {
    WorkflowStage.COMPLETE,
    WorkflowStage.BLOCKED,
    WorkflowStage.FAILED,
}

ALLOWED_TRANSITIONS: dict[WorkflowStage, frozenset[WorkflowStage]] = {
    WorkflowStage.PROJECT_INIT: frozenset({WorkflowStage.RESEARCH_QUESTION}),
    WorkflowStage.RESEARCH_QUESTION: frozenset({WorkflowStage.QUESTION_APPROVAL}),
    WorkflowStage.QUESTION_APPROVAL: frozenset(
        {WorkflowStage.GUIDELINE_MAPPING, WorkflowStage.RESEARCH_QUESTION}
    ),
    WorkflowStage.GUIDELINE_MAPPING: frozenset({WorkflowStage.PROTOCOL_APPROVAL}),
    WorkflowStage.PROTOCOL_APPROVAL: frozenset(
        {WorkflowStage.PROTOCOL_LOCK, WorkflowStage.GUIDELINE_MAPPING}
    ),
    WorkflowStage.PROTOCOL_LOCK: frozenset({WorkflowStage.LITERATURE_SEARCH}),
    WorkflowStage.LITERATURE_SEARCH: frozenset({WorkflowStage.SEARCH_APPROVAL}),
    WorkflowStage.SEARCH_APPROVAL: frozenset(
        {WorkflowStage.SCREENING, WorkflowStage.LITERATURE_SEARCH}
    ),
    WorkflowStage.SCREENING: frozenset({WorkflowStage.EVIDENCE_EXTRACTION}),
    WorkflowStage.EVIDENCE_EXTRACTION: frozenset({WorkflowStage.EVIDENCE_AUDIT}),
    WorkflowStage.EVIDENCE_AUDIT: frozenset(
        {WorkflowStage.METHODOLOGY_CRITIC, WorkflowStage.EVIDENCE_EXTRACTION}
    ),
    WorkflowStage.METHODOLOGY_CRITIC: frozenset({WorkflowStage.ANALYSIS_PLAN_APPROVAL}),
    WorkflowStage.ANALYSIS_PLAN_APPROVAL: frozenset(
        {WorkflowStage.ANALYSIS_PLAN_LOCK, WorkflowStage.METHODOLOGY_CRITIC}
    ),
    WorkflowStage.ANALYSIS_PLAN_LOCK: frozenset({WorkflowStage.STATISTICS_EXECUTION}),
    WorkflowStage.STATISTICS_EXECUTION: frozenset({WorkflowStage.RESULTS_APPROVAL}),
    WorkflowStage.RESULTS_APPROVAL: frozenset(
        {WorkflowStage.WRITING, WorkflowStage.STATISTICS_EXECUTION}
    ),
    WorkflowStage.WRITING: frozenset({WorkflowStage.CLAIM_AUDIT}),
    WorkflowStage.CLAIM_AUDIT: frozenset(
        {
            WorkflowStage.REVIEW,
            WorkflowStage.WRITING,
            WorkflowStage.REVISION,
            WorkflowStage.FINAL_COMPLIANCE_AUDIT,
        }
    ),
    WorkflowStage.REVIEW: frozenset({WorkflowStage.REVISION}),
    WorkflowStage.REVISION: frozenset({WorkflowStage.CLAIM_AUDIT}),
    WorkflowStage.FINAL_COMPLIANCE_AUDIT: frozenset(
        {WorkflowStage.FINAL_SIGN_OFF, WorkflowStage.REVISION}
    ),
    WorkflowStage.FINAL_SIGN_OFF: frozenset(
        {WorkflowStage.EXPORT, WorkflowStage.REVISION}
    ),
    WorkflowStage.EXPORT: frozenset({WorkflowStage.COMPLETE}),
}

REQUIRED_GATE_FOR_STAGE: dict[WorkflowStage, GateType] = {
    WorkflowStage.GUIDELINE_MAPPING: "question",
    WorkflowStage.PROTOCOL_LOCK: "protocol",
    WorkflowStage.SCREENING: "search_strategy",
    WorkflowStage.ANALYSIS_PLAN_LOCK: "analysis_plan",
    WorkflowStage.WRITING: "results_interpretation",
    WorkflowStage.EXPORT: "final_sign_off",
}


def new_workflow_state(
    *,
    project_id: str,
    workflow_run_id: str,
    thread_id: str,
    now: str,
    study_type: str = "retrospective_observational_clinical_study",
    species_scope: list[str] | None = None,
) -> WorkflowState:
    state: WorkflowState = {
        "project_id": project_id,
        "workflow_run_id": workflow_run_id,
        "thread_id": thread_id,
        "schema_version": SCHEMA_VERSION,
        "current_stage": WorkflowStage.PROJECT_INIT.value,
        "run_status": RunStatus.PENDING.value,
        "created_at": now,
        "updated_at": now,
        "study_type": study_type,
        "species_scope": species_scope or ["canine", "feline"],
        "retry_count": 0,
        "revision_round": 0,
        "max_revision_rounds": 3,
        "artifacts": {},
        "approvals": {},
        "locks": {},
        "literature_summary": None,
        "evidence_summary": None,
        "dataset_summary": None,
        "analysis_plan_summary": None,
        "analysis_run_summary": None,
        "methodology_findings": [],
        "variable_spec_drafts": [],
        "analysis_spec_drafts": [],
        "result_drafts": [],
        "ai_usage": None,
        "manuscript_summary": None,
        "section_drafts": [],
        "claim_drafts": [],
        "support_drafts": [],
        "citation_drafts": [],
        "review_findings": [],
        "revision_decisions": [],
        "revision_summary": None,
        "compliance_findings": [],
        "checklist_summary": None,
        "export_readiness": None,
        "sign_off_binding": None,
        "export_package": None,
        "pending_interrupt": None,
        "resume_decision": None,
        "errors": [],
        "warnings": [],
        "audit_events": [],
        "tags": [],
        "metrics": {},
    }
    assert_json_serializable(state)
    return state


def assert_json_serializable(value: Any) -> None:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Workflow state must be strictly JSON serializable") from exc


def validate_transition(current: str, target: str) -> None:
    current_stage = WorkflowStage(current)
    target_stage = WorkflowStage(target)
    if current_stage in TERMINAL_STAGES:
        raise ValueError(f"Cannot leave terminal stage: {current_stage.value}")
    if target_stage not in ALLOWED_TRANSITIONS.get(current_stage, frozenset()):
        raise ValueError(
            f"Invalid workflow transition: {current_stage.value} -> "
            f"{target_stage.value}"
        )


def require_approved_gate(state: WorkflowState, gate: GateType) -> ApprovalRef:
    approval = state.get("approvals", {}).get(gate)
    if approval is None:
        raise PermissionError(f"Missing required approval for gate: {gate}")
    if approval["decision"] != ApprovalDecision.APPROVED.value:
        raise PermissionError(f"Gate is not approved: {gate}")
    return approval


def validate_stage_preconditions(state: WorkflowState, target: str) -> None:
    target_stage = WorkflowStage(target)
    if gate := REQUIRED_GATE_FOR_STAGE.get(target_stage):
        require_approved_gate(state, gate)
    if target_stage is WorkflowStage.REVISION and state.get(
        "revision_round", 0
    ) >= state.get("max_revision_rounds", 3):
        raise PermissionError(
            "Automated revision limit reached; human escalation is required"
        )
    assert_json_serializable(state)


__all__ = [
    "ALLOWED_TRANSITIONS",
    "REQUIRED_GATE_FOR_STAGE",
    "AIUsageSummary",
    "AnalysisPlanSummary",
    "AnalysisRunSummary",
    "AnalysisSpecDraft",
    "ApprovalDecision",
    "ApprovalRef",
    "ArtifactRef",
    "ChecklistSummary",
    "ComplianceFindingEntry",
    "DatasetSummary",
    "EvidenceDraft",
    "EvidenceSummary",
    "ExportPackageSummary",
    "GateType",
    "InterruptPayload",
    "LiteratureRecordDraft",
    "LiteratureSummary",
    "LockRef",
    "ManuscriptCitationDraft",
    "ManuscriptClaimDraft",
    "ManuscriptSectionDraft",
    "ManuscriptSummary",
    "ManuscriptSupportDraft",
    "MethodologyFinding",
    "ResultDraft",
    "ReviewFindingEntry",
    "RevisionDecisionEntry",
    "RevisionSummary",
    "RunStatus",
    "SignOffBinding",
    "SourceSpanDraft",
    "VariableSpecDraft",
    "WorkflowStage",
    "WorkflowState",
    "assert_json_serializable",
    "new_workflow_state",
    "require_approved_gate",
    "validate_stage_preconditions",
    "validate_transition",
]
