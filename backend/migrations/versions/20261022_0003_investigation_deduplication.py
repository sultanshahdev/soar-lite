"""add investigation uniqueness

Revision ID: 20261022_0003
Revises: 20261021_0002
Create Date: 2026-10-22
"""

from alembic import op

revision = "20261022_0003"
down_revision = "20261021_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_investigations_incident_type_ip", "investigation_executions", ["incident_id", "investigation_type", "source_ip"])


def downgrade() -> None:
    op.drop_constraint("uq_investigations_incident_type_ip", "investigation_executions", type_="unique")
