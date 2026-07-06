"""Structured input/output schemas for every workflow node and artifact payload.

This module formalises the contracts described in ``agent_contracts.md`` and
``domain_model.md`` into importable, JSON-serialisable typed dictionaries.
Each workflow node receives a ``NodeInput`` and returns a ``NodeOutput``;
each artifact has a structured payload schema that defines its canonical
content shape.

Relationship to :mod:`vet_manuscript_lab.workflow.state`:

- ``state.py`` defines the *runtime* LangGraph state container
  (``WorkflowState``), transition rules, and compact ref types.
- ``state_schema.py`` (this module) defines the *structural contracts* for
  node inputs/outputs and artifact payload content—the shapes that agents
  must produce and that downstream nodes and the policy layer validate.

All schemas are plain ``TypedDict`` / ``Literal`` constructs so they remain
runtime-free and strictly JSON-serialisable.
"""

from __future__ import annotations

import typing
from typing import (
    Any,
    Literal,
    NotRequired,
    Protocol,
    Required,
    TypedDict,
    get_origin,
    get_type_hints,
)

from vet_manuscript_lab.domain.conventions import ArtifactType, ErrorCode
from vet_manuscript_lab.workflow.state import (
    ApprovalRef,
    ArtifactRef,
    GateType,
    LockRef,
    WorkflowStage,
    assert_json_serializable,
)

# ---------------------------------------------------------------------------
# Enums and literal types used across node contracts
# ---------------------------------------------------------------------------

#: Allowed study types in the MVP.
StudyType = Literal[
    "retrospective_observational_clinical_study",
    "prospective_observational_study",
    "systematic_review",
    "randomized_controlled_trial",
    "case_report",
]

#: STROBE-Vet / ARRIVE / PRISMA / REFLECT.
ReportingGuideline = Literal[
    "STROBE-Vet",
    "ARRIVE_2.0",
    "PRISMA_2020",
    "REFLECT",
]

#: Where a claim sits in the IMRaD structure.
ManuscriptSectionType = Literal[
    "title",
    "abstract",
    "introduction",
    "methods",
    "results",
    "discussion",
    "conclusion",
    "references",
]

#: Whether a claim is a factual statement or an author interpretation.
ClaimType = Literal[
    "fact",
    "result",
    "interpretation",
    "hypothesis",
    "methodological",
]

CertaintyLevel = Literal[
    "high",
    "moderate",
    "low",
    "unspecified",
]

#: Support relation between a claim and its backing source.
SupportType = Literal[
    "evidence_item",
    "statistical_result",
    "protocol",
]

#: Confirmatory vs. exploratory analysis class.
AnalysisClass = Literal[
    "confirmatory",
    "exploratory",
    "sensitivity",
]

#: Severity for review findings and compliance findings.
FindingSeverity = Literal[
    "critical",
    "high",
    "medium",
    "low",
    "info",
]

#: Disposition of a review finding during revision.
FindingDisposition = Literal[
    "accept",
    "reject",
    "defer",
]

#: Lifecycle status of an artifact version.
ArtifactStatus = Literal[
    "draft",
    "in_review",
    "approved",
    "rejected",
    "locked",
    "superseded",
    "failed",
]

#: PECO/PICO component labels.
PicoComponent = Literal[
    "population",
    "exposure",
    "intervention",
    "comparator",
    "outcome",
    "timing",
    "setting",
]


# ---------------------------------------------------------------------------
# Entity payload schemas — canonical content stored in artifacts
# ---------------------------------------------------------------------------


class PecoPicoSpec(TypedDict, total=False):
    """PECO / PICO / PICOS breakdown for a research question."""

    population: Required[str]
    exposure: NotRequired[str]
    intervention: NotRequired[str]
    comparator: Required[str]
    outcomes: Required[list[str]]
    timing: NotRequired[str]
    setting: NotRequired[str]
    study_design: NotRequired[str]


class ResearchQuestionPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.RESEARCH_QUESTION`` artifacts."""

    study_type: Required[StudyType]
    species_scope: Required[list[str]]
    pico: Required[PecoPicoSpec]
    primary_objective: Required[str]
    secondary_objectives: NotRequired[list[str]]
    assumptions: NotRequired[list[str]]
    unresolved_questions: NotRequired[list[str]]
    version: Required[int]


class ProtocolPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.PROTOCOL`` artifacts."""

    research_question_version_id: Required[str]
    guideline: Required[ReportingGuideline]
    primary_endpoint: Required[str]
    secondary_endpoints: NotRequired[list[str]]
    eligibility_criteria: Required[str]
    inclusion_criteria: NotRequired[list[str]]
    exclusion_criteria: NotRequired[list[str]]
    variables: NotRequired[list[str]]
    limitations: NotRequired[list[str]]
    version: Required[int]


class GuidelineMappingItem(TypedDict, total=False):
    """A single checklist item in a guideline mapping."""

    item_number: Required[str]
    description: Required[str]
    applicability: Required[Literal["required", "not_applicable", "conditional"]]
    required_evidence: NotRequired[str]
    owner: NotRequired[str]
    status: Required[Literal["pending", "addressed", "missing", "not_applicable"]]


class GuidelineMappingPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.GUIDELINE_MAPPING`` artifacts."""

    protocol_version_id: Required[str]
    guideline: Required[ReportingGuideline]
    guideline_version: Required[str]
    checklist_items: Required[list[GuidelineMappingItem]]
    version: Required[int]


class SearchStrategyPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.SEARCH_STRATEGY`` artifacts."""

    databases: Required[list[str]]
    query: Required[str]
    database_queries: NotRequired[dict[str, str]]
    date_range: Required[str]
    filters: NotRequired[list[str]]
    species_scope: Required[list[str]]
    eligibility_version_id: NotRequired[str]
    deduplication_policy: NotRequired[str]
    record_count: Required[int]
    version: Required[int]


class ScreeningDecisionEntry(TypedDict, total=False):
    """One record-level screening decision within a screening result."""

    record_id: Required[str]
    decision: Required[Literal["included", "excluded"]]
    stage: NotRequired[Literal["title_abstract", "full_text"]]
    reason: NotRequired[str]
    confidence: NotRequired[CertaintyLevel]


class ScreeningResultPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.SCREENING_RESULT`` artifacts."""

    total: Required[int]
    included: Required[int]
    excluded: Required[int]
    decisions: Required[list[ScreeningDecisionEntry]]
    conflicts: NotRequired[list[str]]
    version: Required[int]


class EvidenceEntry(TypedDict, total=False):
    """One evidence item within an evidence ledger payload."""

    evidence_id: Required[str]
    concept: Required[str]
    value: NotRequired[str | None]
    units: NotRequired[str | None]
    population: NotRequired[str | None]
    certainty: NotRequired[CertaintyLevel]
    literature_record_id: Required[str]
    source_span_ids: Required[list[str]]
    requires_human_review: Required[bool]
    extraction_status: Required[str]


class EvidenceLedgerPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.EVIDENCE_LEDGER`` artifacts."""

    total_evidence: Required[int]
    items: Required[list[EvidenceEntry]]
    gaps: NotRequired[list[str]]
    version: Required[int]


class VariableDefinition(TypedDict, total=False):
    """One variable in a dataset dictionary."""

    name: Required[str]
    data_type: Required[
        Literal["continuous", "categorical", "ordinal", "binary", "text", "datetime"]
    ]
    unit: NotRequired[str | None]
    role: NotRequired[
        Literal["outcome", "exposure", "confounder", "covariate", "identifier"]
    ]
    missing_code: NotRequired[str]
    reference_range: NotRequired[str]


class DatasetPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.DATASET`` artifacts."""

    name: Required[str]
    row_count: Required[int]
    column_count: NotRequired[int]
    schema_hash: NotRequired[str]
    variables: NotRequired[list[VariableDefinition]]
    version: Required[int]


class AnalysisModelSpec(TypedDict, total=False):
    """A single model specification within an analysis plan."""

    name: Required[str]
    model_type: Required[str]
    dependent_variable: NotRequired[str]
    independent_variables: NotRequired[list[str]]
    random_effects: NotRequired[list[str]]
    covariates: NotRequired[list[str]]
    analysis_class: Required[AnalysisClass]


class AnalysisPlanPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.ANALYSIS_PLAN`` artifacts."""

    protocol_version_id: Required[str]
    dataset_version_id: NotRequired[str]
    populations: NotRequired[list[str]]
    primary_analysis: Required[AnalysisModelSpec]
    secondary_analyses: NotRequired[list[AnalysisModelSpec]]
    sensitivity_analyses: NotRequired[list[AnalysisModelSpec]]
    missingness_strategy: NotRequired[str]
    multiple_testing_correction: NotRequired[str]
    limitations: NotRequired[list[str]]
    version: Required[int]


class AnalysisRunManifest(TypedDict, total=False):
    """Reproducibility manifest for a single analysis execution."""

    plan_version_id: Required[str]
    dataset_version_id: Required[str]
    script_version_id: Required[str]
    dataset_hash: Required[str]
    script_hash: Required[str]
    random_seed: Required[int]
    runner_environment: Required[str]
    package_versions: Required[dict[str, str]]
    exit_status: Required[Literal["success", "failure"]]
    stdout_hash: NotRequired[str]
    stderr_hash: NotRequired[str]


class StatisticalResultEntry(TypedDict, total=False):
    """One typed statistical result within an analysis result payload."""

    result_id: Required[str]
    estimand: Required[str]
    estimate: Required[float]
    estimate_units: NotRequired[str]
    se: NotRequired[float]
    ci_lower: NotRequired[float]
    ci_upper: NotRequired[float]
    confidence_level: NotRequired[float]
    p_value: NotRequired[float]
    effect_size: NotRequired[str]
    analysis_class: Required[AnalysisClass]
    model_name: NotRequired[str]


class AnalysisResultPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.ANALYSIS_RESULT`` artifacts."""

    run_manifest: Required[AnalysisRunManifest]
    results: Required[list[StatisticalResultEntry]]
    tables: NotRequired[list[str]]
    figures: NotRequired[list[str]]
    version: Required[int]


class ClaimSupportEntry(TypedDict, total=False):
    """One support relation linking a claim to an evidence/statistical source."""

    support_type: Required[SupportType]
    target_id: Required[str]
    relation: NotRequired[Literal["supports", "contradicts", "partially_supports"]]
    audit_status: NotRequired[Literal["verified", "unverified", "flagged"]]


class ClaimEntry(TypedDict, total=False):
    """One manuscript claim extracted by the writing or revision agent."""

    claim_id: Required[str]
    section: Required[ManuscriptSectionType]
    sentence: Required[str]
    claim_type: Required[ClaimType]
    certainty: Required[CertaintyLevel]
    supports: Required[list[ClaimSupportEntry]]
    status: Required[Literal["draft", "audited", "needs_human_review", "rejected"]]
    locator: NotRequired[str]


class CitationEntry(TypedDict, total=False):
    """One citation occurrence linking a manuscript location to a reference."""

    citation_id: Required[str]
    claim_id: NotRequired[str]
    section: NotRequired[ManuscriptSectionType]
    literature_record_id: Required[str]
    citation_key: Required[str]
    locator: NotRequired[str]
    source_span_id: NotRequired[str]


class ManuscriptSectionPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.MANUSCRIPT_SECTION`` artifacts."""

    section_type: Required[ManuscriptSectionType]
    content_uri: Required[str]
    content_hash: Required[str]
    order: Required[int]
    claims: Required[list[ClaimEntry]]
    citations: Required[list[CitationEntry]]
    evidence_gaps: NotRequired[list[str]]
    version: Required[int]


class ManuscriptPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.MANUSCRIPT`` artifacts."""

    target_journal: NotRequired[str]
    section_version_ids: Required[list[str]]
    citation_set: NotRequired[list[str]]
    content_hash: Required[str]
    version: Required[int]


class ReviewFindingEntry(TypedDict, total=False):
    """One actionable critique from the reviewer agent."""

    finding_id: Required[str]
    category: Required[str]
    severity: Required[FindingSeverity]
    location: NotRequired[str]
    rationale: Required[str]
    evidence: NotRequired[list[str]]
    proposed_resolution: NotRequired[str]
    status: Required[Literal["open", "accepted", "rejected", "deferred", "resolved"]]


class ReviewerCritiquePayload(TypedDict, total=False):
    """Payload for ``ArtifactType.REVIEWER_CRITIQUE`` artifacts."""

    manuscript_version_id: Required[str]
    findings: Required[list[ReviewFindingEntry]]
    version: Required[int]


class RevisionDecisionEntry(TypedDict, total=False):
    """Human disposition of a single review finding."""

    finding_id: Required[str]
    disposition: Required[FindingDisposition]
    reason: Required[str]
    reviewer_id: Required[str]


class CitationAuditFinding(TypedDict, total=False):
    """One finding from a citation / evidence audit pass."""

    finding_id: Required[str]
    check_type: Required[
        Literal[
            "existence",
            "locator_integrity",
            "entailment",
            "overreach",
            "contradictory_support",
            "quote_hash_mismatch",
        ]
    ]
    target_claim_id: NotRequired[str]
    target_citation_id: NotRequired[str]
    target_evidence_id: NotRequired[str]
    severity: Required[FindingSeverity]
    message: Required[str]


class CitationAuditPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.CITATION_AUDIT`` artifacts."""

    audit_stage: Required[Literal["evidence_audit", "claim_audit", "final_audit"]]
    findings: Required[list[CitationAuditFinding]]
    total_checked: Required[int]
    items_requiring_review: Required[int]
    version: Required[int]


class ComplianceFindingEntry(TypedDict, total=False):
    """One checklist / audit outcome from the final compliance audit."""

    rule_id: Required[str]
    rule_description: Required[str]
    status: Required[Literal["pass", "fail", "warning", "not_applicable"]]
    evidence: NotRequired[str]
    requires_human_review: Required[bool]
    severity: NotRequired[FindingSeverity]


class GuidelineChecklistPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.GUIDELINE_CHECKLIST`` artifacts."""

    manuscript_version_id: Required[str]
    guideline: Required[ReportingGuideline]
    findings: Required[list[ComplianceFindingEntry]]
    completeness_score: NotRequired[float]
    export_readiness: Required[Literal["ready", "not_ready", "conditional"]]
    version: Required[int]


class ExportPackagePayload(TypedDict, total=False):
    """Payload for ``ArtifactType.EXPORT_PACKAGE`` artifacts."""

    manuscript_version_id: Required[str]
    sign_off_approval_id: Required[str]
    components: Required[list[str]]
    docx_uri: Required[str]
    bib_uri: Required[str]
    package_hash: Required[str]
    version: Required[int]


class AIUsageLogEntry(TypedDict, total=False):
    """One record of AI model usage for disclosure."""

    agent_type: Required[str]
    model_provider: Required[str]
    model_name: Required[str]
    model_version: Required[str]
    prompt_version: NotRequired[str]
    usage_stage: Required[str]
    purpose: Required[str]
    human_reviewed: Required[bool]


class AIUsageLogPayload(TypedDict, total=False):
    """Payload for ``ArtifactType.AI_USAGE_LOG`` artifacts."""

    entries: Required[list[AIUsageLogEntry]]
    version: Required[int]


# ---------------------------------------------------------------------------
# Generic node input / output base shapes
# ---------------------------------------------------------------------------


class NodeInput(TypedDict, total=False):
    """Common fields present in every node input payload."""

    project_id: Required[str]
    workflow_run_id: Required[str]
    thread_id: Required[str]
    schema_version: Required[str]
    current_stage: Required[str]


class NodeOutput(TypedDict, total=False):
    """Common fields present in every node output payload."""

    current_stage: Required[str]
    updated_at: Required[str]
    audit_events: Required[list[dict[str, Any]]]


class InterruptRequest(TypedDict):
    """Serialisable interrupt payload sent to the human reviewer."""

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


class NodeFailure(TypedDict):
    """Structured failure record emitted when a node encounters an error."""

    error_code: ErrorCode
    message: str
    retryable: bool
    stage: str
    details: NotRequired[dict[str, Any]]


# ---------------------------------------------------------------------------
# Per-node input / output schemas (mirrors agent_contracts.md § 2)
# ---------------------------------------------------------------------------


class ProjectInitInput(NodeInput, total=False):
    title: Required[str]
    owner_ids: Required[list[str]]
    species_scope: Required[list[str]]
    study_type: Required[StudyType]
    data_sensitivity: NotRequired[str]


class ProjectInitOutput(NodeOutput, total=False):
    project_id: Required[str]
    workflow_run_id: Required[str]
    thread_id: Required[str]


class ResearchQuestionInput(NodeInput, total=False):
    project_brief_version_id: NotRequired[str]
    investigator_notes: NotRequired[str]


class ResearchQuestionOutput(NodeOutput, total=False):
    research_question_artifact: Required[ArtifactRef]


class GuidelineMappingInput(NodeInput, total=False):
    research_question_artifact: Required[ArtifactRef]
    question_approval: Required[ApprovalRef]


class GuidelineMappingOutput(NodeOutput, total=False):
    protocol_artifact: Required[ArtifactRef]
    guideline_mapping_artifact: Required[ArtifactRef]


class ProtocolApprovalOutput(NodeOutput, total=False):
    protocol_approval: Required[ApprovalRef]


class ProtocolLockOutput(NodeOutput, total=False):
    protocol_lock: Required[LockRef]


class LiteratureSearchInput(NodeInput, total=False):
    protocol_lock: Required[LockRef]
    protocol_artifact: Required[ArtifactRef]


class LiteratureSearchOutput(NodeOutput, total=False):
    search_strategy_artifact: Required[ArtifactRef]
    literature_summary: Required[dict[str, Any]]


class SearchApprovalOutput(NodeOutput, total=False):
    search_approval: Required[ApprovalRef]


class ScreeningInput(NodeInput, total=False):
    search_approval: Required[ApprovalRef]
    search_strategy_artifact: Required[ArtifactRef]


class ScreeningOutput(NodeOutput, total=False):
    screening_result_artifact: Required[ArtifactRef]
    literature_summary: Required[dict[str, Any]]


class EvidenceExtractionInput(NodeInput, total=False):
    search_approval: Required[ApprovalRef]
    screening_result_artifact: Required[ArtifactRef]


class EvidenceExtractionOutput(NodeOutput, total=False):
    evidence_ledger_artifact: Required[ArtifactRef]
    evidence_summary: Required[dict[str, Any]]


class EvidenceAuditInput(NodeInput, total=False):
    evidence_ledger_artifact: Required[ArtifactRef]


class EvidenceAuditOutput(NodeOutput, total=False):
    citation_audit_artifact: Required[ArtifactRef]
    evidence_summary: Required[dict[str, Any]]


class MethodologyCriticInput(NodeInput, total=False):
    protocol_lock: Required[LockRef]
    evidence_ledger_artifact: Required[ArtifactRef]
    guideline_mapping_artifact: Required[ArtifactRef]
    dataset_artifact: NotRequired[ArtifactRef]


class MethodologyCriticOutput(NodeOutput, total=False):
    analysis_plan_artifact: Required[ArtifactRef]


class AnalysisPlanApprovalOutput(NodeOutput, total=False):
    analysis_plan_approval: Required[ApprovalRef]


class AnalysisPlanLockOutput(NodeOutput, total=False):
    analysis_plan_lock: Required[LockRef]


class StatisticsInput(NodeInput, total=False):
    analysis_plan_lock: Required[LockRef]
    dataset_lock: NotRequired[LockRef]
    analysis_plan_artifact: Required[ArtifactRef]
    dataset_artifact: Required[ArtifactRef]


class StatisticsOutput(NodeOutput, total=False):
    analysis_result_artifact: Required[ArtifactRef]


class ResultsApprovalOutput(NodeOutput, total=False):
    results_approval: Required[ApprovalRef]


class WritingInput(NodeInput, total=False):
    results_approval: Required[ApprovalRef]
    protocol_artifact: Required[ArtifactRef]
    evidence_ledger_artifact: Required[ArtifactRef]
    analysis_result_artifact: Required[ArtifactRef]
    guideline_mapping_artifact: Required[ArtifactRef]
    section_request: Required[ManuscriptSectionType]


class WritingOutput(NodeOutput, total=False):
    manuscript_section_artifact: Required[ArtifactRef]


class ClaimAuditInput(NodeInput, total=False):
    manuscript_section_artifact: Required[ArtifactRef]
    evidence_ledger_artifact: Required[ArtifactRef]
    analysis_result_artifact: Required[ArtifactRef]


class ClaimAuditOutput(NodeOutput, total=False):
    citation_audit_artifact: Required[ArtifactRef]


class ReviewerInput(NodeInput, total=False):
    manuscript_artifact: Required[ArtifactRef]
    evidence_ledger_artifact: Required[ArtifactRef]
    analysis_result_artifact: Required[ArtifactRef]
    guideline_mapping_artifact: Required[ArtifactRef]


class ReviewerOutput(NodeOutput, total=False):
    reviewer_critique_artifact: Required[ArtifactRef]


class RevisionInput(NodeInput, total=False):
    manuscript_artifact: Required[ArtifactRef]
    reviewer_critique_artifact: Required[ArtifactRef]
    revision_decisions: Required[list[RevisionDecisionEntry]]


class RevisionOutput(NodeOutput, total=False):
    manuscript_section_artifact: Required[ArtifactRef]
    revision_round: Required[int]


class ComplianceAuditInput(NodeInput, total=False):
    manuscript_artifact: Required[ArtifactRef]
    guideline_mapping_artifact: Required[ArtifactRef]
    citation_audit_artifact: Required[ArtifactRef]
    analysis_result_artifact: Required[ArtifactRef]
    ai_usage_log_artifact: NotRequired[ArtifactRef]


class ComplianceAuditOutput(NodeOutput, total=False):
    guideline_checklist_artifact: Required[ArtifactRef]


class FinalSignOffOutput(NodeOutput, total=False):
    final_approval: Required[ApprovalRef]


class ExportInput(NodeInput, total=False):
    final_approval: Required[ApprovalRef]
    manuscript_artifact: Required[ArtifactRef]
    guideline_checklist_artifact: Required[ArtifactRef]
    journal_template: NotRequired[str]


class ExportOutput(NodeOutput, total=False):
    export_package_artifact: Required[ArtifactRef]


# ---------------------------------------------------------------------------
# Schema registry
# ---------------------------------------------------------------------------

#: Maps artifact type to its canonical payload TypedDict.
ARTIFACT_PAYLOAD_SCHEMAS: dict[ArtifactType, type] = {
    ArtifactType.RESEARCH_QUESTION: ResearchQuestionPayload,
    ArtifactType.PROTOCOL: ProtocolPayload,
    ArtifactType.GUIDELINE_MAPPING: GuidelineMappingPayload,
    ArtifactType.SEARCH_STRATEGY: SearchStrategyPayload,
    ArtifactType.SCREENING_RESULT: ScreeningResultPayload,
    ArtifactType.EVIDENCE_LEDGER: EvidenceLedgerPayload,
    ArtifactType.DATASET: DatasetPayload,
    ArtifactType.DATASET_DICTIONARY: DatasetPayload,
    ArtifactType.ANALYSIS_PLAN: AnalysisPlanPayload,
    ArtifactType.ANALYSIS_RESULT: AnalysisResultPayload,
    ArtifactType.MANUSCRIPT_SECTION: ManuscriptSectionPayload,
    ArtifactType.MANUSCRIPT: ManuscriptPayload,
    ArtifactType.REVIEWER_CRITIQUE: ReviewerCritiquePayload,
    ArtifactType.GUIDELINE_CHECKLIST: GuidelineChecklistPayload,
    ArtifactType.CITATION_AUDIT: CitationAuditPayload,
    ArtifactType.AI_USAGE_LOG: AIUsageLogPayload,
    ArtifactType.EXPORT_PACKAGE: ExportPackagePayload,
}

#: Maps workflow stage to the input schema for the node that runs at that stage.
NODE_INPUT_SCHEMAS: dict[WorkflowStage, type] = {
    WorkflowStage.PROJECT_INIT: ProjectInitInput,
    WorkflowStage.RESEARCH_QUESTION: ResearchQuestionInput,
    WorkflowStage.GUIDELINE_MAPPING: GuidelineMappingInput,
    WorkflowStage.LITERATURE_SEARCH: LiteratureSearchInput,
    WorkflowStage.SCREENING: ScreeningInput,
    WorkflowStage.EVIDENCE_EXTRACTION: EvidenceExtractionInput,
    WorkflowStage.EVIDENCE_AUDIT: EvidenceAuditInput,
    WorkflowStage.METHODOLOGY_CRITIC: MethodologyCriticInput,
    WorkflowStage.STATISTICS_EXECUTION: StatisticsInput,
    WorkflowStage.WRITING: WritingInput,
    WorkflowStage.CLAIM_AUDIT: ClaimAuditInput,
    WorkflowStage.REVIEW: ReviewerInput,
    WorkflowStage.REVISION: RevisionInput,
    WorkflowStage.FINAL_COMPLIANCE_AUDIT: ComplianceAuditInput,
    WorkflowStage.EXPORT: ExportInput,
}

#: Maps workflow stage to the output schema for the node that runs at that stage.
NODE_OUTPUT_SCHEMAS: dict[WorkflowStage, type] = {
    WorkflowStage.PROJECT_INIT: ProjectInitOutput,
    WorkflowStage.RESEARCH_QUESTION: ResearchQuestionOutput,
    WorkflowStage.GUIDELINE_MAPPING: GuidelineMappingOutput,
    WorkflowStage.PROTOCOL_APPROVAL: ProtocolApprovalOutput,
    WorkflowStage.PROTOCOL_LOCK: ProtocolLockOutput,
    WorkflowStage.LITERATURE_SEARCH: LiteratureSearchOutput,
    WorkflowStage.SEARCH_APPROVAL: SearchApprovalOutput,
    WorkflowStage.SCREENING: ScreeningOutput,
    WorkflowStage.EVIDENCE_EXTRACTION: EvidenceExtractionOutput,
    WorkflowStage.EVIDENCE_AUDIT: EvidenceAuditOutput,
    WorkflowStage.METHODOLOGY_CRITIC: MethodologyCriticOutput,
    WorkflowStage.ANALYSIS_PLAN_APPROVAL: AnalysisPlanApprovalOutput,
    WorkflowStage.ANALYSIS_PLAN_LOCK: AnalysisPlanLockOutput,
    WorkflowStage.STATISTICS_EXECUTION: StatisticsOutput,
    WorkflowStage.RESULTS_APPROVAL: ResultsApprovalOutput,
    WorkflowStage.WRITING: WritingOutput,
    WorkflowStage.CLAIM_AUDIT: ClaimAuditOutput,
    WorkflowStage.REVIEW: ReviewerOutput,
    WorkflowStage.REVISION: RevisionOutput,
    WorkflowStage.FINAL_COMPLIANCE_AUDIT: ComplianceAuditOutput,
    WorkflowStage.FINAL_SIGN_OFF: FinalSignOffOutput,
    WorkflowStage.EXPORT: ExportOutput,
}


# ---------------------------------------------------------------------------
# Validation utilities
# ---------------------------------------------------------------------------


class SchemaValidator(Protocol):
    """Protocol for pluggable schema validators (e.g. jsonschema, pydantic)."""

    def validate(self, payload: dict[str, Any], schema_type: type) -> list[str]:
        """Return a list of violation messages; empty list means valid."""
        ...


def _extract_required_keys(typed_dict_cls: type) -> frozenset[str]:
    """Return the set of keys that are required in a TypedDict class.

    When ``from __future__ import annotations`` is active, the runtime
    ``__required_keys__`` attribute may be empty for ``total=False`` dicts
    because ``Required[]`` annotations are stored as strings.  This function
    resolves type hints with ``include_extras=True`` and inspects
    ``get_origin`` to correctly identify ``Required[]`` / ``NotRequired[]``
    wrappers.
    """

    is_total = getattr(typed_dict_cls, "__total__", True)
    try:
        hints = get_type_hints(typed_dict_cls, include_extras=True)
    except Exception:
        return frozenset(getattr(typed_dict_cls, "__required_keys__", frozenset()))

    required: set[str] = set()
    for key, hint in hints.items():
        origin = get_origin(hint)
        if origin is typing.Required:
            required.add(key)
        elif origin is typing.NotRequired:
            continue
        elif is_total:
            # total=True: every field is required unless explicitly NotRequired
            required.add(key)
    return frozenset(required)


def validate_payload(
    payload: dict[str, Any],
    artifact_type: ArtifactType,
) -> list[str]:
    """Check that *payload* satisfies the required keys for *artifact_type*.

    Returns a list of human-readable violation messages.  An empty list
    means the payload is structurally valid (all required keys present).
    This is a lightweight structural check; full JSON-schema validation
    can be layered on top later.
    """

    schema_cls = ARTIFACT_PAYLOAD_SCHEMAS.get(artifact_type)
    if schema_cls is None:
        return [f"No payload schema registered for artifact type: {artifact_type}"]

    violations: list[str] = []
    required = _extract_required_keys(schema_cls)
    for key in sorted(required):
        if key not in payload:
            violations.append(
                f"Missing required field '{key}' for {artifact_type.value} payload"
            )

    try:
        assert_json_serializable(payload)
    except ValueError as exc:
        violations.append(str(exc))

    return violations


def validate_node_output(
    output: dict[str, Any],
    stage: WorkflowStage,
) -> list[str]:
    """Check that *output* satisfies the required keys for *stage*."""

    schema_cls = NODE_OUTPUT_SCHEMAS.get(stage)
    if schema_cls is None:
        return [f"No output schema registered for stage: {stage.value}"]

    violations: list[str] = []
    required = _extract_required_keys(schema_cls)
    for key in sorted(required):
        if key not in output:
            violations.append(
                f"Missing required field '{key}' in output for stage {stage.value}"
            )

    try:
        assert_json_serializable(output)
    except ValueError as exc:
        violations.append(str(exc))

    return violations


def make_node_failure(
    *,
    error_code: ErrorCode,
    message: str,
    stage: WorkflowStage,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> NodeFailure:
    """Construct a structured failure record for a node error."""

    failure: NodeFailure = {
        "error_code": error_code,
        "message": message,
        "retryable": retryable,
        "stage": stage.value,
    }
    if details is not None:
        failure["details"] = details
    return failure


__all__ = [
    # Schema registries
    "ARTIFACT_PAYLOAD_SCHEMAS",
    "NODE_INPUT_SCHEMAS",
    "NODE_OUTPUT_SCHEMAS",
    # Entity payload schemas
    "AIUsageLogEntry",
    "AIUsageLogPayload",
    # Literal type aliases
    "AnalysisClass",
    "AnalysisModelSpec",
    # Node I/O schemas
    "AnalysisPlanApprovalOutput",
    "AnalysisPlanLockOutput",
    "AnalysisPlanPayload",
    "AnalysisResultPayload",
    "AnalysisRunManifest",
    "ArtifactStatus",
    "CertaintyLevel",
    "CitationAuditFinding",
    "CitationAuditPayload",
    "CitationEntry",
    "ClaimAuditInput",
    "ClaimAuditOutput",
    "ClaimEntry",
    "ClaimSupportEntry",
    "ClaimType",
    "ComplianceAuditInput",
    "ComplianceAuditOutput",
    "ComplianceFindingEntry",
    "DatasetPayload",
    "EvidenceAuditInput",
    "EvidenceAuditOutput",
    "EvidenceEntry",
    "EvidenceExtractionInput",
    "EvidenceExtractionOutput",
    "EvidenceLedgerPayload",
    "ExportInput",
    "ExportOutput",
    "ExportPackagePayload",
    "FinalSignOffOutput",
    "FindingDisposition",
    "FindingSeverity",
    "GuidelineChecklistPayload",
    "GuidelineMappingInput",
    "GuidelineMappingItem",
    "GuidelineMappingOutput",
    "GuidelineMappingPayload",
    "InterruptRequest",
    "LiteratureSearchInput",
    "LiteratureSearchOutput",
    "ManuscriptPayload",
    "ManuscriptSectionPayload",
    "ManuscriptSectionType",
    "MethodologyCriticInput",
    "MethodologyCriticOutput",
    "NodeFailure",
    "NodeInput",
    "NodeOutput",
    "PecoPicoSpec",
    "PicoComponent",
    "ProjectInitInput",
    "ProjectInitOutput",
    "ProtocolApprovalOutput",
    "ProtocolLockOutput",
    "ProtocolPayload",
    "ReportingGuideline",
    "ResearchQuestionInput",
    "ResearchQuestionOutput",
    "ResearchQuestionPayload",
    "ResultsApprovalOutput",
    "ReviewFindingEntry",
    "ReviewerCritiquePayload",
    "ReviewerInput",
    "ReviewerOutput",
    "RevisionDecisionEntry",
    "RevisionInput",
    "RevisionOutput",
    # Validation utilities
    "SchemaValidator",
    "ScreeningDecisionEntry",
    "ScreeningInput",
    "ScreeningOutput",
    "ScreeningResultPayload",
    "SearchApprovalOutput",
    "SearchStrategyPayload",
    "StatisticalResultEntry",
    "StatisticsInput",
    "StatisticsOutput",
    "StudyType",
    "SupportType",
    "VariableDefinition",
    "WritingInput",
    "WritingOutput",
    "make_node_failure",
    "validate_node_output",
    "validate_payload",
]
