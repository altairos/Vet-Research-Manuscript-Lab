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
    "ApprovalDecision",
    "ApprovalRef",
    "ArtifactRef",
    "EvidenceSummary",
    "GateType",
    "InterruptPayload",
    "LiteratureSummary",
    "LockRef",
    "RunStatus",
    "WorkflowStage",
    "WorkflowState",
    "assert_json_serializable",
    "new_workflow_state",
    "require_approved_gate",
    "validate_stage_preconditions",
    "validate_transition",
]
