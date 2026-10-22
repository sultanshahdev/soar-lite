"""add investigation lease owner

Revision ID: 20261022_0004
Revises: 20261022_0003
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa

revision = "20261022_0004"
down_revision = "20261022_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("investigation_executions", sa.Column("lease_owner", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("investigation_executions", "lease_owner")
