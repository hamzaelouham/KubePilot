"""Add agent automation triggers and background runs.

Revision ID: q3f4g5h6i7j8
Revises: p2e3f4g5h6i7
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "q3f4g5h6i7j8"
down_revision: str | None = "p2e3f4g5h6i7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.add_column("events", sa.Column("event_type", sa.String(length=32), nullable=True))
    op.add_column("events", sa.Column("reason", sa.String(length=128), nullable=True))

    op.create_table(
        "ai_agent_automation_triggers",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("agent_id", uuid_type, nullable=False),
        sa.Column("cluster_id", uuid_type, nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("cron_expression", sa.String(length=128), nullable=True),
        sa.Column("timezone", sa.String(length=64), server_default="UTC", nullable=False),
        sa.Column("namespace", sa.String(length=253), nullable=True),
        sa.Column("event_kind", sa.String(length=64), nullable=True),
        sa.Column("event_name", sa.String(length=253), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=True),
        sa.Column("event_reason", sa.String(length=128), nullable=True),
        sa.Column("owner_id", uuid_type, nullable=False),
        sa.Column("notification_destination_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", uuid_type, nullable=True),
        sa.Column("updated_by_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_agent_automation_triggers_agent_id", "ai_agent_automation_triggers", ["agent_id"])
    op.create_index("ix_ai_agent_automation_triggers_cluster_id", "ai_agent_automation_triggers", ["cluster_id"])
    op.create_index("ix_ai_agent_automation_triggers_owner_id", "ai_agent_automation_triggers", ["owner_id"])
    op.create_index("ix_ai_agent_automation_triggers_created_by_id", "ai_agent_automation_triggers", ["created_by_id"])
    op.create_index("ix_ai_agent_automation_triggers_updated_by_id", "ai_agent_automation_triggers", ["updated_by_id"])
    op.create_index("ix_ai_agent_automation_triggers_enabled_type", "ai_agent_automation_triggers", ["enabled", "trigger_type"])
    op.create_index("ix_ai_agent_automation_triggers_agent_enabled", "ai_agent_automation_triggers", ["agent_id", "enabled"])

    op.create_table(
        "ai_agent_runs",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("trigger_id", uuid_type, nullable=True),
        sa.Column("agent_id", uuid_type, nullable=False),
        sa.Column("owner_id", uuid_type, nullable=False),
        sa.Column("cluster_id", uuid_type, nullable=False),
        sa.Column("namespace", sa.String(length=253), nullable=True),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_id", uuid_type, nullable=True),
        sa.Column("dedupe_key", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("result_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("log_output", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trigger_id"], ["ai_agent_automation_triggers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_ai_agent_runs_dedupe_key"),
    )
    op.create_index("ix_ai_agent_runs_trigger_id", "ai_agent_runs", ["trigger_id"])
    op.create_index("ix_ai_agent_runs_agent_id", "ai_agent_runs", ["agent_id"])
    op.create_index("ix_ai_agent_runs_owner_id", "ai_agent_runs", ["owner_id"])
    op.create_index("ix_ai_agent_runs_cluster_id", "ai_agent_runs", ["cluster_id"])
    op.create_index("ix_ai_agent_runs_event_id", "ai_agent_runs", ["event_id"])
    op.create_index("ix_ai_agent_runs_status_created", "ai_agent_runs", ["status", "created_at"])
    op.create_index("ix_ai_agent_runs_agent_created", "ai_agent_runs", ["agent_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_agent_runs_agent_created", table_name="ai_agent_runs")
    op.drop_index("ix_ai_agent_runs_status_created", table_name="ai_agent_runs")
    op.drop_index("ix_ai_agent_runs_event_id", table_name="ai_agent_runs")
    op.drop_index("ix_ai_agent_runs_cluster_id", table_name="ai_agent_runs")
    op.drop_index("ix_ai_agent_runs_owner_id", table_name="ai_agent_runs")
    op.drop_index("ix_ai_agent_runs_agent_id", table_name="ai_agent_runs")
    op.drop_index("ix_ai_agent_runs_trigger_id", table_name="ai_agent_runs")
    op.drop_table("ai_agent_runs")

    op.drop_index("ix_ai_agent_automation_triggers_agent_enabled", table_name="ai_agent_automation_triggers")
    op.drop_index("ix_ai_agent_automation_triggers_enabled_type", table_name="ai_agent_automation_triggers")
    op.drop_index("ix_ai_agent_automation_triggers_updated_by_id", table_name="ai_agent_automation_triggers")
    op.drop_index("ix_ai_agent_automation_triggers_created_by_id", table_name="ai_agent_automation_triggers")
    op.drop_index("ix_ai_agent_automation_triggers_owner_id", table_name="ai_agent_automation_triggers")
    op.drop_index("ix_ai_agent_automation_triggers_cluster_id", table_name="ai_agent_automation_triggers")
    op.drop_index("ix_ai_agent_automation_triggers_agent_id", table_name="ai_agent_automation_triggers")
    op.drop_table("ai_agent_automation_triggers")
    op.drop_column("events", "reason")
    op.drop_column("events", "event_type")
