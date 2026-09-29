"""Add integration connection lifecycle storage.

Revision ID: k7f8a9b0c1d2
Revises: j6e7f8a9b0c1
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "k7f8a9b0c1d2"
down_revision: str | None = "j6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.create_table(
        "integration_connections",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="not_connected", nullable=False),
        sa.Column("external_account_id", sa.String(length=512), nullable=True),
        sa.Column("external_account_label", sa.String(length=512), nullable=True),
        sa.Column("granted_scopes", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("access_token_ciphertext", sa.Text(), nullable=True),
        sa.Column("refresh_token_ciphertext", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", uuid_type, nullable=True),
        sa.Column("updated_by_id", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", name="uq_integration_connections_provider"),
    )
    op.create_index("ix_integration_connections_created_by_id", "integration_connections", ["created_by_id"])
    op.create_index("ix_integration_connections_updated_by_id", "integration_connections", ["updated_by_id"])
    op.create_index("ix_integration_connections_status", "integration_connections", ["status"])

    op.create_table(
        "integration_oauth_states",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("state_digest", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("actor_id", uuid_type, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_digest", name="uq_integration_oauth_states_digest"),
    )
    op.create_index("ix_integration_oauth_states_actor_id", "integration_oauth_states", ["actor_id"])
    op.create_index("ix_integration_oauth_states_expires_at", "integration_oauth_states", ["expires_at"])
    op.create_index(
        "ix_integration_oauth_states_provider_expiry",
        "integration_oauth_states",
        ["provider", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_integration_oauth_states_provider_expiry", table_name="integration_oauth_states")
    op.drop_index("ix_integration_oauth_states_expires_at", table_name="integration_oauth_states")
    op.drop_index("ix_integration_oauth_states_actor_id", table_name="integration_oauth_states")
    op.drop_table("integration_oauth_states")
    op.drop_index("ix_integration_connections_status", table_name="integration_connections")
    op.drop_index("ix_integration_connections_updated_by_id", table_name="integration_connections")
    op.drop_index("ix_integration_connections_created_by_id", table_name="integration_connections")
    op.drop_table("integration_connections")
