"""allow live Helm release action jobs without Marketplace metadata

Revision ID: a7b8c9d0e1f2
Revises: f2a3b4c5d6e7
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("installation_jobs") as batch:
        for column in ("package_id", "package_name", "chart_name", "chart_repository", "chart_version"):
            batch.alter_column(column, nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("installation_jobs") as batch:
        for column in ("package_id", "package_name", "chart_name", "chart_repository", "chart_version"):
            batch.alter_column(column, nullable=False)
