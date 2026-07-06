"""Checkpointed mock Foundation graph through protocol lock."""

from __future__ import annotations

import json
import uuid
from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from vet_manuscript_lab.domain.conventions import sha256_bytes, utc_now
from vet_manuscript_lab.workflow.state import (
    ApprovalRef,
    ArtifactRef,
    LockRef,
    RunStatus,
    WorkflowStage,
    WorkflowState,
    require_approved_gate,
)

_NAMESPACE = uuid.UUID("a3e79b2a-f277-41df-b53c-538724fabd8f")
_DECISIONS = frozenset({"approved", "rejected", "changes_requested"})


def _stable_id(*parts: object) -> str:
    return str(uuid.uuid5(_NAMESPACE, ":".join(str(part) for part in parts)))


def _event(state: WorkflowState, action: str, stage: WorkflowStage) -> dict[str, str]:
    return {
        "event_id": _stable_id(
            state["workflow_run_id"], action, state.get("retry_count", 0)
        ),
        "event_type": action,
        "stage": stage.value,
        "message": action.replace(".", " "),
        "occurred_at": utc_now(),
    }


def _mock_artifact(
    state: WorkflowState,
    *,
    role: str,
    artifact_type: str,
    payload: dict[str, Any],
) -> ArtifactRef:
    previous = state.get("artifacts", {}).get(role)
    previous_approval = state.get("approvals", {}).get(
        "question" if role == "research_question" else "protocol"
    )
    needs_revision = (
        previous_approval is not None and previous_approval["decision"] != "approved"
    )
    version = (previous["version"] + 1) if previous and needs_revision else 1
    payload = {**payload, "version": version}
    content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    content_hash = sha256_bytes(content)
    artifact_id = _stable_id(state["project_id"], role)
    version_id = _stable_id(artifact_id, version, content_hash)
    return {
        "artifact_id": artifact_id,
        "version_id": version_id,
        "artifact_type": artifact_type,
        "version": version,
        "status": "in_review",
        "content_hash": content_hash,
        "uri": f"mock://{artifact_id}/{version}",
        "media_type": "application/json",
        "created_at": utc_now(),
        "created_by_run_id": state["workflow_run_id"],
    }


def _parse_resume(value: object, *, gate: str, subject: ArtifactRef) -> ApprovalRef:
    if not isinstance(value, dict):
        raise ValueError("Approval resume value must be an object")
    decision = value.get("decision")
    reviewer_id = value.get("reviewer_id")
    reviewer_role = value.get("reviewer_role")
    if decision not in _DECISIONS:
        raise ValueError("Invalid approval decision")
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise ValueError("Human reviewer identity is required")
    if not isinstance(reviewer_role, str) or not reviewer_role.strip():
        raise ValueError("Human reviewer role is required")
    approval: ApprovalRef = {
        "approval_id": _stable_id(gate, subject["version_id"], reviewer_id, decision),
        "gate": cast(Any, gate),
        "subject_id": subject["artifact_id"],
        "subject_version_id": subject["version_id"],
        "subject_hash": subject["content_hash"],
        "decision": str(decision),
        "reviewer_id": reviewer_id.strip(),
        "reviewer_role": reviewer_role.strip(),
        "decided_at": utc_now(),
    }
    comment = value.get("comment")
    if isinstance(comment, str) and comment.strip():
        approval["comment"] = comment.strip()
    return approval


def project_init_node(state: WorkflowState) -> dict[str, Any]:
    return {
        "current_stage": WorkflowStage.PROJECT_INIT.value,
        "run_status": RunStatus.RUNNING.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(state, "foundation.started", WorkflowStage.PROJECT_INIT)
        ],
    }


def research_question_node(state: WorkflowState) -> dict[str, Any]:
    artifact = _mock_artifact(
        state,
        role="research_question",
        artifact_type="research_question",
        payload={
            "study_type": state.get("study_type"),
            "species_scope": state.get("species_scope", []),
            "population": "Synthetic canine/feline clinical population",
            "exposure": "Exposure to be confirmed by investigator",
            "comparator": "Comparator to be confirmed by investigator",
            "outcome": "Primary outcome to be confirmed by investigator",
        },
    )
    artifacts = dict(state.get("artifacts", {}))
    artifacts["research_question"] = artifact
    return {
        "artifacts": artifacts,
        "current_stage": WorkflowStage.RESEARCH_QUESTION.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(state, "research_question.drafted", WorkflowStage.RESEARCH_QUESTION)
        ],
    }


def question_approval_node(state: WorkflowState) -> dict[str, Any]:
    subject = state["artifacts"]["research_question"]
    resume = interrupt(
        {
            "gate": "question",
            "subject_id": subject["artifact_id"],
            "subject_version_id": subject["version_id"],
            "subject_hash": subject["content_hash"],
            "title": "Approve research question and study type",
            "summary": "Review the structured PECO question before protocol mapping.",
            "proposed_next_stage": WorkflowStage.GUIDELINE_MAPPING.value,
            "allowed_decisions": sorted(_DECISIONS),
            "required_reviewer_role": "investigator",
            "warning_codes": [],
        }
    )
    approval = _parse_resume(resume, gate="question", subject=subject)
    approvals = dict(state.get("approvals", {}))
    approvals["question"] = approval
    return {
        "approvals": approvals,
        "current_stage": WorkflowStage.QUESTION_APPROVAL.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(state, "question.reviewed", WorkflowStage.QUESTION_APPROVAL)
        ],
    }


def route_question_decision(state: WorkflowState) -> str:
    decision = state["approvals"]["question"]["decision"]
    return "guideline_mapping" if decision == "approved" else "research_question"


def guideline_mapping_node(state: WorkflowState) -> dict[str, Any]:
    question_approval = require_approved_gate(state, "question")
    question = state["artifacts"]["research_question"]
    if question_approval["subject_hash"] != question["content_hash"]:
        raise PermissionError("Question approval is stale")

    protocol = _mock_artifact(
        state,
        role="protocol",
        artifact_type="protocol",
        payload={
            "research_question_version_id": question["version_id"],
            "guideline": "STROBE-Vet",
            "primary_endpoint": "Requires investigator confirmation",
            "eligibility": "Requires investigator confirmation",
        },
    )
    guideline = _mock_artifact(
        state,
        role="guideline_mapping",
        artifact_type="guideline_mapping",
        payload={
            "protocol_version_id": protocol["version_id"],
            "guideline": "STROBE-Vet",
        },
    )
    artifacts = dict(state["artifacts"])
    artifacts.update({"protocol": protocol, "guideline_mapping": guideline})
    return {
        "artifacts": artifacts,
        "current_stage": WorkflowStage.GUIDELINE_MAPPING.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(state, "protocol.drafted", WorkflowStage.GUIDELINE_MAPPING)
        ],
    }


def protocol_approval_node(state: WorkflowState) -> dict[str, Any]:
    subject = state["artifacts"]["protocol"]
    resume = interrupt(
        {
            "gate": "protocol",
            "subject_id": subject["artifact_id"],
            "subject_version_id": subject["version_id"],
            "subject_hash": subject["content_hash"],
            "title": "Approve and lock protocol scope",
            "summary": "Review endpoints, eligibility, and STROBE-Vet mapping.",
            "proposed_next_stage": WorkflowStage.PROTOCOL_LOCK.value,
            "allowed_decisions": sorted(_DECISIONS),
            "required_reviewer_role": "investigator",
            "warning_codes": ["SCOPE_WILL_BE_LOCKED"],
        }
    )
    approval = _parse_resume(resume, gate="protocol", subject=subject)
    approvals = dict(state.get("approvals", {}))
    approvals["protocol"] = approval
    return {
        "approvals": approvals,
        "current_stage": WorkflowStage.PROTOCOL_APPROVAL.value,
        "updated_at": utc_now(),
        "audit_events": [
            _event(state, "protocol.reviewed", WorkflowStage.PROTOCOL_APPROVAL)
        ],
    }


def route_protocol_decision(state: WorkflowState) -> str:
    decision = state["approvals"]["protocol"]["decision"]
    return "protocol_lock" if decision == "approved" else "guideline_mapping"


def protocol_lock_node(state: WorkflowState) -> dict[str, Any]:
    approval = require_approved_gate(state, "protocol")
    protocol = state["artifacts"]["protocol"]
    if approval["subject_version_id"] != protocol["version_id"]:
        raise PermissionError("Protocol approval belongs to another version")
    if approval["subject_hash"] != protocol["content_hash"]:
        raise PermissionError("Protocol approval hash is stale")
    lock: LockRef = {
        "lock_id": _stable_id("protocol_lock", protocol["version_id"]),
        "lock_type": "protocol",
        "subject_id": protocol["artifact_id"],
        "subject_version_id": protocol["version_id"],
        "subject_hash": protocol["content_hash"],
        "approval_id": approval["approval_id"],
        "locked_by": approval["reviewer_id"],
        "locked_at": utc_now(),
    }
    locks = dict(state.get("locks", {}))
    locks["protocol"] = lock
    artifacts = dict(state["artifacts"])
    artifacts["protocol"] = {**protocol, "status": "locked"}
    return {
        "locks": locks,
        "artifacts": artifacts,
        "current_stage": WorkflowStage.PROTOCOL_LOCK.value,
        "run_status": RunStatus.COMPLETE.value,
        "updated_at": utc_now(),
        "audit_events": [_event(state, "protocol.locked", WorkflowStage.PROTOCOL_LOCK)],
    }


def build_foundation_graph(checkpointer: BaseCheckpointSaver[Any]) -> Any:
    builder = StateGraph(WorkflowState)
    builder.add_node("project_init", project_init_node)
    builder.add_node("research_question", research_question_node)
    builder.add_node("question_approval", question_approval_node)
    builder.add_node("guideline_mapping", guideline_mapping_node)
    builder.add_node("protocol_approval", protocol_approval_node)
    builder.add_node("protocol_lock", protocol_lock_node)

    builder.add_edge(START, "project_init")
    builder.add_edge("project_init", "research_question")
    builder.add_edge("research_question", "question_approval")
    builder.add_conditional_edges("question_approval", route_question_decision)
    builder.add_edge("guideline_mapping", "protocol_approval")
    builder.add_conditional_edges("protocol_approval", route_protocol_decision)
    builder.add_edge("protocol_lock", END)
    return builder.compile(checkpointer=checkpointer)


__all__ = ["build_foundation_graph"]
