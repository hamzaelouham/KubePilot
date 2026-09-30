"""Allowlisted tool assignments for AI agents.

Revision ID: o1d2e3f4g5h6
Revises: n0c1d2e3f4g5
"""
from alembic import op
import sqlalchemy as sa


revision = "o1d2e3f4g5h6"
down_revision = "n0c1d2e3f4g5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_agent_tool_assignments",
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_id", sa.String(128), nullable=False),
        sa.PrimaryKeyConstraint("agent_id", "tool_id", name="pk_ai_agent_tool_assignments"),
    )


def downgrade():
    op.drop_table("ai_agent_tool_assignments")
