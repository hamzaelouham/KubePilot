"""allow live Helm release action jobs without Marketplace metadata

Revision ID: a7b8c9d0e1f2
Revises: f2a3b4c5d6e7
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    historical_table = _installation_jobs_table()
    with op.batch_alter_table("installation_jobs", copy_from=historical_table) as batch:
        for column in ("package_id", "package_name", "chart_name", "chart_repository", "chart_version"):
            batch.alter_column(column, nullable=True)


def downgrade() -> None:
    historical_table = _installation_jobs_table()
    with op.batch_alter_table("installation_jobs", copy_from=historical_table) as batch:
        for column in ("package_id", "package_name", "chart_name", "chart_repository", "chart_version"):
            batch.alter_column(column, nullable=False)


def _installation_jobs_table() -> sa.Table:
    metadata = sa.MetaData()
    table = sa.Table(
        "installation_jobs",
        metadata,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
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
        sa.Column("chart_repository_url", sa.String(length=2048), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False, server_default="install"),
        sa.Column("revision", sa.Integer(), nullable=True),
        sa.Column("log_output", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster_connections.id"], ondelete="CASCADE"),
    )
    sa.Index("ix_installation_jobs_cluster_status", table.c.cluster_id, table.c.status)
    return table
