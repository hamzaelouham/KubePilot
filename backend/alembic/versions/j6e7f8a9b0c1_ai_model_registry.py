"""Add the administrator-managed AI model registry.

Revision ID: j6e7f8a9b0c1
Revises: i5d6e7f8a9b0
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "j6e7f8a9b0c1"
down_revision: str | None = "i5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.create_table(
        "ai_model_configs",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("provider_id", sa.String(length=32), nullable=False),
        sa.Column("external_model_id", sa.String(length=255), nullable=False),
        sa.Column("friendly_name", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("supports_streaming", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("supports_tools", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("supports_reasoning", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("supports_vision", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("supports_large_context", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("availability", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("availability_message", sa.String(length=512), nullable=True),
        sa.Column("availability_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", uuid_type, nullable=True),
        sa.Column("updated_by_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", "external_model_id", name="uq_ai_model_configs_provider_external"),
    )
    op.create_index("ix_ai_model_configs_created_by_id", "ai_model_configs", ["created_by_id"])
    op.create_index("ix_ai_model_configs_updated_by_id", "ai_model_configs", ["updated_by_id"])
    op.create_index("ix_ai_model_configs_provider", "ai_model_configs", ["provider_id"])
    op.create_index("ix_ai_model_configs_eligibility", "ai_model_configs", ["enabled", "availability"])
    op.create_index(
        "uq_ai_model_configs_global_default",
        "ai_model_configs",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
        sqlite_where=sa.text("is_default = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_ai_model_configs_global_default", table_name="ai_model_configs")
    op.drop_index("ix_ai_model_configs_eligibility", table_name="ai_model_configs")
    op.drop_index("ix_ai_model_configs_provider", table_name="ai_model_configs")
    op.drop_index("ix_ai_model_configs_updated_by_id", table_name="ai_model_configs")
    op.drop_index("ix_ai_model_configs_created_by_id", table_name="ai_model_configs")
    op.drop_table("ai_model_configs")
