"""Reusable AI agent skills and assignments.

Revision ID: n0c1d2e3f4g5
Revises: m9b0c1d2e3f4
"""
from alembic import op
import sqlalchemy as sa


revision = "n0c1d2e3f4g5"
down_revision = "m9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_agent_skills",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_ai_agent_skills_name"),
    )
    op.create_table(
        "ai_agent_skill_assignments",
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("ai_agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_id", sa.Uuid(), sa.ForeignKey("ai_agent_skills.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("agent_id", "skill_id", name="pk_ai_agent_skill_assignments"),
    )
    op.create_index("ix_ai_agent_skill_assignments_skill_id", "ai_agent_skill_assignments", ["skill_id"])


def downgrade():
    op.drop_index("ix_ai_agent_skill_assignments_skill_id", table_name="ai_agent_skill_assignments")
    op.drop_table("ai_agent_skill_assignments")
    op.drop_table("ai_agent_skills")
