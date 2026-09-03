"""create application schema

Revision ID: dd752e8644a9
Revises: 
Create Date: 2026-09-03 10:40:15.626234
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'dd752e8644a9'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    timestamp_type = sa.DateTime(timezone=True)

    op.create_table(
        "user_accounts",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False, server_default="operator"),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_user_accounts_email", "user_accounts", ["email"], unique=False)

    op.create_table(
        "cluster_connections",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("endpoint", sa.String(length=2048), nullable=False),
        sa.Column("kubeconfig_ref", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_cluster_connections_status", "cluster_connections", ["status"], unique=False)

    op.create_table(
        "sessions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("issued_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", timestamp_type, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_index("ix_sessions_active_expiry", "sessions", ["user_id", "expires_at"], unique=False)

    op.create_table(
        "namespaces",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("cluster_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=253), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cluster_id", "name", name="uq_namespaces_cluster_name"),
    )
    op.create_index("ix_namespaces_cluster_status", "namespaces", ["cluster_id", "status"], unique=False)

    op.create_table(
        "workloads",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("cluster_id", uuid_type, nullable=False),
        sa.Column("namespace", sa.String(length=253), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=253), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("image", sa.String(length=2048), nullable=True),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cluster_id", "namespace", "kind", "name", name="uq_workloads_identity"),
    )
    op.create_index("ix_workloads_cluster_namespace", "workloads", ["cluster_id", "namespace"], unique=False)

    for table_name, columns, constraint_name in (
        ("pods", [sa.Column("cluster_id", uuid_type, nullable=False), sa.Column("namespace", sa.String(length=253), nullable=False), sa.Column("name", sa.String(length=253), nullable=False), sa.Column("status", sa.String(length=32), nullable=False), sa.Column("ready", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("restarts", sa.Integer(), nullable=False, server_default="0"), sa.Column("age", sa.String(length=64), nullable=False)], "uq_pods_identity"),
        ("deployments", [sa.Column("cluster_id", uuid_type, nullable=False), sa.Column("namespace", sa.String(length=253), nullable=False), sa.Column("name", sa.String(length=253), nullable=False), sa.Column("replicas", sa.Integer(), nullable=False, server_default="0"), sa.Column("status", sa.String(length=32), nullable=False), sa.Column("image", sa.String(length=2048), nullable=True)], "uq_deployments_identity"),
        ("services", [sa.Column("cluster_id", uuid_type, nullable=False), sa.Column("namespace", sa.String(length=253), nullable=False), sa.Column("name", sa.String(length=253), nullable=False), sa.Column("selector", sa.JSON(), nullable=False), sa.Column("ports", sa.JSON(), nullable=False), sa.Column("status", sa.String(length=32), nullable=False)], "uq_services_identity"),
    ):
        op.create_table(
            table_name,
            sa.Column("id", uuid_type, nullable=False),
            *columns,
            sa.ForeignKeyConstraint(["cluster_id"], ["cluster_connections.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("cluster_id", "namespace", "name", name=constraint_name),
        )
        op.create_index(f"ix_{table_name}_cluster_namespace", table_name, ["cluster_id", "namespace"], unique=False)

    op.create_table(
        "nodes",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("cluster_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=253), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cluster_id", "name", name="uq_nodes_identity"),
    )
    op.create_index("ix_nodes_cluster_status", "nodes", ["cluster_id", "status"], unique=False)

    op.create_table(
        "events",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("cluster_id", uuid_type, nullable=False),
        sa.Column("namespace", sa.String(length=253), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=253), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["cluster_id"], ["cluster_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_cluster_namespace_created", "events", ["cluster_id", "namespace", "created_at"], unique=False)

    op.create_table(
        "audit_actions",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("actor_id", uuid_type, nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=128), nullable=False),
        sa.Column("resource_id", sa.String(length=512), nullable=False),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["actor_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_actions_actor_id", "audit_actions", ["actor_id"], unique=False)
    op.create_index("ix_audit_actions_created", "audit_actions", ["created_at"], unique=False)

    op.create_table(
        "user_preferences",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("default_namespace", sa.String(length=253), nullable=True),
        sa.Column("view_settings", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_index("ix_audit_actions_created", table_name="audit_actions")
    op.drop_index("ix_audit_actions_actor_id", table_name="audit_actions")
    op.drop_table("audit_actions")
    op.drop_index("ix_events_cluster_namespace_created", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_nodes_cluster_status", table_name="nodes")
    op.drop_table("nodes")
    for table_name in ("services", "deployments", "pods"):
        op.drop_index(f"ix_{table_name}_cluster_namespace", table_name=table_name)
        op.drop_table(table_name)
    op.drop_index("ix_workloads_cluster_namespace", table_name="workloads")
    op.drop_table("workloads")
    op.drop_index("ix_namespaces_cluster_status", table_name="namespaces")
    op.drop_table("namespaces")
    op.drop_index("ix_sessions_active_expiry", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_cluster_connections_status", table_name="cluster_connections")
    op.drop_table("cluster_connections")
    op.drop_index("ix_user_accounts_email", table_name="user_accounts")
    op.drop_table("user_accounts")
