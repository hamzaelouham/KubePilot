"""add chart_repository_url to installation_jobs

Revision ID: d1e2f3a4b5c6
Revises: c4d5e6f7a8b9
Create Date: 2026-09-08 17:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "installation_jobs",
        sa.Column("chart_repository_url", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("installation_jobs", "chart_repository_url")