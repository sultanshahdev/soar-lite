"""create investigation persistence

Revision ID: 20261021_0002
Revises: 20261021_0001
Create Date: 2026-10-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261021_0002"
down_revision = "20261021_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigation_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("source_ip", sa.String(length=45), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.String(length=512), nullable=True),
        sa.CheckConstraint("investigation_type IN ('suspicious_ip')", name="ck_investigations_type"),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed')", name="ck_investigations_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_investigations_attempt_count"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investigations_status_next_attempt", "investigation_executions", ["status", "next_attempt_at"])
    op.create_index("ix_investigations_incident_created_at", "investigation_executions", ["incident_id", "created_at"])
    op.create_table(
        "investigation_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_source", sa.String(length=64), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigation_executions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investigation_evidence_investigation_created", "investigation_evidence", ["investigation_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_investigation_evidence_investigation_created", table_name="investigation_evidence")
    op.drop_table("investigation_evidence")
    op.drop_index("ix_investigations_incident_created_at", table_name="investigation_executions")
    op.drop_index("ix_investigations_status_next_attempt", table_name="investigation_executions")
    op.drop_table("investigation_executions")
