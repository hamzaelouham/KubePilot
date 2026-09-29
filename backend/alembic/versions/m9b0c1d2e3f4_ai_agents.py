"""Shared AI agent definitions.

Revision ID: m9b0c1d2e3f4
Revises: l8a9b0c1d2e3
"""
from alembic import op
import sqlalchemy as sa

revision = "m9b0c1d2e3f4"
down_revision = "l8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_agents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Uuid(), sa.ForeignKey("ai_model_configs.id", ondelete="SET NULL")),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_ai_agents_name"),
    )
    op.create_index("ix_ai_agents_model_id", "ai_agents", ["model_id"])


def downgrade():
    op.drop_index("ix_ai_agents_model_id", table_name="ai_agents")
    op.drop_table("ai_agents")
