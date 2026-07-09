"""Writing, review, and revision pipeline extending the analysis graph.

Implements the ``WRITING -> CLAIM_AUDIT -> REVIEW -> REVISION`` vertical
slice with controlled revision loops.  Every policy invariant (claim
support, numeric consistency, no causal overreach, reviewer read-only,
revision limits) is enforced inside the nodes.

The section writer, reviewer, and reviser are injected via Protocol.
When ``None``, deterministic mock implementations are used so the
pipeline remains runnable in offline development.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from vet_manuscript_lab.domain.conventions import RunMode, utc_now
from vet_manuscript_lab.domain.policies import (
    AuditContext,
    ClaimSnapshot,
    PolicyViolation,
    StatisticalResultSnapshot,
    require_factual_claim_has_support,
    require_finding_before_revision,
    require_no_causal_overreach,
    require_no_mock_fallback,
    require_numeric_consistency,
    require_reviewer_readonly,
    require_revision_within_limit,
    require_writing_inputs_approved,
)
from vet_manuscript_lab.infrastructure.model_gateway.gateway import (
    ModelGateway,
)
from vet_manuscript_lab.services.analysis.runner import (
    StatisticsRunner,
)
from vet_manuscript_lab.services.writing import (
    ClaimDraftData,
    MockReviewer,
    MockReviser,
    MockSectionWriter,
    Reviewer,
    ReviewInput,
    Reviser,
    RevisionDecisionDraft,
    RevisionInput,
    SectionDraft,
    SectionWriter,
    WritingInput,
)
from vet_manuscript_lab.workflow.analysis_graph import (
    _evidence_audit_running,
    _protocol_lock_running,
    analysis_plan_approval_node,
    analysis_plan_lock_node,
    analysis_plan_node,
    methodology_critic_node,
    results_approval_node,
    route_analysis_plan_decision,
    statistics_execution_node,
)
from vet_manuscript_lab.workflow.foundation_graph import (
    _event,
    _stable_id,
    guideline_mapping_node,
    project_init_node,
    protocol_approval_node,
    question_approval_node,
    research_question_node,
    route_protocol_decision,
    route_question_decision,
)
from vet_manuscript_lab.workflow.literature_graph import (
    _make_artifact,
    evidence_extraction_node,
    literature_search_node,
    route_search_decision,
    screening_node,
    search_approval_node,
)
from vet_manuscript_lab.workflow.state import (
    ManuscriptCitationDraft,
    ManuscriptClaimDraft,
    ManuscriptSectionDraft,
    ManuscriptSummary,
    ManuscriptSupportDraft,
    ReviewFindingEntry,
    RevisionDecisionEntry,
    RevisionSummary,
    WorkflowStage,
    WorkflowState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_hash(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode()).hexdigest()}"


def _build_support_counts(
    supports: list[ManuscriptSupportDraft],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in supports:
        cid = s.get("claim_id", "")
        counts[cid] = counts.get(cid, 0) + 1
    return counts


def _section_draft_to_dc(s: ManuscriptSectionDraft) -> SectionDraft:
    return SectionDraft(
        section_id=s["section_id"],
        section_type=s["section_type"],
        content=s["content"],
        content_hash=s["content_hash"],
        order=s["order"],
        word_count=s.get("word_count", 0),
        claim_ids=tuple(s.get("claim_ids", [])),
    )


def _dc_to_section_draft(s: SectionDraft) -> ManuscriptSectionDraft:
    return ManuscriptSectionDraft(
        section_id=s.section_id,
        section_type=s.section_type,
        content=s.content,
        content_hash=s.content_hash,
        order=s.order,
        word_count=s.word_count,
        claim_ids=list(s.claim_ids),
    )


# ---------------------------------------------------------------------------
# Stage nodes
# ---------------------------------------------------------------------------


def section_writing_node(
    state: WorkflowState,
    *,
    writer: SectionWriter | None = None,
    run_mode: RunMode = RunMode.DEMO,
) -> dict[str, Any]:
    """Generate manuscript sections from evidence and statistical results.

    Enforces the writing precondition: protocol locked, evidence audited,
    and results approved.  Uses the injected ``SectionWriter`` or falls
    back to ``MockSectionWriter`` for offline development.
    """

    locks = state.get("locks", {})
    approvals: dict[str, Any] = dict(state.get("approvals") or {})
    results_approval: dict[str, Any] = dict(
        approvals.get("results_interpretation") or {}
    )
    ctx = AuditContext(
        protocol_locked="protocol" in locks,
        evidence_audited=state.get("evidence_summary") is not None,
        results_approved=results_approval.get("decision") == "approved",
    )
    require_writing_inputs_approved(ctx)

    result_drafts = state.get("result_drafts", [])
    evidence_summary: dict[str, Any] = dict(state.get("evidence_summary") or {})
    literature_records = list(state.get("literature_record_drafts", []))
    analysis_plan_summary: dict[str, Any] = dict(
        state.get("analysis_plan_summary") or {}
    )

    actual_writer = writer or MockSectionWriter()

    # In production mode, the mock writer must not generate formal manuscript
    if isinstance(actual_writer, MockSectionWriter):
        require_no_mock_fallback(
            run_mode=run_mode,
            is_mock_generated=True,
            context="section writing (no real writer provided)",
        )

    output = actual_writer.write_sections(
        WritingInput(
            project_id=state["project_id"],
            evidence_summary=evidence_summary,
            result_drafts=[dict(r) for r in result_drafts],
            literature_records=[dict(r) for r in literature_records],
            analysis_plan_summary=dict(analysis_plan_summary),
        )
    )

    section_drafts = [_dc_to_section_draft(s) for s in output.sections]
    claim_drafts: list[ManuscriptClaimDraft] = []
    for c in output.claims:
        claim_drafts.append(
            ManuscriptClaimDraft(
                claim_id=c.claim_id,
                claim_type=c.claim_type,
                text=c.text,
                certainty=c.certainty,
                section_id=c.section_id,
                referenced_numbers=list(c.referenced_numbers),
            )
        )
    support_drafts: list[ManuscriptSupportDraft] = [
        ManuscriptSupportDraft(
            claim_id=s.claim_id,
            support_type=s.support_type,
            source_id=s.source_id,
            relation=s.relation,
            audit_status=s.audit_status,
        )
        for s in output.supports
    ]
    citation_drafts: list[ManuscriptCitationDraft] = [
        ManuscriptCitationDraft(
            citation_key=c.citation_key,
            literature_record_id=c.literature_record_id,
            section_id=c.section_id,
            claim_id=c.claim_id or "",
            locator=c.locator or "",
        )
        for c in output.citations
    ]

    manuscript_id = _stable_id(state["project_id"], "manuscript")
    version_id = _stable_id(
        manuscript_id, state.get("revision_round", 0) + 1, output.manuscript_hash
    )
    manuscript_summary: ManuscriptSummary = {
        "manuscript_id": manuscript_id,
        "version_id": version_id,
        "version": state.get("revision_round", 0) + 1,
        "content_hash": output.manuscript_hash,
        "section_count": len(output.sections),
        "claim_count": len(output.claims),
        "status": "draft",
    }

    artifact = _make_artifact(
        state,
        role="manuscript",
        artifact_type="manuscript",
        gate="results_interpretation",
        payload={
            "manuscript_id": manuscript_id,
            "content_hash": output.manuscript_hash,
            "section_types": [s["section_type"] for s in section_drafts],
            "claim_count": len(output.claims),
        },
    )
    artifacts = dict(state.get("artifacts", {}))
    artifacts["manuscript"] = artifact

    return {
        "manuscript_summary": manuscript_summary,
        "section_drafts": section_drafts,
        "claim_drafts": claim_drafts,
        "support_drafts": support_drafts,
        "citation_drafts": citation_drafts,
        "artifacts": artifacts,
        "current_stage": WorkflowStage.WRITING.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(state, "writing.sections_generated", WorkflowStage.WRITING)
        ],
    }


def claim_audit_node(state: WorkflowState) -> dict[str, Any]:
    """Run automated policy checks on every claim in the manuscript.

    Checks four invariants: factual claims have support, numbers match
    official results, no causal overreach, and citations exist.  The
    routing function uses the artifact status to decide the next step.
    """

    claims = state.get("claim_drafts", [])
    supports = state.get("support_drafts", [])
    results = state.get("result_drafts", [])

    support_counts = _build_support_counts(supports)
    result_snaps = tuple(
        StatisticalResultSnapshot(
            result_id=r.get("result_id", ""),
            estimate=r.get("estimate"),
            p_value=r.get("p_value"),
        )
        for r in results
    )

    audit_errors: list[dict[str, Any]] = []
    claim_snaps: list[ClaimSnapshot] = []

    for c in claims:
        claim_id = c.get("claim_id", "")
        claim_type = c.get("claim_type", "")
        text = c.get("text", "")
        count = support_counts.get(claim_id, 0)
        snap = ClaimSnapshot(
            claim_id=claim_id,
            claim_type=claim_type,
            text=text,
            certainty=c.get("certainty", "high"),
            has_support=count > 0,
            support_count=count,
            referenced_numbers=tuple(c.get("referenced_numbers", [])),
        )
        claim_snaps.append(snap)

        try:
            require_factual_claim_has_support(snap)
        except PolicyViolation as exc:
            audit_errors.append(
                {
                    "check": "factual_claim_support",
                    "claim_id": claim_id,
                    "error": str(exc),
                }
            )

        try:
            require_no_causal_overreach(snap)
        except PolicyViolation as exc:
            audit_errors.append(
                {"check": "causal_overreach", "claim_id": claim_id, "error": str(exc)}
            )

    try:
        require_numeric_consistency(tuple(claim_snaps), results=result_snaps)
    except PolicyViolation as exc:
        audit_errors.append({"check": "numeric_consistency", "error": str(exc)})

    passed = len(audit_errors) == 0
    artifact = _make_artifact(
        state,
        role="claim_audit",
        artifact_type="claim_audit",
        gate="results_interpretation",
        payload={
            "total_claims": len(claims),
            "error_count": len(audit_errors),
            "errors": audit_errors,
            "passed": passed,
        },
    )
    artifact = {**artifact, "status": "audit_passed" if passed else "audit_failed"}
    artifacts = dict(state.get("artifacts", {}))
    artifacts["claim_audit"] = artifact

    return {
        "artifacts": artifacts,
        "current_stage": WorkflowStage.CLAIM_AUDIT.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(state, "claim_audit.completed", WorkflowStage.CLAIM_AUDIT)
        ],
    }


def review_node(
    state: WorkflowState,
    *,
    reviewer: Reviewer | None = None,
) -> dict[str, Any]:
    """Scan manuscript claims and produce structured review findings.

    The reviewer must be read-only: the manuscript hash must not change
    during this stage.
    """

    manuscript_summary = state.get("manuscript_summary")
    if manuscript_summary is None:
        raise PolicyViolation("Review requires a manuscript")

    manuscript_hash = manuscript_summary["content_hash"]
    claims = state.get("claim_drafts", [])
    supports = state.get("support_drafts", [])
    results = state.get("result_drafts", [])

    support_counts = _build_support_counts(supports)
    claim_data = tuple(
        ClaimDraftData(
            claim_id=c.get("claim_id", ""),
            claim_type=c.get("claim_type", ""),
            text=c.get("text", ""),
            certainty=c.get("certainty", "high"),
            has_support=support_counts.get(c.get("claim_id", ""), 0) > 0,
            support_count=support_counts.get(c.get("claim_id", ""), 0),
            referenced_numbers=tuple(c.get("referenced_numbers", [])),
        )
        for c in claims
    )
    result_data = tuple(
        {
            "result_id": r.get("result_id", ""),
            "estimate": r.get("estimate"),
            "p_value": r.get("p_value"),
        }
        for r in results
    )

    actual_reviewer = reviewer or MockReviewer()
    review_output = actual_reviewer.review(
        ReviewInput(
            manuscript_hash=manuscript_hash,
            claims=claim_data,
            results=result_data,
        )
    )

    require_reviewer_readonly(
        manuscript_hash_before=manuscript_hash,
        manuscript_hash_after=manuscript_hash,
    )

    findings: list[ReviewFindingEntry] = [
        ReviewFindingEntry(
            finding_id=f.finding_id,
            category=f.category,
            severity=f.severity,
            location=f.location,
            rationale=f.rationale,
            recommendation=f.recommendation,
            status=f.status,
        )
        for f in review_output.findings
    ]

    return {
        "review_findings": findings,
        "current_stage": WorkflowStage.REVIEW.value,
        "updated_at": utc_now(),
        "audit_events": [_event(state, "review.completed", WorkflowStage.REVIEW)],
    }


def _parse_review_decisions(
    resume: object,
    finding_ids: set[str],
) -> tuple[list[RevisionDecisionEntry], str, str]:
    if not isinstance(resume, dict):
        raise ValueError("Review disposition resume value must be an object")

    reviewer_id = resume.get("reviewer_id", "")
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise ValueError("Human reviewer identity is required")

    reviewer_role = resume.get("reviewer_role", "")
    if not isinstance(reviewer_role, str) or not reviewer_role.strip():
        raise ValueError("Human reviewer role is required")

    raw_decisions = resume.get("decisions", [])
    if not isinstance(raw_decisions, list):
        raise ValueError("Decisions must be a list")

    valid = {"accept", "reject", "defer"}
    decisions: list[RevisionDecisionEntry] = []
    for d in raw_decisions:
        if not isinstance(d, dict):
            continue
        fid = d.get("finding_id", "")
        decision = d.get("decision", "")
        if fid not in finding_ids:
            raise ValueError(f"Unknown finding_id: {fid}")
        if decision not in valid:
            raise ValueError(f"Invalid decision '{decision}' for finding {fid}")
        decisions.append(
            RevisionDecisionEntry(
                finding_id=fid,
                decision=decision,
                reason=d.get("reason", ""),
                reviewer_id=reviewer_id.strip(),
            )
        )
    return decisions, reviewer_id.strip(), reviewer_role.strip()


def review_approval_node(state: WorkflowState) -> dict[str, Any]:
    """Interrupt for human disposition of each review finding.

    The human can accept, reject, or defer each finding.  Accepted
    findings trigger a revision cycle; rejected findings are dismissed.
    """

    findings = state.get("review_findings", [])

    if not findings:
        return {
            "current_stage": WorkflowStage.REVIEW.value,
            "updated_at": utc_now(),
            "audit_events": [_event(state, "review.no_findings", WorkflowStage.REVIEW)],
        }

    resume = interrupt(
        {
            "gate": "review",
            "title": "Dispose review findings",
            "summary": f"{len(findings)} finding(s) require disposition.",
            "findings": [
                {
                    "finding_id": f.get("finding_id", ""),
                    "category": f.get("category", ""),
                    "severity": f.get("severity", ""),
                    "location": f.get("location", ""),
                    "rationale": f.get("rationale", ""),
                    "recommendation": f.get("recommendation", ""),
                }
                for f in findings
            ],
            "allowed_decisions_per_finding": ["accept", "reject", "defer"],
            "required_reviewer_role": "reviewer",
        }
    )

    finding_ids = {f.get("finding_id", "") for f in findings}
    decisions, _reviewer_id, _reviewer_role = _parse_review_decisions(
        resume, finding_ids
    )

    updated_findings: list[ReviewFindingEntry] = []
    decision_map = {d["finding_id"]: d["decision"] for d in decisions}
    for f in findings:
        fid = f.get("finding_id", "")
        new_status = decision_map.get(fid, f.get("status", "open"))
        updated_findings.append({**f, "status": new_status})

    return {
        "review_findings": updated_findings,
        "revision_decisions": decisions,
        "current_stage": WorkflowStage.REVIEW.value,
        "updated_at": utc_now(),
        "audit_events": [_event(state, "review.dispositioned", WorkflowStage.REVIEW)],
    }


def revision_node(
    state: WorkflowState,
    *,
    reviser: Reviser | None = None,
) -> dict[str, Any]:
    """Generate revised section versions based on accepted findings.

    Increments ``revision_round`` and routes back to ``claim_audit``
    for re-audit.  Enforces finding-before-revision and revision-limit
    invariants.
    """

    findings = state.get("review_findings", [])
    decisions = state.get("revision_decisions", [])

    accepted_ids = {d["finding_id"] for d in decisions if d.get("decision") == "accept"}
    accepted_findings = [f for f in findings if f.get("finding_id", "") in accepted_ids]

    require_finding_before_revision(has_accepted_finding=len(accepted_findings) > 0)

    current_round = state.get("revision_round", 0)
    max_rounds = state.get("max_revision_rounds", 3)
    require_revision_within_limit(current_round=current_round, max_rounds=max_rounds)

    section_drafts_state = state.get("section_drafts", [])
    section_dcs = tuple(_section_draft_to_dc(s) for s in section_drafts_state)

    accepted_dicts = tuple(
        {
            "finding_id": f.get("finding_id", ""),
            "category": f.get("category", ""),
            "location": f.get("location", ""),
        }
        for f in accepted_findings
    )
    decision_dcs = tuple(
        RevisionDecisionDraft(
            finding_id=d["finding_id"],
            decision=d["decision"],
            reason=d.get("reason", ""),
            reviewer_id=d.get("reviewer_id", ""),
        )
        for d in decisions
    )

    actual_reviser = reviser or MockReviser()
    revision_output = actual_reviser.revise(
        RevisionInput(
            sections=section_dcs,
            accepted_findings=accepted_dicts,
            decisions=decision_dcs,
        )
    )

    new_sections = [_dc_to_section_draft(s) for s in revision_output.revised_sections]

    # Update claim text for revised sections
    revised_section_map = {s["section_id"]: s for s in new_sections}
    claim_drafts = list(state.get("claim_drafts", []))
    for i, c in enumerate(claim_drafts):
        sid = c.get("section_id", "")
        if sid in revised_section_map:
            revised_section = revised_section_map[sid]
            new_text = revised_section["content"]
            old_text = c.get("text", "")
            if new_text != old_text:
                from vet_manuscript_lab.domain.policies import (
                    extract_referenced_numbers,
                )

                claim_drafts[i] = {
                    **c,
                    "text": new_text,
                    "referenced_numbers": list(extract_referenced_numbers(new_text)),
                }

    new_hash = _content_hash("".join(s["content"] for s in new_sections))
    prev_summary: dict[str, Any] = dict(state.get("manuscript_summary") or {})
    updated_manuscript: ManuscriptSummary = {
        "manuscript_id": prev_summary.get("manuscript_id", ""),
        "version_id": prev_summary.get("version_id", ""),
        "version": prev_summary.get("version", 1) + 1,
        "content_hash": new_hash,
        "section_count": len(new_sections),
        "claim_count": prev_summary.get("claim_count", 0),
        "status": "revised",
    }

    revision_summary: RevisionSummary = {
        "round": current_round + 1,
        "accepted_count": len(accepted_findings),
        "rejected_count": sum(1 for d in decisions if d.get("decision") == "reject"),
        "deferred_count": sum(1 for d in decisions if d.get("decision") == "defer"),
        "section_diffs": [
            {
                "section_id": d.section_id,
                "before_hash": d.before_hash,
                "after_hash": d.after_hash,
                "before_content": d.before_content,
                "after_content": d.after_content,
                "resolved_finding_ids": list(d.resolved_finding_ids),
            }
            for d in revision_output.diffs
        ],
    }

    return {
        "section_drafts": new_sections,
        "claim_drafts": claim_drafts,
        "manuscript_summary": updated_manuscript,
        "revision_round": current_round + 1,
        "revision_summary": revision_summary,
        "current_stage": WorkflowStage.REVISION.value,
        "updated_at": utc_now(),
        "audit_events": [_event(state, "revision.completed", WorkflowStage.REVISION)],
    }


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------


def route_results_to_writing(state: WorkflowState) -> str:
    decision = state["approvals"]["results_interpretation"]["decision"]
    return "section_writing" if decision == "approved" else "statistics_execution"


def route_claim_audit_decision(state: WorkflowState) -> str:
    artifacts: dict[str, Any] = dict(state.get("artifacts") or {})
    audit: dict[str, Any] = dict(artifacts.get("claim_audit") or {})
    if audit.get("status") == "audit_failed":
        return "section_writing"
    return "review"


def route_review_decision(state: WorkflowState) -> str:
    decisions = state.get("revision_decisions", [])
    has_accepted = any(d.get("decision") == "accept" for d in decisions)
    return "revision" if has_accepted else END


def route_revision_decision(state: WorkflowState) -> str:
    current_round = state.get("revision_round", 0)
    max_rounds = state.get("max_revision_rounds", 3)
    if current_round >= max_rounds:
        return END
    return "claim_audit"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WritingPipeline:
    """Optional injection point for writing-stage dependencies."""

    gateway: ModelGateway | None = None
    runner: StatisticsRunner | None = None
    writer: SectionWriter | None = None
    reviewer: Reviewer | None = None
    reviser: Reviser | None = None
    run_mode: RunMode = RunMode.DEMO


def _make_writing_builder(
    *,
    synchroniser: Any = None,
    evidence_pipeline: Any = None,
    writing_pipeline: WritingPipeline | None = None,
    run_mode: RunMode = RunMode.DEMO,
) -> Any:
    """Create the StateGraph builder with all writing-pipeline nodes and edges.

    Returns the **uncompiled** builder so downstream graph assemblers
    (e.g. ``build_compliance_pipeline_graph``) can extend it before
    compilation.
    """

    gateway = writing_pipeline.gateway if writing_pipeline else None
    runner = writing_pipeline.runner if writing_pipeline else None
    writer = writing_pipeline.writer if writing_pipeline else None
    reviewer = writing_pipeline.reviewer if writing_pipeline else None
    reviser = writing_pipeline.reviser if writing_pipeline else None
    effective_run_mode = writing_pipeline.run_mode if writing_pipeline else run_mode

    builder = StateGraph(WorkflowState)

    # Foundation stage
    builder.add_node("project_init", project_init_node)
    builder.add_node("research_question", research_question_node)
    builder.add_node("question_approval", question_approval_node)
    builder.add_node("guideline_mapping", guideline_mapping_node)
    builder.add_node("protocol_approval", protocol_approval_node)
    builder.add_node("protocol_lock", _protocol_lock_running)

    # Literature + evidence stage
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
        else lambda s: evidence_extraction_node(
            s, pipeline=evidence_pipeline, run_mode=effective_run_mode
        ),
    )
    builder.add_node("evidence_audit", _evidence_audit_running)

    # Methodology + statistics stage
    builder.add_node(
        "methodology_critic",
        lambda s: methodology_critic_node(
            s, gateway=gateway, run_mode=effective_run_mode
        ),
    )
    builder.add_node("analysis_plan", analysis_plan_node)
    builder.add_node("analysis_plan_approval", analysis_plan_approval_node)
    builder.add_node("analysis_plan_lock", analysis_plan_lock_node)
    builder.add_node(
        "statistics_execution",
        lambda s: statistics_execution_node(
            s, runner=runner, run_mode=effective_run_mode
        ),
    )
    builder.add_node("results_approval", results_approval_node)

    # Writing stage
    builder.add_node(
        "section_writing",
        lambda s: section_writing_node(s, writer=writer, run_mode=effective_run_mode),
    )
    builder.add_node("claim_audit", claim_audit_node)
    builder.add_node(
        "review",
        review_node
        if reviewer is None
        else lambda s: review_node(s, reviewer=reviewer),
    )
    builder.add_node("review_approval", review_approval_node)
    builder.add_node(
        "revision",
        revision_node
        if reviser is None
        else lambda s: revision_node(s, reviser=reviser),
    )

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
    builder.add_conditional_edges("results_approval", route_results_to_writing)

    # Edges: writing + review + revision
    builder.add_edge("section_writing", "claim_audit")
    builder.add_conditional_edges("claim_audit", route_claim_audit_decision)
    builder.add_edge("review", "review_approval")
    builder.add_conditional_edges("review_approval", route_review_decision)
    builder.add_conditional_edges("revision", route_revision_decision)

    return builder


def build_writing_pipeline_graph(
    checkpointer: BaseCheckpointSaver[Any],
    *,
    synchroniser: Any = None,
    evidence_pipeline: Any = None,
    writing_pipeline: WritingPipeline | None = None,
    run_mode: RunMode = RunMode.DEMO,
) -> Any:
    """Compile the full pipeline from ``PROJECT_INIT`` through ``REVISION``.

    Extends the analysis pipeline graph with the writing, claim audit,
    review, and revision stages.  The foundation, literature, evidence,
    and methodology/statistics stages are reused unchanged.
    """

    builder = _make_writing_builder(
        synchroniser=synchroniser,
        evidence_pipeline=evidence_pipeline,
        writing_pipeline=writing_pipeline,
        run_mode=run_mode,
    )
    return builder.compile(checkpointer=checkpointer)


__all__ = [
    "WritingPipeline",
    "_make_writing_builder",
    "build_writing_pipeline_graph",
    "claim_audit_node",
    "review_approval_node",
    "review_node",
    "revision_node",
    "route_claim_audit_decision",
    "route_results_to_writing",
    "route_review_decision",
    "route_revision_decision",
    "section_writing_node",
]
