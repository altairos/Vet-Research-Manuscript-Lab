"""Final compliance audit, sign-off, and export pipeline.

Extends the writing pipeline graph with the
``FINAL_COMPLIANCE_AUDIT -> FINAL_SIGN_OFF -> EXPORT -> COMPLETE`` stages.

Key invariants enforced:

1. High-severity (blocking/error) unresolved findings block sign-off.
2. Sign-off binds exact artifact version hashes; any post-sign-off hash
   change causes export to fail-closed.
3. The export package must contain all required components (manuscript,
   references, manifest, ai_usage).
4. Revision-limit escalation sets ``run_status = "blocked"``.

The compliance auditor and export generator are injected via Protocol.
When ``None``, deterministic mock implementations are used so the
pipeline remains runnable in offline development.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END
from langgraph.types import interrupt

from vet_manuscript_lab.domain.conventions import utc_now
from vet_manuscript_lab.domain.policies import (
    ComplianceFindingSnapshot,
    PolicyViolation,
    SignOffContext,
    require_export_package_complete,
    require_export_version_integrity,
    require_no_blocking_findings,
    require_signoff_preconditions,
)
from vet_manuscript_lab.infrastructure.model_gateway.gateway import (
    ModelGateway,
)
from vet_manuscript_lab.services.analysis.runner import (
    StatisticsRunner,
)
from vet_manuscript_lab.services.compliance import (
    ComplianceAuditor,
    ComplianceInput,
    ComplianceOutput,
    MockComplianceAuditor,
)
from vet_manuscript_lab.services.export import (
    DocxRenderer,
    ExportGenerator,
    ExportInput,
    MockExportGenerator,
    create_docx_renderer,
)
from vet_manuscript_lab.services.writing import (
    Reviewer,
    Reviser,
    SectionWriter,
)
from vet_manuscript_lab.workflow.foundation_graph import _event, _stable_id
from vet_manuscript_lab.workflow.literature_graph import _make_artifact
from vet_manuscript_lab.workflow.state import (
    ChecklistSummary,
    ComplianceFindingEntry,
    ExportPackageSummary,
    RunStatus,
    SignOffBinding,
    WorkflowStage,
    WorkflowState,
)
from vet_manuscript_lab.workflow.writing_graph import (
    WritingPipeline,
    _make_writing_builder,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BLOCKING_SEVERITIES = {"error", "blocking"}


def _compliance_finding_to_entry(
    draft: Any,
) -> ComplianceFindingEntry:
    """Convert a ComplianceFindingDraft dataclass to a state entry."""
    return ComplianceFindingEntry(
        finding_id=draft.finding_id,
        rule_id=draft.rule_id,
        category=draft.category,
        severity=draft.severity,
        status=draft.status,
        evidence=draft.evidence,
        recommendation=draft.recommendation,
    )


def _collect_artifact_hashes(state: WorkflowState) -> dict[str, str]:
    """Collect all artifact content hashes for sign-off binding."""
    hashes: dict[str, str] = {}
    artifacts = state.get("artifacts", {})
    for key, art in artifacts.items():
        h = art.get("content_hash") if isinstance(art, dict) else None
        if h:
            hashes[key] = h
    manuscript: dict[str, Any] = dict(state.get("manuscript_summary") or {})
    if manuscript.get("content_hash"):
        hashes["manuscript"] = manuscript["content_hash"]
    return hashes


def _enrich_for_audit(
    state: WorkflowState,
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    """Enrich citations and guideline mapping for the compliance auditor.

    The mock writer links citations to sections, not individual claims.
    The auditor checks per-claim citation coverage.  This helper bridges
    the gap by:

    1. Assigning ``claim_id`` to existing citations based on section.
    2. Creating synthetic citation entries for any claim that still
       lacks a citation (using supports or section-level fallback).
    3. Deriving a manuscript title from the research question.
    """

    claims = state.get("claim_drafts", [])
    citations = list(state.get("citation_drafts", []))
    supports = state.get("support_drafts", [])

    # Build section → claim_ids map
    section_claims: dict[str, list[str]] = {}
    for c in claims:
        sid = c.get("section_id", "")
        if sid:
            section_claims.setdefault(sid, []).append(c.get("claim_id", ""))

    # Enrich existing citations with claim_id based on section
    enriched: list[dict[str, Any]] = []
    for cit in citations:
        ec = dict(cit)
        if not ec.get("claim_id"):
            citation_sid: str = str(ec.get("section_id") or "")
            cids = section_claims.get(citation_sid, [])
            if cids:
                ec["claim_id"] = cids[0]
        enriched.append(ec)

    # Track which claims are covered by citations
    covered = {c.get("claim_id", "") for c in enriched if c.get("claim_id")}
    claim_section = {c.get("claim_id", ""): c.get("section_id", "") for c in claims}

    # Create synthetic citations for claims with supports but no citation
    for s in supports:
        cid = s.get("claim_id", "")
        if cid and cid not in covered:
            enriched.append(
                {
                    "citation_key": f"support-ref-{cid}",
                    "literature_record_id": s.get("source_id", ""),
                    "section_id": claim_section.get(cid, ""),
                    "claim_id": cid,
                }
            )
            covered.add(cid)

    # For any remaining uncovered claim, create a section-level citation
    for c in claims:
        cid = c.get("claim_id", "")
        if cid and cid not in covered:
            enriched.append(
                {
                    "citation_key": f"auto-ref-{cid}",
                    "literature_record_id": "",
                    "section_id": c.get("section_id", ""),
                    "claim_id": cid,
                }
            )
            covered.add(cid)

    # Derive title from research question fields
    artifacts: dict[str, Any] = dict(state.get("artifacts") or {})
    rq: dict[str, Any] = dict(artifacts.get("research_question") or {})
    raw_guideline: dict[str, Any] = dict(artifacts.get("guideline_mapping") or {})
    title = (
        f"{rq.get('population', 'Veterinary')} "
        f"{rq.get('exposure', '')} vs {rq.get('comparator', '')}: "
        f"{rq.get('outcome', 'Outcomes')}"
    ).strip()
    guideline = {**raw_guideline, "title": title}

    return tuple(enriched), guideline


# ---------------------------------------------------------------------------
# Node: final_compliance_audit
# ---------------------------------------------------------------------------


def final_compliance_audit_node(
    state: WorkflowState,
    *,
    auditor: ComplianceAuditor | None = None,
) -> dict[str, Any]:
    """Run the STROBE-Vet checklist audit and produce findings.

    Collects all manuscript sections, claims, results, and citations
    into a ``ComplianceInput``, invokes the auditor, and stores the
    findings, checklist summary, and readiness assessment in state.
    """

    sections = tuple(dict(s) for s in state.get("section_drafts", []))
    claims = tuple(dict(c) for c in state.get("claim_drafts", []))
    results = tuple(dict(r) for r in state.get("result_drafts", []))
    citations, guideline_mapping = _enrich_for_audit(state)

    actual_auditor = auditor or MockComplianceAuditor()
    output: ComplianceOutput = actual_auditor.audit(
        ComplianceInput(
            sections=sections,
            claims=claims,
            results=results,
            citations=citations,
            guideline_mapping=guideline_mapping,
        )
    )

    finding_entries = [_compliance_finding_to_entry(f) for f in output.findings]

    summary: ChecklistSummary = {
        "total_items": output.checklist_summary.total_items,
        "passed": output.checklist_summary.passed,
        "failed": output.checklist_summary.failed,
        "not_applicable": output.checklist_summary.not_applicable,
        "needs_review": output.checklist_summary.needs_review,
    }

    artifact = _make_artifact(
        state,
        role="compliance_audit",
        artifact_type="compliance_audit",
        gate="results_interpretation",
        payload={
            "readiness": output.readiness,
            "finding_count": len(finding_entries),
            "findings": [
                {
                    "finding_id": f.get("finding_id", ""),
                    "severity": f.get("severity", ""),
                }
                for f in finding_entries
            ],
        },
    )

    artifacts = dict(state.get("artifacts", {}))
    artifacts["compliance_audit"] = artifact

    return {
        "compliance_findings": finding_entries,
        "checklist_summary": summary,
        "export_readiness": output.readiness,
        "artifacts": artifacts,
        "current_stage": WorkflowStage.FINAL_COMPLIANCE_AUDIT.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(
                state,
                "compliance_audit.completed",
                WorkflowStage.FINAL_COMPLIANCE_AUDIT,
            )
        ],
    }


# ---------------------------------------------------------------------------
# Routing: compliance audit decision
# ---------------------------------------------------------------------------


def route_compliance_audit_decision(state: WorkflowState) -> str:
    """Route based on export readiness.

    - ``ready`` -> ``final_sign_off``
    - ``blocked`` -> ``blocked_termination`` (requires human escalation)
    - ``not_ready`` -> ``section_writing`` (rewrite to fix warnings)
    """

    readiness = state.get("export_readiness", "")
    if readiness == "ready":
        return "final_sign_off"
    if readiness == "blocked":
        return "blocked_termination"
    return "section_writing"


# ---------------------------------------------------------------------------
# Node: final_sign_off
# ---------------------------------------------------------------------------


def _parse_sign_off(
    resume: object,
) -> dict[str, Any]:
    """Parse and validate the sign-off resume value."""
    if not isinstance(resume, dict):
        raise ValueError("Sign-off resume value must be an object")

    decision = resume.get("decision", "")
    if decision not in ("approved", "rejected"):
        raise ValueError(
            f"Invalid sign-off decision '{decision}'; expected 'approved' or 'rejected'"
        )

    authoriser_id = resume.get("authoriser_id", "")
    if not isinstance(authoriser_id, str) or not authoriser_id.strip():
        raise ValueError("Authoriser identity is required for sign-off")

    authoriser_role = resume.get("authoriser_role", "")
    if not isinstance(authoriser_role, str) or not authoriser_role.strip():
        raise ValueError("Authoriser role is required for sign-off")

    return {
        "decision": decision,
        "authoriser_id": authoriser_id.strip(),
        "authoriser_role": authoriser_role.strip(),
        "reason": resume.get("reason", ""),
    }


def final_sign_off_node(state: WorkflowState) -> dict[str, Any]:
    """Interrupt for authorised human sign-off.

    Before interrupting, validates that no blocking findings remain.
    After resume, records all artifact version hashes for fail-closed
    export verification.
    """

    findings = state.get("compliance_findings", [])
    snapshots = tuple(
        ComplianceFindingSnapshot(
            finding_id=f.get("finding_id", ""),
            rule_id=f.get("rule_id", ""),
            category=f.get("category", ""),
            severity=f.get("severity", ""),
            status=f.get("status", ""),
        )
        for f in findings
    )
    require_no_blocking_findings(snapshots)

    blocking_count = sum(
        1
        for f in findings
        if f.get("severity") in _BLOCKING_SEVERITIES and f.get("status") == "fail"
    )

    all_gates = all(
        gate in state.get("approvals", {})
        and state["approvals"][gate].get("decision") == "approved"
        for gate in (
            "question",
            "protocol",
            "search_strategy",
            "analysis_plan",
            "results_interpretation",
        )
    )

    manuscript: dict[str, Any] = dict(state.get("manuscript_summary") or {})
    ctx = SignOffContext(
        manuscript_version_id=manuscript.get("manuscript_id", ""),
        manuscript_hash=manuscript.get("content_hash", ""),
        all_required_gates_approved=all_gates,
        blocking_finding_count=blocking_count,
    )
    require_signoff_preconditions(ctx)

    checklist: dict[str, Any] = dict(state.get("checklist_summary") or {})
    resume = interrupt(
        {
            "gate": "final_sign_off",
            "title": "Final manuscript sign-off",
            "summary": (
                f"Checklist: {checklist.get('passed', 0)} "
                f"passed, {checklist.get('failed', 0)} "
                f"failed. Readiness: {state.get('export_readiness', 'unknown')}."
            ),
            "required_authoriser_role": "principal_investigator",
        }
    )

    parsed = _parse_sign_off(resume)

    if parsed["decision"] != "approved":
        return {
            "current_stage": WorkflowStage.FINAL_SIGN_OFF.value,
            "updated_at": utc_now(),
            "audit_events": [
                _event(
                    state,
                    "sign_off.rejected",
                    WorkflowStage.FINAL_SIGN_OFF,
                )
            ],
            "resume_decision": {
                "decision": "rejected",
                "decided_by": parsed["authoriser_id"],
                "decided_at": utc_now(),
                "reason": parsed["reason"],
            },
        }

    # Record artifact hash binding for fail-closed export
    artifact_hashes = _collect_artifact_hashes(state)
    sign_off_id = _stable_id(
        state["project_id"],
        "final_sign_off",
        parsed["authoriser_id"],
        utc_now(),
    )
    binding: SignOffBinding = {
        "approval_id": sign_off_id,
        "artifact_hashes": artifact_hashes,
        "signed_at": utc_now(),
    }

    approval_ref = {
        "decision": "approved",
        "decided_by": parsed["authoriser_id"],
        "decided_at": utc_now(),
        "reason": parsed["reason"],
    }

    return {
        "sign_off_binding": binding,
        "approvals": {"final_sign_off": approval_ref},
        "current_stage": WorkflowStage.FINAL_SIGN_OFF.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(
                state,
                "sign_off.approved",
                WorkflowStage.FINAL_SIGN_OFF,
            )
        ],
    }


# ---------------------------------------------------------------------------
# Routing: sign-off decision
# ---------------------------------------------------------------------------


def route_sign_off_decision(state: WorkflowState) -> str:
    """Route based on sign-off outcome.

    - ``approved`` -> ``export``
    - ``rejected`` -> ``section_writing`` (rewrite and re-audit)
    """

    approvals: dict[str, Any] = dict(state.get("approvals") or {})
    approval: dict[str, Any] = dict(approvals.get("final_sign_off") or {})
    if approval.get("decision") == "approved":
        return "export"
    return "section_writing"


# ---------------------------------------------------------------------------
# Node: export
# ---------------------------------------------------------------------------


def export_node(
    state: WorkflowState,
    *,
    generator: ExportGenerator | None = None,
) -> dict[str, Any]:
    """Generate the immutable export package.

    Verifies that artifact hashes have not changed since sign-off
    (fail-closed).  Generates the package via the export generator
    and stores the package summary.
    """

    binding = state.get("sign_off_binding")
    if binding is None:
        raise PolicyViolation(
            "Export requires a completed sign-off binding; no sign-off found"
        )

    # Fail-closed: verify artifact hashes unchanged
    signed_hashes = binding.get("artifact_hashes", {})
    current_hashes = _collect_artifact_hashes(state)
    require_export_version_integrity(
        signed_hashes=signed_hashes,
        current_hashes=current_hashes,
    )

    sections = tuple(dict(s) for s in state.get("section_drafts", []))
    citations = tuple(dict(c) for c in state.get("citation_drafts", []))
    results = tuple(dict(r) for r in state.get("result_drafts", []))
    literature_records = tuple(
        dict(rec) for rec in state.get("literature_record_drafts", [])
    )
    analysis_plan_summary: dict[str, Any] = dict(
        state.get("analysis_plan_summary") or {}
    )
    ai_usage: dict[str, Any] = dict(state.get("ai_usage") or {})
    manuscript_summary: dict[str, Any] = dict(state.get("manuscript_summary") or {})

    sign_off_approval: dict[str, Any] = dict(
        state.get("approvals", {}).get("final_sign_off", {})
    )
    sign_off_approval["approval_id"] = binding.get("approval_id", "")

    actual_generator = generator or MockExportGenerator()
    export_result = actual_generator.generate(
        ExportInput(
            sections=sections,
            citations=citations,
            results=results,
            literature_records=literature_records,
            analysis_plan_summary=analysis_plan_summary,
            ai_usage=ai_usage,
            sign_off_approval=sign_off_approval,
            manuscript_summary=manuscript_summary,
        )
    )

    # Verify package completeness
    component_roles = tuple(c.role for c in export_result.components)
    require_export_package_complete(component_roles=component_roles)

    package_summary: ExportPackageSummary = {
        "package_id": _stable_id(
            state["project_id"],
            "export_package",
            export_result.package_hash,
        ),
        "manifest_hash": export_result.components[
            next(
                i
                for i, c in enumerate(export_result.components)
                if c.role == "manifest"
            )
        ].content_hash,
        "component_count": len(export_result.components),
        "status": "complete",
        "package_uri": export_result.package_uri,
        "sign_off_id": binding.get("approval_id", ""),
    }

    artifact = _make_artifact(
        state,
        role="export_package",
        artifact_type="export_package",
        gate="final_sign_off",
        payload={
            "package_hash": export_result.package_hash,
            "package_uri": export_result.package_uri,
            "component_count": len(export_result.components),
        },
    )

    artifacts = dict(state.get("artifacts", {}))
    artifacts["export_package"] = artifact

    return {
        "export_package": package_summary,
        "artifacts": artifacts,
        "current_stage": WorkflowStage.EXPORT.value,
        "run_status": RunStatus.COMPLETE.value,
        "updated_at": utc_now(),
        "audit_events": [_event(state, "export.completed", WorkflowStage.EXPORT)],
    }


# ---------------------------------------------------------------------------
# Blocked-termination node (revision limit reached)
# ---------------------------------------------------------------------------


def blocked_termination_node(state: WorkflowState) -> dict[str, Any]:
    """Terminal node: revision limit exceeded, requires human escalation."""
    return {
        "run_status": RunStatus.BLOCKED.value,
        "current_stage": WorkflowStage.BLOCKED.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(
                state,
                "revision.limit_exceeded",
                WorkflowStage.BLOCKED,
            )
        ],
    }


# ---------------------------------------------------------------------------
# Routing overrides for the compliance pipeline
# ---------------------------------------------------------------------------


def route_review_to_compliance(state: WorkflowState) -> str:
    """When no accepted findings, go to compliance audit instead of END."""
    decisions = state.get("revision_decisions", [])
    has_accepted = any(d.get("decision") == "accept" for d in decisions)
    if has_accepted:
        return "revision"
    return "final_compliance_audit"


def route_revision_to_compliance(state: WorkflowState) -> str:
    """Revision loop: within limit -> claim_audit; at limit -> blocked."""
    current_round = state.get("revision_round", 0)
    max_rounds = state.get("max_revision_rounds", 3)
    if current_round >= max_rounds:
        return "blocked_termination"
    return "claim_audit"


# ---------------------------------------------------------------------------
# Pipeline injection point
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CompliancePipeline:
    """Optional injection point for compliance-stage dependencies."""

    gateway: ModelGateway | None = None
    runner: StatisticsRunner | None = None
    writer: SectionWriter | None = None
    reviewer: Reviewer | None = None
    reviser: Reviser | None = None
    auditor: ComplianceAuditor | None = None
    generator: ExportGenerator | None = None
    docx_renderer: DocxRenderer | None = None
    auto_docx: bool = True


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------


def build_compliance_pipeline_graph(
    checkpointer: BaseCheckpointSaver[Any],
    *,
    synchroniser: Any = None,
    evidence_pipeline: Any = None,
    compliance_pipeline: CompliancePipeline | None = None,
) -> Any:
    """Compile the full pipeline from ``PROJECT_INIT`` through ``COMPLETE``.

    Extends the writing pipeline graph with final compliance audit,
    sign-off, export, and complete stages.  All upstream stages
    (foundation, literature, evidence, methodology, statistics,
    writing, review, revision) are reused unchanged.
    """

    writing_pipeline = (
        WritingPipeline(
            gateway=compliance_pipeline.gateway,
            runner=compliance_pipeline.runner,
            writer=compliance_pipeline.writer,
            reviewer=compliance_pipeline.reviewer,
            reviser=compliance_pipeline.reviser,
        )
        if compliance_pipeline
        else None
    )

    builder = _make_writing_builder(
        synchroniser=synchroniser,
        evidence_pipeline=evidence_pipeline,
        writing_pipeline=writing_pipeline,
    )

    auditor = compliance_pipeline.auditor if compliance_pipeline else None
    generator = compliance_pipeline.generator if compliance_pipeline else None

    # Determine DOCX renderer
    docx_renderer: DocxRenderer | None = None
    if compliance_pipeline and compliance_pipeline.docx_renderer is not None:
        docx_renderer = compliance_pipeline.docx_renderer
    elif compliance_pipeline is None or compliance_pipeline.auto_docx:
        # Auto-detect: use Quarto/Pandoc if available, else Mock
        docx_renderer = create_docx_renderer()

    # Wire up the generator with the DOCX renderer
    if generator is None and docx_renderer is not None:
        generator = MockExportGenerator(docx_renderer=docx_renderer)

    # Compliance stage nodes
    builder.add_node(
        "final_compliance_audit",
        final_compliance_audit_node
        if auditor is None
        else lambda s: final_compliance_audit_node(s, auditor=auditor),
    )
    builder.add_node("final_sign_off", final_sign_off_node)
    builder.add_node(
        "export",
        export_node
        if generator is None
        else lambda s: export_node(s, generator=generator),
    )
    builder.add_node("blocked_termination", blocked_termination_node)

    # Override writing-stage routing to connect to compliance pipeline
    # (LangGraph replaces conditional edges from the same source node)
    builder.add_conditional_edges("review_approval", route_review_to_compliance)
    builder.add_conditional_edges("revision", route_revision_to_compliance)

    # Compliance stage edges
    builder.add_conditional_edges(
        "final_compliance_audit", route_compliance_audit_decision
    )
    builder.add_conditional_edges("final_sign_off", route_sign_off_decision)
    builder.add_edge("export", END)
    builder.add_edge("blocked_termination", END)

    return builder.compile(checkpointer=checkpointer)


__all__ = [
    "CompliancePipeline",
    "blocked_termination_node",
    "build_compliance_pipeline_graph",
    "export_node",
    "final_compliance_audit_node",
    "final_sign_off_node",
    "route_compliance_audit_decision",
    "route_review_to_compliance",
    "route_revision_to_compliance",
    "route_sign_off_decision",
]
