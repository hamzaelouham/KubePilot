"""Add account-backed Assistant conversations and sanitized parts."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "r4g5h6i7j8k9"
down_revision: str | None = "q3f4g5h6i7j8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.create_table(
        "assistant_conversations",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("owner_id", uuid_type, nullable=False),
        sa.Column("title", sa.String(length=160), server_default="New conversation", nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("model_id", uuid_type, nullable=True),
        sa.Column("agent_id", uuid_type, nullable=True),
        sa.Column("cluster_id", uuid_type, nullable=True),
        sa.Column("cluster_name", sa.String(length=253), nullable=False),
        sa.Column("namespace", sa.String(length=253), nullable=True),
        sa.Column("resource", sa.String(length=64), nullable=True),
        sa.Column("resource_name", sa.String(length=253), nullable=True),
        sa.Column("release", sa.String(length=253), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_id"], ["ai_model_configs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster_connections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_conversations_owner_id", "assistant_conversations", ["owner_id"])
    op.create_index("ix_assistant_conversations_model_id", "assistant_conversations", ["model_id"])
    op.create_index("ix_assistant_conversations_agent_id", "assistant_conversations", ["agent_id"])
    op.create_index("ix_assistant_conversations_cluster_id", "assistant_conversations", ["cluster_id"])
    op.create_index("ix_assistant_conversations_owner_updated", "assistant_conversations", ["owner_id", "updated_at"])
    op.create_index("ix_assistant_conversations_updated", "assistant_conversations", ["updated_at"])

    op.create_table(
        "assistant_conversation_parts",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("conversation_id", uuid_type, nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("part_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("proposal_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["assistant_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["proposal_id"], ["assistant_proposals.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "sequence", name="uq_assistant_conversation_parts_sequence"),
    )
    op.create_index("ix_assistant_conversation_parts_conversation_id", "assistant_conversation_parts", ["conversation_id"])
    op.create_index("ix_assistant_conversation_parts_proposal_id", "assistant_conversation_parts", ["proposal_id"])
    op.create_index("ix_assistant_conversation_parts_order", "assistant_conversation_parts", ["conversation_id", "sequence"])


def downgrade() -> None:
    op.drop_index("ix_assistant_conversation_parts_order", table_name="assistant_conversation_parts")
    op.drop_index("ix_assistant_conversation_parts_proposal_id", table_name="assistant_conversation_parts")
    op.drop_index("ix_assistant_conversation_parts_conversation_id", table_name="assistant_conversation_parts")
    op.drop_table("assistant_conversation_parts")
    op.drop_index("ix_assistant_conversations_updated", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_owner_updated", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_cluster_id", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_agent_id", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_model_id", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_owner_id", table_name="assistant_conversations")
    op.drop_table("assistant_conversations")
