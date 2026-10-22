"""add human-approved response actions

Revision ID: 20261022_0005
Revises: 20261022_0004
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261022_0005"
down_revision = "20261022_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "response_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("target_ip", sa.String(length=45), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("proposed_by", sa.String(length=128), nullable=False),
        sa.Column("decided_by", sa.String(length=128), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("execution_error", sa.String(length=512), nullable=True),
        sa.CheckConstraint("action_type IN ('block_ip')", name="ck_response_actions_type"),
        sa.CheckConstraint("status IN ('proposed', 'approved', 'executing', 'executed', 'rejected', 'failed', 'reverted')", name="ck_response_actions_status"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigation_executions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_response_actions_incident_created", "response_actions", ["incident_id", "created_at"])
    op.create_index("ix_response_actions_status_created", "response_actions", ["status", "created_at"])
    op.create_index("uq_response_actions_active_target", "response_actions", ["incident_id", "action_type", "target_ip"], unique=True, postgresql_where=sa.text("status IN ('proposed', 'approved', 'executing')"))
    op.create_table(
        "response_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("response_action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=True),
        sa.Column("to_status", sa.String(length=16), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["response_action_id"], ["response_actions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_response_audit_action_created", "response_audit_events", ["response_action_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_response_audit_action_created", table_name="response_audit_events")
    op.drop_table("response_audit_events")
    op.drop_index("uq_response_actions_active_target", table_name="response_actions")
    op.drop_index("ix_response_actions_status_created", table_name="response_actions")
    op.drop_index("ix_response_actions_incident_created", table_name="response_actions")
    op.drop_table("response_actions")
