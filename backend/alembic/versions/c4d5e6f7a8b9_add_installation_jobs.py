"""add installation_jobs

Revision ID: c4d5e6f7a8b9
Revises: b7e8f9a0c1d2
Create Date: 2026-09-08 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b7e8f9a0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "installation_jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("package_id", sa.String(length=512), nullable=False),
        sa.Column("package_name", sa.String(length=253), nullable=False),
        sa.Column("chart_name", sa.String(length=253), nullable=False),
        sa.Column("chart_repository", sa.String(length=253), nullable=False),
        sa.Column("chart_version", sa.String(length=64), nullable=False),
        sa.Column("cluster_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("namespace", sa.String(length=253), nullable=False),
        sa.Column("release_name", sa.String(length=253), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_installation_jobs_cluster_status", "cluster_id", "status"),
    )


def downgrade() -> None:
    op.drop_table("installation_jobs")