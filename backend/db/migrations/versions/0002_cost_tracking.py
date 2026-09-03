"""Add per-run cost tracking columns to application_runs.

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("application_runs", sa.Column("total_cost_usd", sa.Float(), nullable=True))
    op.add_column("application_runs", sa.Column("token_usage", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("application_runs", "token_usage")
    op.drop_column("application_runs", "total_cost_usd")
