"""Add evidence_type and evidence_metadata columns to evidence_items.

Supports Phase C (Evidence Type Schema) of the vertical-hardening plan.
``evidence_type`` is a structured classification (see EvidenceType enum)
and ``evidence_metadata`` stores type-specific required fields.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_evidence_type_schema"
down_revision: str | None = "0005_compliance_export"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("evidence_items") as batch_op:
        batch_op.add_column(
            sa.Column(
                "evidence_type",
                sa.String(64),
                nullable=False,
                server_default="background_claim",
            )
        )
        batch_op.add_column(
            sa.Column(
                "evidence_metadata",
                sa.JSON,
                nullable=False,
                server_default="{}",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("evidence_items") as batch_op:
        batch_op.drop_column("evidence_metadata")
        batch_op.drop_column("evidence_type")
