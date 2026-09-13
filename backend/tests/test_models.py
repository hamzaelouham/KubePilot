from sqlalchemy import create_engine, inspect

from app.models.base import Base
from app.models import UserAccount


EXPECTED_TABLES = {
	"user_accounts",
	"sessions",
	"cluster_connections",
	"namespaces",
	"workloads",
	"pods",
	"deployments",
	"services",
	"nodes",
	"events",
	"audit_actions",
	"user_preferences",
	"installation_jobs",
	"helm_repositories",
	"assistant_proposals",
}


def test_metadata_contains_expected_tables_and_ownership_constraints() -> None:
	engine = create_engine("sqlite:///:memory:")
	Base.metadata.create_all(engine)
	database_tables = set(inspect(engine).get_table_names())

	assert database_tables == EXPECTED_TABLES
	assert {constraint.name for constraint in Base.metadata.tables["namespaces"].constraints} >= {
		"uq_namespaces_cluster_name"
	}
	assert any(
		foreign_key.target_fullname == "cluster_connections.id"
		for foreign_key in Base.metadata.tables["namespaces"].c.cluster_id.foreign_keys
	)


def test_sensitive_values_are_hash_or_reference_fields() -> None:
	user_columns = set(UserAccount.__table__.columns.keys())
	session_columns = set(Base.metadata.tables["sessions"].columns.keys())
	cluster_columns = set(Base.metadata.tables["cluster_connections"].columns.keys())

	assert "password" not in user_columns
	assert "password_hash" in user_columns
	assert "token" not in session_columns
	assert "token_hash" in session_columns
	assert "kubeconfig" not in cluster_columns
	assert "kubeconfig_ref" in cluster_columns
