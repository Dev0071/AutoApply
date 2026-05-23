"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-22 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("github_url", sa.String(), nullable=True),
        sa.Column("skills", ARRAY(sa.Text()), nullable=True),
        sa.Column("experience", JSONB(), nullable=True),
        sa.Column("fit_threshold", sa.Integer(), nullable=False, server_default="70"),
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"])

    op.create_table(
        "job_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("company", sa.String(), nullable=True),
        sa.Column("raw_jd_text", sa.Text(), nullable=True),
        sa.Column("keywords", ARRAY(sa.Text()), nullable=True),
        sa.Column("fit_score", sa.Float(), nullable=True),
        sa.Column("ats_type", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_job_records_user_id", "job_records", ["user_id"])

    op.create_table(
        "application_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_record_id", UUID(as_uuid=True), sa.ForeignKey("job_records.id"), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "queued", "running", "review", "submitted", "failed", name="applicationstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("steps", JSONB(), nullable=True),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("bullets", ARRAY(sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_application_runs_user_id", "application_runs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_application_runs_user_id", "application_runs")
    op.drop_table("application_runs")
    op.execute("DROP TYPE IF EXISTS applicationstatus")
    op.drop_index("ix_job_records_user_id", "job_records")
    op.drop_table("job_records")
    op.drop_index("ix_user_profiles_user_id", "user_profiles")
    op.drop_table("user_profiles")
