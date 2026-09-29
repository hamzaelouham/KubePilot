"""Add integration delivery jobs.

Revision ID: l8a9b0c1d2e3
Revises: k7f8a9b0c1d2
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "l8a9b0c1d2e3"
down_revision: str | None = "k7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.create_table(
        "integration_delivery_jobs",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("connection_id", uuid_type, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("destination_hint", sa.String(length=128), nullable=False),
        sa.Column("payload_ciphertext", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("actor_id", uuid_type, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["integration_connections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_integration_delivery_jobs_idempotency"),
    )
    op.create_index("ix_integration_delivery_jobs_connection_id", "integration_delivery_jobs", ["connection_id"])
    op.create_index("ix_integration_delivery_jobs_actor_id", "integration_delivery_jobs", ["actor_id"])
    op.create_index("ix_integration_delivery_jobs_next_attempt_at", "integration_delivery_jobs", ["next_attempt_at"])
    op.create_index(
        "ix_integration_delivery_jobs_status_due",
        "integration_delivery_jobs",
        ["status", "next_attempt_at"],
    )
    op.create_index(
        "ix_integration_delivery_jobs_provider_created",
        "integration_delivery_jobs",
        ["provider", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_integration_delivery_jobs_provider_created", table_name="integration_delivery_jobs")
    op.drop_index("ix_integration_delivery_jobs_status_due", table_name="integration_delivery_jobs")
    op.drop_index("ix_integration_delivery_jobs_next_attempt_at", table_name="integration_delivery_jobs")
    op.drop_index("ix_integration_delivery_jobs_actor_id", table_name="integration_delivery_jobs")
    op.drop_index("ix_integration_delivery_jobs_connection_id", table_name="integration_delivery_jobs")
    op.drop_table("integration_delivery_jobs")
