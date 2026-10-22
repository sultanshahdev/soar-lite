"""add simulated lab response execution state

Revision ID: 20261022_0006
Revises: 20261022_0005
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261022_0006"
down_revision = "20261022_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("response_actions", sa.Column("execution_attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("response_actions", sa.Column("lease_token", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("response_actions", sa.Column("lease_owner", sa.String(length=128), nullable=True))
    op.add_column("response_actions", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "lab_block_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("response_action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["response_action_id"], ["response_actions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("response_action_id", name="uq_lab_blocks_response_action"),
    )
    op.create_index("ix_lab_blocks_ip_active", "lab_block_entries", ["ip_address", "active"])


def downgrade() -> None:
    op.drop_index("ix_lab_blocks_ip_active", table_name="lab_block_entries")
    op.drop_table("lab_block_entries")
    op.drop_column("response_actions", "lease_expires_at")
    op.drop_column("response_actions", "lease_owner")
    op.drop_column("response_actions", "lease_token")
    op.drop_column("response_actions", "execution_attempt_count")
