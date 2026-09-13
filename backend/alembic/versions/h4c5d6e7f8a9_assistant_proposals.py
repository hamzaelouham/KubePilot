"""Durable, one-use assistant action proposals."""
from alembic import op
import sqlalchemy as sa

revision = "h4c5d6e7f8a9"
down_revision = "g3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("cluster_id", sa.Uuid(), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("precondition", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.JSON()),
    )
    op.create_index("ix_assistant_proposals_actor_id", "assistant_proposals", ["actor_id"])


def downgrade():
    op.drop_index("ix_assistant_proposals_actor_id", "assistant_proposals")
    op.drop_table("assistant_proposals")
