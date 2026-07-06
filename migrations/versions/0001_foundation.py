"""Create Foundation project, artifact, approval, lock, and audit tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("study_type", sa.String(100), nullable=False),
        sa.Column("species_scope", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("owner_id", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False
        ),
        sa.Column("thread_id", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_stage", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_runs_project_id", "workflow_runs", ["project_id"])
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False
        ),
        sa.Column("artifact_type", sa.String(100), nullable=False),
        sa.Column("logical_name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "artifact_type", "logical_name"),
    )
    op.create_index("ix_artifacts_project_id", "artifacts", ["project_id"])
    op.create_table(
        "artifact_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "artifact_id", sa.String(36), sa.ForeignKey("artifacts.id"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column(
            "created_by_run_id", sa.String(36), sa.ForeignKey("workflow_runs.id")
        ),
        sa.Column("source_version_ids", sa.JSON(), nullable=False),
        sa.Column("is_formal", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("artifact_id", "version"),
        sa.UniqueConstraint("artifact_id", "content_hash"),
    )
    op.create_index(
        "ix_artifact_versions_artifact_id", "artifact_versions", ["artifact_id"]
    )
    op.create_index("ix_artifact_versions_status", "artifact_versions", ["status"])
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False
        ),
        sa.Column("gate", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("subject_version_id", sa.String(36), nullable=False),
        sa.Column("subject_hash", sa.String(80), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reviewer_id", sa.String(100), nullable=False),
        sa.Column("reviewer_role", sa.String(64), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("gate", "subject_version_id", "reviewer_id"),
    )
    op.create_index("ix_approvals_project_id", "approvals", ["project_id"])
    op.create_table(
        "locks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False
        ),
        sa.Column("lock_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("subject_version_id", sa.String(36), nullable=False),
        sa.Column("subject_hash", sa.String(80), nullable=False),
        sa.Column(
            "approval_id", sa.String(36), sa.ForeignKey("approvals.id"), nullable=False
        ),
        sa.Column("locked_by", sa.String(100), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("lock_type", "subject_version_id"),
    )
    op.create_index("ix_locks_project_id", "locks", ["project_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False
        ),
        sa.Column("workflow_run_id", sa.String(36), sa.ForeignKey("workflow_runs.id")),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_project_id", "audit_events", ["project_id"])
    op.create_index(
        "ix_audit_events_workflow_run_id", "audit_events", ["workflow_run_id"]
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("locks")
    op.drop_table("approvals")
    op.drop_table("artifact_versions")
    op.drop_table("artifacts")
    op.drop_table("workflow_runs")
    op.drop_table("projects")
