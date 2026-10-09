"""Encrypt existing cluster kubeconfigs without changing the storage column."""

from alembic import context, op
import sqlalchemy as sa

from app.services.kubeconfig_encryption import migrate_kubeconfigs

revision = "s5h6i7j8k9l0"
down_revision = "r4g5h6i7j8k9"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("Kubeconfig encryption requires an online migration with the encryption key")
    table = sa.table("cluster_connections", sa.column("id", sa.Uuid()), sa.column("kubeconfig_content", sa.Text()))
    migrate_kubeconfigs(op.get_bind(), table)


def downgrade():
    # Older code must not consume ciphertext as YAML; never restore plaintext automatically.
    raise RuntimeError("Kubeconfig encryption cannot be downgraded safely")
