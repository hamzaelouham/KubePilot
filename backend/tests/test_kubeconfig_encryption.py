import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import ConfigurationError
from app.models.base import Base
from app.models.entities import ClusterConnection
from app.services.kubeconfig_encryption import PREFIX, migrate_kubeconfigs


def test_database_stores_ciphertext_and_clients_read_plaintext():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        row = ClusterConnection(name="test", endpoint="https://example.com", kubeconfig_ref="", kubeconfig_content="private token")
        session.add(row)
        session.commit()
        raw = session.execute(text("select kubeconfig_content from cluster_connections")).scalar_one()
        assert raw.startswith(PREFIX) and "private token" not in raw
        session.expire_all()
        assert row.kubeconfig_content == "private token"
        row.kubeconfig_content = "new private token"
        session.commit()
        assert row.kubeconfig_content == "new private token"
        assert session.execute(text("select kubeconfig_content from cluster_connections")).scalar_one() != raw


def test_migration_is_idempotent_and_missing_key_preserves_plaintext(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    table = ClusterConnection.__table__
    with engine.begin() as connection:
        connection.execute(table.insert().values(name="old", endpoint="x", kubeconfig_ref="", kubeconfig_content="old credential"))
    with monkeypatch.context() as patch:
        patch.delenv("KUBEPILOT_ENCRYPTION_KEY")
        with pytest.raises(ConfigurationError), engine.begin() as connection:
            migrate_kubeconfigs(connection, table)
    with engine.begin() as connection:
        assert connection.execute(text("select kubeconfig_content from cluster_connections")).scalar_one() == "old credential"
        migrate_kubeconfigs(connection, table)
        encrypted = connection.execute(text("select kubeconfig_content from cluster_connections")).scalar_one()
        migrate_kubeconfigs(connection, table)
        assert connection.execute(text("select kubeconfig_content from cluster_connections")).scalar_one() == encrypted
    with Session(engine) as session:
        assert session.query(ClusterConnection).one().kubeconfig_content == "old credential"


def test_missing_key_corruption_and_unmigrated_records_fail_closed(monkeypatch):
    row = ClusterConnection(kubeconfig_content="secret")
    with monkeypatch.context() as patch:
        patch.delenv("KUBEPILOT_ENCRYPTION_KEY")
        with pytest.raises(ConfigurationError):
            _ = row.kubeconfig_content
        with pytest.raises(ConfigurationError):
            row.kubeconfig_content = "replacement"
    assert row.kubeconfig_content == "secret"
    for invalid in ["plaintext", PREFIX + "corrupt"]:
        row._kubeconfig_content = invalid
        with pytest.raises(ConfigurationError):
            _ = row.kubeconfig_content
