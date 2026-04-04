"""add report_url and external_signals

Revision ID: 002
Revises: 001
Create Date: 2026-04-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add report_url to assessments
    op.add_column(
        "assessments",
        sa.Column("report_url", sa.String(2000), nullable=True),
    )

    # Create external_signals table
    op.create_table(
        "external_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assessment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("assessments.id"),
            nullable=False,
        ),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.String(2000), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("data", JSONB, nullable=True),
    )
    op.create_index("ix_external_signals_assessment_id", "external_signals", ["assessment_id"])


def downgrade() -> None:
    op.drop_index("ix_external_signals_assessment_id", "external_signals")
    op.drop_table("external_signals")
    op.drop_column("assessments", "report_url")
