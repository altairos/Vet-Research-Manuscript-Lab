"""Create manuscript, claim, citation, review, and revision tables.

Supports the Manuscript aggregate described in domain_model.md.
Unique constraints are defined inline for SQLite ALTER compatibility.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_writing_review_revision"
down_revision: str | None = "0003_methodology_statistics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- manuscripts: stable manuscript identity ---
    op.create_table(
        "manuscripts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("target_journal", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_manuscripts_project_id", "manuscripts", ["project_id"])

    # --- manuscript_versions: immutable assembled draft ---
    op.create_table(
        "manuscript_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "manuscript_id",
            sa.String(36),
            sa.ForeignKey("manuscripts.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default=sa.text("'draft'")
        ),
        sa.Column(
            "section_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "revision_round", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("created_by_run_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("manuscript_id", "version"),
        sa.UniqueConstraint("manuscript_id", "content_hash"),
    )
    op.create_index(
        "ix_manuscript_versions_manuscript_id",
        "manuscript_versions",
        ["manuscript_id"],
    )
    op.create_index(
        "ix_manuscript_versions_status",
        "manuscript_versions",
        ["status"],
    )

    # --- manuscript_sections: versioned section ---
    op.create_table(
        "manuscript_sections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "manuscript_version_id",
            sa.String(36),
            sa.ForeignKey("manuscript_versions.id"),
            nullable=False,
        ),
        sa.Column("section_type", sa.String(64), nullable=False),
        sa.Column("content_uri", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column(
            "section_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "word_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("manuscript_version_id", "section_type"),
    )
    op.create_index(
        "ix_manuscript_sections_manuscript_version_id",
        "manuscript_sections",
        ["manuscript_version_id"],
    )

    # --- claims: manuscript assertion ---
    op.create_table(
        "claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "manuscript_section_id",
            sa.String(36),
            sa.ForeignKey("manuscript_sections.id"),
            nullable=False,
        ),
        sa.Column("claim_type", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("span_start", sa.Integer(), nullable=True),
        sa.Column("span_end", sa.Integer(), nullable=True),
        sa.Column("certainty", sa.String(32), nullable=False),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default=sa.text("'active'")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_claims_manuscript_section_id",
        "claims",
        ["manuscript_section_id"],
    )
    op.create_index("ix_claims_claim_type", "claims", ["claim_type"])

    # --- claim_supports: claim-to-source relation ---
    op.create_table(
        "claim_supports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "claim_id",
            sa.String(36),
            sa.ForeignKey("claims.id"),
            nullable=False,
        ),
        sa.Column("support_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("relation", sa.String(64), nullable=False),
        sa.Column(
            "audit_status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_claim_supports_claim_id",
        "claim_supports",
        ["claim_id"],
    )
    op.create_index(
        "ix_claim_supports_support_type",
        "claim_supports",
        ["support_type"],
    )

    # --- citations: citation occurrence ---
    op.create_table(
        "citations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "claim_id",
            sa.String(36),
            sa.ForeignKey("claims.id"),
            nullable=True,
        ),
        sa.Column(
            "manuscript_section_id",
            sa.String(36),
            sa.ForeignKey("manuscript_sections.id"),
            nullable=False,
        ),
        sa.Column("literature_record_id", sa.String(36), nullable=False),
        sa.Column("citation_key", sa.String(200), nullable=False),
        sa.Column("locator", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_citations_manuscript_section_id",
        "citations",
        ["manuscript_section_id"],
    )

    # --- review_findings: actionable critique ---
    op.create_table(
        "review_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "manuscript_version_id",
            sa.String(36),
            sa.ForeignKey("manuscript_versions.id"),
            nullable=False,
        ),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column("reviewer_id", sa.String(100), nullable=True),
        sa.Column(
            "revision_round", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_review_findings_manuscript_version_id",
        "review_findings",
        ["manuscript_version_id"],
    )
    op.create_index(
        "ix_review_findings_severity",
        "review_findings",
        ["severity"],
    )
    op.create_index("ix_review_findings_status", "review_findings", ["status"])

    # --- revision_decisions: human disposition ---
    op.create_table(
        "revision_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "review_finding_id",
            sa.String(36),
            sa.ForeignKey("review_findings.id"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.String(100), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("review_finding_id"),
    )
    op.create_index(
        "ix_revision_decisions_review_finding_id",
        "revision_decisions",
        ["review_finding_id"],
    )


def downgrade() -> None:
    op.drop_table("revision_decisions")
    op.drop_table("review_findings")
    op.drop_table("citations")
    op.drop_table("claim_supports")
    op.drop_table("claims")
    op.drop_table("manuscript_sections")
    op.drop_table("manuscript_versions")
    op.drop_table("manuscripts")
