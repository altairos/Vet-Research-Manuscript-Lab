"""Persist checkpointed human decisions into the formal governance tables."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from vet_manuscript_lab.domain.conventions import new_id
from vet_manuscript_lab.domain.policies import (
    ApprovalSnapshot,
    require_approved_subject,
)
from vet_manuscript_lab.infrastructure.database.models import (
    ApprovalRecord,
    AuditEventRecord,
    LockRecord,
    WorkflowRunRecord,
)
from vet_manuscript_lab.infrastructure.database.repository import now_utc
from vet_manuscript_lab.workflow.state import WorkflowState


class GovernanceRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    def sync_state(self, state: WorkflowState) -> None:
        """Idempotently copy approvals/locks and run status from graph state."""

        with self.sessions.begin() as session:
            run = session.get(WorkflowRunRecord, state["workflow_run_id"])
            if run is None:
                raise LookupError("Workflow run does not exist in the domain database")
            if (
                run.project_id != state["project_id"]
                or run.thread_id != state["thread_id"]
            ):
                raise PermissionError(
                    "Workflow state identity does not match stored run"
                )

            run.status = state["run_status"]
            run.current_stage = state["current_stage"]
            run.updated_at = now_utc()

            for approval in state.get("approvals", {}).values():
                if session.get(ApprovalRecord, approval["approval_id"]) is not None:
                    continue
                approval_record = ApprovalRecord(
                    id=approval["approval_id"],
                    project_id=state["project_id"],
                    gate=approval["gate"],
                    subject_id=approval["subject_id"],
                    subject_version_id=approval["subject_version_id"],
                    subject_hash=approval["subject_hash"],
                    decision=approval["decision"],
                    reviewer_id=approval["reviewer_id"],
                    reviewer_role=approval["reviewer_role"],
                    comment=approval.get("comment"),
                    decided_at=now_utc(),
                )
                session.add(approval_record)
                self._event(
                    session,
                    state=state,
                    actor_id=approval_record.reviewer_id,
                    action="approval.recorded",
                    target_type="approval",
                    target_id=approval_record.id,
                )
            session.flush()

            for lock in state.get("locks", {}).values():
                if session.get(LockRecord, lock["lock_id"]) is not None:
                    continue
                lock_approval = state.get("approvals", {}).get(lock["lock_type"])
                snapshot = None
                if lock_approval is not None:
                    snapshot = ApprovalSnapshot(
                        gate=lock_approval["gate"],
                        subject_version_id=lock_approval["subject_version_id"],
                        subject_hash=lock_approval["subject_hash"],
                        decision=lock_approval["decision"],
                        reviewer_id=lock_approval["reviewer_id"],
                        reviewer_role=lock_approval["reviewer_role"],
                    )
                require_approved_subject(
                    snapshot,
                    gate=lock["lock_type"],
                    subject_version_id=lock["subject_version_id"],
                    subject_hash=lock["subject_hash"],
                    allowed_roles=frozenset({"investigator"}),
                )
                lock_record = LockRecord(
                    id=lock["lock_id"],
                    project_id=state["project_id"],
                    lock_type=lock["lock_type"],
                    subject_id=lock["subject_id"],
                    subject_version_id=lock["subject_version_id"],
                    subject_hash=lock["subject_hash"],
                    approval_id=lock["approval_id"],
                    locked_by=lock["locked_by"],
                    locked_at=now_utc(),
                )
                session.add(lock_record)
                self._event(
                    session,
                    state=state,
                    actor_id=lock_record.locked_by,
                    action="lock.recorded",
                    target_type="lock",
                    target_id=lock_record.id,
                )

    @staticmethod
    def _event(
        session: Session,
        *,
        state: WorkflowState,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
    ) -> None:
        session.add(
            AuditEventRecord(
                id=new_id(),
                project_id=state["project_id"],
                workflow_run_id=state["workflow_run_id"],
                actor_type="human",
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                outcome="success",
                event_metadata={},
                occurred_at=now_utc(),
            )
        )


__all__ = ["GovernanceRepository"]
