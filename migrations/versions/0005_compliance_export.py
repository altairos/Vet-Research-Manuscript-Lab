"""Create compliance findings and export packages tables.

Supports the compliance and export aggregate described in domain_model.md.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_compliance_export"
down_revision: str | None = "0004_writing_review_revision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- compliance_findings: checklist/audit outcomes ---
    op.create_table(
        "compliance_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "manuscript_version_id",
            sa.String(36),
            sa.ForeignKey("manuscript_versions.id"),
            nullable=True,
        ),
        sa.Column("rule_id", sa.String(200), nullable=False),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="needs_review"
        ),
        sa.Column("evidence", sa.Text, nullable=True),
        sa.Column("recommendation", sa.Text, nullable=True),
        sa.Column("created_by_run_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_compliance_findings_project_id", "compliance_findings", ["project_id"]
    )
    op.create_index(
        "ix_compliance_findings_severity", "compliance_findings", ["severity"]
    )
    op.create_index("ix_compliance_findings_status", "compliance_findings", ["status"])

    # --- export_packages: immutable hash-addressed bundles ---
    op.create_table(
        "export_packages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("sign_off_approval_id", sa.String(36), nullable=False),
        sa.Column("manifest_hash", sa.String(80), nullable=False),
        sa.Column("package_hash", sa.String(80), nullable=False),
        sa.Column("component_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="generated"),
        sa.Column("package_uri", sa.String(500), nullable=False),
        sa.UniqueConstraint("project_id", "manifest_hash"),
        sa.UniqueConstraint("package_hash"),
    )
    op.create_index("ix_export_packages_project_id", "export_packages", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_export_packages_project_id", table_name="export_packages")
    op.drop_table("export_packages")
    op.drop_index("ix_compliance_findings_status", table_name="compliance_findings")
    op.drop_index("ix_compliance_findings_severity", table_name="compliance_findings")
    op.drop_index("ix_compliance_findings_project_id", table_name="compliance_findings")
    op.drop_table("compliance_findings")
