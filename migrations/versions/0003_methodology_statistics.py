"""Create methodology, dataset, analysis plan, and statistics tables.

Supports the Dataset and statistics aggregate described in domain_model.md.
Unique constraints are defined inline for SQLite ALTER compatibility.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_methodology_statistics"
down_revision: str | None = "0002_literature_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- datasets: stable dataset identity ---
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])
    op.create_index(
        "ix_datasets_name",
        "datasets",
        ["name"],
    )

    # --- dataset_versions: immutable content version ---
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.String(36),
            sa.ForeignKey("datasets.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_by_run_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dataset_id", "version"),
        sa.UniqueConstraint("dataset_id", "content_hash"),
    )
    op.create_index(
        "ix_dataset_versions_dataset_id",
        "dataset_versions",
        ["dataset_id"],
    )
    op.create_index("ix_dataset_versions_status", "dataset_versions", ["status"])

    # --- dataset_variables: variable dictionary ---
    op.create_table(
        "dataset_variables",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "dataset_version_id",
            sa.String(36),
            sa.ForeignKey("dataset_versions.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("var_type", sa.String(64), nullable=False),
        sa.Column("unit", sa.String(128), nullable=True),
        sa.Column("missing_code", sa.String(64), nullable=True),
        sa.Column("role", sa.String(64), nullable=False, server_default="covariate"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("dataset_version_id", "name"),
    )
    op.create_index(
        "ix_dataset_variables_dataset_version_id",
        "dataset_variables",
        ["dataset_version_id"],
    )
    op.create_index("ix_dataset_variables_role", "dataset_variables", ["role"])

    # --- analysis_plan_versions: prespecified analysis plan ---
    op.create_table(
        "analysis_plan_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column(
            "is_exploratory",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("methodology_version_id", sa.String(36), nullable=True),
        sa.Column("protocol_version_id", sa.String(36), nullable=True),
        sa.Column("created_by_run_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "version"),
        sa.UniqueConstraint("project_id", "content_hash"),
    )
    op.create_index(
        "ix_analysis_plan_versions_project_id",
        "analysis_plan_versions",
        ["project_id"],
    )
    op.create_index(
        "ix_analysis_plan_versions_status",
        "analysis_plan_versions",
        ["status"],
    )

    # --- analysis_plan_locks: approved plan freeze ---
    op.create_table(
        "analysis_plan_locks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("plan_version_id", sa.String(36), nullable=False),
        sa.Column("plan_hash", sa.String(80), nullable=False),
        sa.Column("dataset_version_id", sa.String(36), nullable=False),
        sa.Column("dataset_hash", sa.String(80), nullable=False),
        sa.Column("approval_id", sa.String(36), nullable=False),
        sa.Column("locked_by", sa.String(100), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("plan_version_id"),
        sa.UniqueConstraint("dataset_version_id"),
    )
    op.create_index(
        "ix_analysis_plan_locks_project_id",
        "analysis_plan_locks",
        ["project_id"],
    )

    # --- methodology_findings: structured critic output ---
    op.create_table(
        "methodology_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column(
            "analysis_plan_version_id",
            sa.String(36),
            nullable=True,
        ),
        sa.Column("created_by_run_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_methodology_findings_project_id",
        "methodology_findings",
        ["project_id"],
    )
    op.create_index(
        "ix_methodology_findings_severity",
        "methodology_findings",
        ["severity"],
    )

    # --- analysis_runs: reproducible execution record ---
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("plan_version_id", sa.String(36), nullable=False),
        sa.Column("plan_hash", sa.String(80), nullable=False),
        sa.Column("dataset_version_id", sa.String(36), nullable=False),
        sa.Column("dataset_hash", sa.String(80), nullable=False),
        sa.Column("script_hash", sa.String(80), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("package_versions", sa.JSON(), nullable=False),
        sa.Column("environment", sa.JSON(), nullable=False),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column(
            "is_exploratory",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("created_by_run_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_analysis_runs_project_id", "analysis_runs", ["project_id"])
    op.create_index("ix_analysis_runs_status", "analysis_runs", ["status"])
    op.create_index(
        "ix_analysis_runs_plan_version_id",
        "analysis_runs",
        ["plan_version_id"],
    )

    # --- statistical_results: typed result ---
    op.create_table(
        "statistical_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "analysis_run_id",
            sa.String(36),
            sa.ForeignKey("analysis_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("estimand", sa.String(300), nullable=False),
        sa.Column("estimate", sa.Float(), nullable=True),
        sa.Column("estimate_units", sa.String(128), nullable=True),
        sa.Column("uncertainty_type", sa.String(64), nullable=True),
        sa.Column("uncertainty_lower", sa.Float(), nullable=True),
        sa.Column("uncertainty_upper", sa.Float(), nullable=True),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("method", sa.String(200), nullable=True),
        sa.Column("population", sa.String(300), nullable=True),
        sa.Column("analysis_class", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_statistical_results_analysis_run_id",
        "statistical_results",
        ["analysis_run_id"],
    )
    op.create_index(
        "ix_statistical_results_project_id",
        "statistical_results",
        ["project_id"],
    )
    op.create_index(
        "ix_statistical_results_analysis_class",
        "statistical_results",
        ["analysis_class"],
    )


def downgrade() -> None:
    op.drop_table("statistical_results")
    op.drop_table("analysis_runs")
    op.drop_table("methodology_findings")
    op.drop_table("analysis_plan_locks")
    op.drop_table("analysis_plan_versions")
    op.drop_table("dataset_variables")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
