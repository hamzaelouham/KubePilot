"""add user rbac columns

Revision ID: a1b2c3d4e5f6
Revises: 570583371bec
Create Date: 2026-09-06 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "570583371bec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audit_actions_table() -> sa.Table:
    uuid_type = sa.Uuid(as_uuid=True)
    return sa.Table(
        "audit_actions",
        sa.MetaData(),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("actor_id", uuid_type, nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=128), nullable=False),
        sa.Column("resource_id", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["actor_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.Index("ix_audit_actions_actor_id", "actor_id"),
        sa.Index("ix_audit_actions_created", "created_at"),
    )


def _audit_actions_after_table() -> sa.Table:
    uuid_type = sa.Uuid(as_uuid=True)
    return sa.Table(
        "audit_actions",
        sa.MetaData(),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("actor_id", uuid_type, nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=128), nullable=False),
        sa.Column("resource_id", sa.String(length=512), nullable=False),
        sa.Column("target_user_id", uuid_type, nullable=True),
        sa.Column("result", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["actor_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["user_accounts.id"],
            name="fk_audit_actions_target_user",
            ondelete="RESTRICT",
        ),
        sa.Index("ix_audit_actions_actor_id", "actor_id"),
        sa.Index("ix_audit_actions_target_user_id", "target_user_id"),
        sa.Index("ix_audit_actions_created", "created_at"),
    )


def upgrade() -> None:
    op.add_column(
        "user_accounts",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column("user_accounts", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_accounts", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_accounts", sa.Column("password_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "user_accounts",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "sessions",
        sa.Column("restricted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    with op.batch_alter_table("audit_actions", copy_from=_audit_actions_table()) as batch_op:
        batch_op.alter_column("actor_id", existing_type=sa.Uuid(as_uuid=True), nullable=True)
        batch_op.add_column(sa.Column("target_user_id", sa.Uuid(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column("result", sa.String(length=64), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("context", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_audit_actions_target_user", "user_accounts", ["target_user_id"], ["id"], ondelete="RESTRICT"
        )
        batch_op.create_index("ix_audit_actions_target_user_id", ["target_user_id"])


def downgrade() -> None:
    with op.batch_alter_table("audit_actions", copy_from=_audit_actions_after_table()) as batch_op:
        batch_op.drop_index("ix_audit_actions_target_user_id")
        batch_op.drop_constraint("fk_audit_actions_target_user", type_="foreignkey")
        batch_op.drop_column("target_user_id")
        batch_op.drop_column("result")
        batch_op.drop_column("context")
        batch_op.alter_column("actor_id", existing_type=sa.Uuid(as_uuid=True), nullable=False)

    op.drop_column("sessions", "restricted")
    op.drop_column("user_accounts", "must_change_password")
    op.drop_column("user_accounts", "password_expires_at")
    op.drop_column("user_accounts", "password_changed_at")
    op.drop_column("user_accounts", "last_login_at")
    op.drop_column("user_accounts", "updated_at")
    op.drop_column("user_accounts", "is_active")
