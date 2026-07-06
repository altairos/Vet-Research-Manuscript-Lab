"""Create literature, evidence, screening, and provenance tables.

Supports the Literature and evidence aggregate described in domain_model.md.
Unique constraints are defined inline for SQLite ALTER compatibility.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_literature_evidence"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- literature_records: local bibliographic identity ---
    op.create_table(
        "literature_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("title", sa.String(600), nullable=False),
        sa.Column("doi", sa.String(255), nullable=True),
        sa.Column("pmid", sa.String(32), nullable=True),
        sa.Column("zotero_item_key", sa.String(64), nullable=True),
        sa.Column("zotero_library_id", sa.String(64), nullable=True),
        sa.Column("bibtex_key", sa.String(128), nullable=True),
        sa.Column("creators", sa.JSON(), nullable=False),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("journal", sa.String(500), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "sync_status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'local'"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "doi"),
        sa.UniqueConstraint("project_id", "pmid"),
    )
    op.create_index(
        "ix_literature_records_project_id",
        "literature_records",
        ["project_id"],
    )
    op.create_index("ix_literature_records_doi", "literature_records", ["doi"])
    op.create_index("ix_literature_records_pmid", "literature_records", ["pmid"])
    op.create_index(
        "ix_literature_records_zotero_item_key",
        "literature_records",
        ["zotero_item_key"],
    )

    # --- attachment_versions: immutable source file per literature record ---
    op.create_table(
        "attachment_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "literature_record_id",
            sa.String(36),
            sa.ForeignKey("literature_records.id"),
            nullable=False,
        ),
        sa.Column("attachment_key", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("created_by_run_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("literature_record_id", "version"),
        sa.UniqueConstraint("literature_record_id", "content_hash"),
    )
    op.create_index(
        "ix_attachment_versions_literature_record_id",
        "attachment_versions",
        ["literature_record_id"],
    )

    # --- source_spans: exact source location within an attachment ---
    op.create_table(
        "source_spans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "literature_record_id",
            sa.String(36),
            sa.ForeignKey("literature_records.id"),
            nullable=False,
        ),
        sa.Column(
            "attachment_version_id",
            sa.String(36),
            sa.ForeignKey("attachment_versions.id"),
            nullable=True,
        ),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section_label", sa.String(128), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("quote_hash", sa.String(80), nullable=False),
        sa.Column("created_by_run_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_source_spans_project_id", "source_spans", ["project_id"])
    op.create_index(
        "ix_source_spans_literature_record_id",
        "source_spans",
        ["literature_record_id"],
    )

    # --- evidence_items: validatable extracted evidence ---
    op.create_table(
        "evidence_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("concept", sa.String(300), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("units", sa.String(128), nullable=True),
        sa.Column("population", sa.String(300), nullable=True),
        sa.Column(
            "certainty",
            sa.String(64),
            nullable=False,
            server_default=sa.text("'unspecified'"),
        ),
        sa.Column(
            "extraction_status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("source_span_ids", sa.JSON(), nullable=False),
        sa.Column(
            "literature_record_id",
            sa.String(36),
            sa.ForeignKey("literature_records.id"),
            nullable=False,
        ),
        sa.Column("created_by_run_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "requires_human_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index("ix_evidence_items_project_id", "evidence_items", ["project_id"])
    op.create_index(
        "ix_evidence_items_literature_record_id",
        "evidence_items",
        ["literature_record_id"],
    )
    op.create_index("ix_evidence_items_concept", "evidence_items", ["concept"])

    # --- screening_decisions: inclusion / exclusion per record ---
    op.create_table(
        "screening_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "literature_record_id",
            sa.String(36),
            sa.ForeignKey("literature_records.id"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.String(100), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "literature_record_id", "stage", name="uq_screening_record_stage"
        ),
    )
    op.create_index(
        "ix_screening_decisions_project_id",
        "screening_decisions",
        ["project_id"],
    )
    op.create_index(
        "ix_screening_decisions_literature_record_id",
        "screening_decisions",
        ["literature_record_id"],
    )

    # --- provenance_links: typed directed derivation edges ---
    op.create_table(
        "provenance_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column("source_version_id", sa.String(36), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("target_version_id", sa.String(36), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("relation", sa.String(64), nullable=False),
        sa.Column("created_by_run_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source_version_id",
            "target_version_id",
            "relation",
            name="uq_provenance_link_edge",
        ),
    )
    op.create_index(
        "ix_provenance_links_project_id",
        "provenance_links",
        ["project_id"],
    )
    op.create_index(
        "ix_provenance_links_target_version_id",
        "provenance_links",
        ["target_version_id"],
    )


def downgrade() -> None:
    op.drop_table("provenance_links")
    op.drop_table("screening_decisions")
    op.drop_table("evidence_items")
    op.drop_table("source_spans")
    op.drop_table("attachment_versions")
    op.drop_table("literature_records")
