"""add user_accounts is_active

Revision ID: 570583371bec
Revises: dd752e8644a9
Create Date: 2026-09-05 23:19:09.216870
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '570583371bec'
down_revision: Union[str, None] = 'dd752e8644a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_accounts",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("user_accounts", "is_active")