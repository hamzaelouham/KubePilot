import pytest
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
	"application_settings",
	"application_credentials",
	"ai_model_configs",
	"ai_agents",
	"ai_agent_skills",
	"ai_agent_skill_assignments",
	"ai_agent_tool_assignments",
	"ai_agent_notification_destinations",
	"ai_agent_automation_triggers",
	"ai_agent_runs",
	"assistant_conversations",
	"assistant_conversation_parts",
	"integration_connections",
	"integration_oauth_states",
	"integration_delivery_jobs",
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
	assert {constraint.name for constraint in Base.metadata.tables["ai_model_configs"].constraints} >= {
		"uq_ai_model_configs_provider_external"
	}
	assert {index.name for index in Base.metadata.tables["ai_model_configs"].indexes} >= {
		"uq_ai_model_configs_global_default"
	}


@pytest.mark.parametrize("table,column,target,ondelete", [
	("ai_agent_notification_destinations", "agent_id", "ai_agents.id", "CASCADE"),
	("ai_agent_skill_assignments", "agent_id", "ai_agents.id", "CASCADE"),
	("ai_agent_skill_assignments", "skill_id", "ai_agent_skills.id", "RESTRICT"),
	("ai_agent_tool_assignments", "agent_id", "ai_agents.id", "CASCADE"),
	("ai_agent_automation_triggers", "owner_id", "user_accounts.id", "RESTRICT"),
	("ai_agent_runs", "owner_id", "user_accounts.id", "RESTRICT"),
	("assistant_conversations", "owner_id", "user_accounts.id", "CASCADE"),
	("assistant_conversation_parts", "conversation_id", "assistant_conversations.id", "CASCADE"),
])
def test_agent_and_conversation_ownership_constraints(table, column, target, ondelete) -> None:
	field = Base.metadata.tables[table].c[column]
	assert field.nullable is False
	assert {(key.target_fullname, key.ondelete) for key in field.foreign_keys} == {(target, ondelete)}


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
