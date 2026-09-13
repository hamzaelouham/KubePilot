"""add global Helm repository connections

Revision ID: g3b4c5d6e7f8
Revises: a7b8c9d0e1f2
Create Date: 2026-09-13 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g3b4c5d6e7f8"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    timestamp_type = sa.DateTime(timezone=True)
    op.create_table(
        "helm_repositories",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=63), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("created_by_id", uuid_type, nullable=True),
        sa.Column("updated_by_id", uuid_type, nullable=True),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_helm_repositories_name"),
        sa.UniqueConstraint("url", name="uq_helm_repositories_url"),
    )
    op.create_index("ix_helm_repositories_created_by_id", "helm_repositories", ["created_by_id"], unique=False)
    op.create_index("ix_helm_repositories_updated_by_id", "helm_repositories", ["updated_by_id"], unique=False)
    op.create_index("ix_helm_repositories_name", "helm_repositories", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_helm_repositories_name", table_name="helm_repositories")
    op.drop_index("ix_helm_repositories_updated_by_id", table_name="helm_repositories")
    op.drop_index("ix_helm_repositories_created_by_id", table_name="helm_repositories")
    op.drop_table("helm_repositories")
