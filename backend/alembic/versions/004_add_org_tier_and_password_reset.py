"""add org tier fields and password_reset_tokens table

Revision ID: 004
Revises: 003
Create Date: 2026-04-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add tier and is_demo to organizations
    op.add_column("organizations", sa.Column("tier", sa.String(20), nullable=False, server_default="tier_1"))
    op.add_column("organizations", sa.Column("is_demo", sa.Boolean, nullable=False, server_default="false"))

    # Create password_reset_tokens table
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_email", "password_reset_tokens", ["email"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_email", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("organizations", "is_demo")
    op.drop_column("organizations", "tier")
