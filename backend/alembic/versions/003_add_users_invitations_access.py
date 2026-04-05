"""add users, invitations, user_assessment_access

Revision ID: 003
Revises: 002
Create Date: 2026-04-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_organization_id", "users", ["organization_id"])

    op.create_table(
        "invitations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("invited_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_invitations_email", "invitations", ["email"])
    op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)

    op.create_table(
        "user_assessment_access",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assessment_id", UUID(as_uuid=True), sa.ForeignKey("assessments.id"), nullable=False),
        sa.Column("granted_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "assessment_id", name="uq_user_assessment"),
    )
    op.create_index("ix_uaa_user_id", "user_assessment_access", ["user_id"])
    op.create_index("ix_uaa_assessment_id", "user_assessment_access", ["assessment_id"])


def downgrade() -> None:
    op.drop_table("user_assessment_access")
    op.drop_table("invitations")
    op.drop_table("users")
