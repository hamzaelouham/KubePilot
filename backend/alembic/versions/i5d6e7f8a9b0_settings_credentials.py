"""add registered application settings and encrypted credentials"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i5d6e7f8a9b0"
down_revision: Union[str, None] = "h4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    timestamp_type = sa.DateTime(timezone=True)

    op.create_table(
        "application_settings",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("created_by_id", uuid_type, nullable=True),
        sa.Column("updated_by_id", uuid_type, nullable=True),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_application_settings_key"),
    )
    op.create_index("ix_application_settings_created_by_id", "application_settings", ["created_by_id"])
    op.create_index("ix_application_settings_updated_by_id", "application_settings", ["updated_by_id"])

    op.create_table(
        "application_credentials",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("credential_key", sa.String(length=128), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("created_by_id", uuid_type, nullable=True),
        sa.Column("updated_by_id", uuid_type, nullable=True),
        sa.Column("created_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", timestamp_type, nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_key", name="uq_application_credentials_key"),
    )
    op.create_index("ix_application_credentials_created_by_id", "application_credentials", ["created_by_id"])
    op.create_index("ix_application_credentials_updated_by_id", "application_credentials", ["updated_by_id"])


def downgrade() -> None:
    op.drop_index("ix_application_credentials_updated_by_id", table_name="application_credentials")
    op.drop_index("ix_application_credentials_created_by_id", table_name="application_credentials")
    op.drop_table("application_credentials")
    op.drop_index("ix_application_settings_updated_by_id", table_name="application_settings")
    op.drop_index("ix_application_settings_created_by_id", table_name="application_settings")
    op.drop_table("application_settings")
