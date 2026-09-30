"""Add agent notification destinations and delivery source metadata.

Revision ID: p2e3f4g5h6i7
Revises: o1d2e3f4g5h6
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "p2e3f4g5h6i7"
down_revision: str | None = "o1d2e3f4g5h6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.create_table(
        "ai_agent_notification_destinations",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("agent_id", uuid_type, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("destination_ciphertext", sa.Text(), nullable=False),
        sa.Column("destination_digest", sa.String(length=128), nullable=False),
        sa.Column("destination_hint", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_id", uuid_type, nullable=True),
        sa.Column("updated_by_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agent_id",
            "destination_digest",
            name="uq_ai_agent_notification_destinations_agent_digest",
        ),
    )
    op.create_index(
        "ix_ai_agent_notification_destinations_agent_id",
        "ai_agent_notification_destinations",
        ["agent_id"],
    )
    op.create_index(
        "ix_ai_agent_notification_destinations_created_by_id",
        "ai_agent_notification_destinations",
        ["created_by_id"],
    )
    op.create_index(
        "ix_ai_agent_notification_destinations_updated_by_id",
        "ai_agent_notification_destinations",
        ["updated_by_id"],
    )
    op.create_index(
        "ix_ai_agent_notification_destinations_agent_enabled",
        "ai_agent_notification_destinations",
        ["agent_id", "enabled"],
    )

    op.add_column("integration_delivery_jobs", sa.Column("agent_id", uuid_type, nullable=True))
    op.add_column("integration_delivery_jobs", sa.Column("agent_destination_id", uuid_type, nullable=True))
    if op.get_context().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_integration_delivery_jobs_agent_id",
            "integration_delivery_jobs",
            "ai_agents",
            ["agent_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_integration_delivery_jobs_agent_destination_id",
            "integration_delivery_jobs",
            "ai_agent_notification_destinations",
            ["agent_destination_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_integration_delivery_jobs_agent_id", "integration_delivery_jobs", ["agent_id"])
    op.create_index(
        "ix_integration_delivery_jobs_agent_destination_id",
        "integration_delivery_jobs",
        ["agent_destination_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_integration_delivery_jobs_agent_destination_id", table_name="integration_delivery_jobs")
    op.drop_index("ix_integration_delivery_jobs_agent_id", table_name="integration_delivery_jobs")
    if op.get_context().dialect.name != "sqlite":
        op.drop_constraint("fk_integration_delivery_jobs_agent_destination_id", "integration_delivery_jobs", type_="foreignkey")
        op.drop_constraint("fk_integration_delivery_jobs_agent_id", "integration_delivery_jobs", type_="foreignkey")
    op.drop_column("integration_delivery_jobs", "agent_destination_id")
    op.drop_column("integration_delivery_jobs", "agent_id")

    op.drop_index(
        "ix_ai_agent_notification_destinations_agent_enabled",
        table_name="ai_agent_notification_destinations",
    )
    op.drop_index(
        "ix_ai_agent_notification_destinations_updated_by_id",
        table_name="ai_agent_notification_destinations",
    )
    op.drop_index(
        "ix_ai_agent_notification_destinations_created_by_id",
        table_name="ai_agent_notification_destinations",
    )
    op.drop_index(
        "ix_ai_agent_notification_destinations_agent_id",
        table_name="ai_agent_notification_destinations",
    )
    op.drop_table("ai_agent_notification_destinations")
