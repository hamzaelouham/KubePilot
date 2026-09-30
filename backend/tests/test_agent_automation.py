"""Agent automation validates simple schedules and safe trigger lifecycle."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.base import Base
from app.models.entities import AIAgent, AIAgentAutomationTrigger, AIAgentRun, ClusterConnection, Event, UserAccount
from app.services import agent_automation
from app.services.agent_automation import AgentAutomationError, cron_matches, parse_cron, validate_schedule, _event_matches


@pytest.fixture()
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'automation.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    database = factory()
    owner = UserAccount(email="owner@example.com", password_hash="unused", role="operator", is_active=True)
    cluster = ClusterConnection(name="primary", endpoint="in-cluster", kubeconfig_ref="in-cluster", status="active")
    agent = AIAgent(name="Health", description="Health", instructions="Inspect", enabled=True, updated_at=datetime.now(timezone.utc))
    database.add_all([owner, cluster, agent])
    database.commit()
    yield database, owner, cluster, agent
    database.close()
    engine.dispose()


def test_simple_five_field_cron_matches_local_minute() -> None:
    moment = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    assert cron_matches(moment, "0 12 * * *")
    assert not cron_matches(moment.replace(minute=1), "0 12 * * *")
    assert cron_matches(moment, "0 12 * * 3")


def test_cron_rejects_seconds_and_named_extensions() -> None:
    with pytest.raises(AgentAutomationError, match="five-field"):
        parse_cron("0 0 12 * * *")
    with pytest.raises(AgentAutomationError, match="numbers"):
        parse_cron("0 12 * * MON")
    with pytest.raises(AgentAutomationError, match="timezone"):
        validate_schedule("0 12 * * *", "Not/AZone")


def test_event_matching_uses_optional_safe_filters() -> None:
    trigger = AIAgentAutomationTrigger(
        agent_id=uuid4(),
        cluster_id=uuid4(),
        trigger_type="kubernetes_event",
        timezone="UTC",
        owner_id=uuid4(),
        notification_destination_ids=[],
        event_kind="Pod",
        event_type="Warning",
        event_reason="BackOff",
    )
    event = Event(
        cluster_id=trigger.cluster_id,
        namespace="production",
        kind="Pod",
        name="web-0",
        event_type="Warning",
        reason="BackOff",
        message="back-off restarting failed container",
    )
    assert _event_matches(trigger, event)
    event.reason = "Pulled"
    assert not _event_matches(trigger, event)


def test_cron_step_and_weekday_normalization() -> None:
    monday = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
    sunday = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    assert cron_matches(monday, "0 12 * * 1")
    assert cron_matches(sunday, "0 12 * * 0")
    assert cron_matches(sunday, "0 12 * * 7")


def test_scheduler_deduplicates_a_schedule_occurrence(database) -> None:
    db, owner, cluster, agent = database
    trigger = AIAgentAutomationTrigger(
        agent_id=agent.id,
        cluster_id=cluster.id,
        trigger_type="schedule",
        cron_expression="0 12 * * *",
        timezone="UTC",
        owner_id=owner.id,
        notification_destination_ids=[],
        enabled=True,
    )
    db.add(trigger)
    db.commit()
    settings = SimpleNamespace(worker_poll_seconds=5)
    moment = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    assert agent_automation.evaluate_triggers(db, settings, moment) == 1
    assert agent_automation.evaluate_triggers(db, settings, moment) == 0
    assert db.scalar(select(AIAgentRun).where(AIAgentRun.trigger_id == trigger.id)) is not None


def test_worker_rechecks_owner_before_any_cluster_or_model_access(database) -> None:
    db, owner, cluster, agent = database
    run = AIAgentRun(
        agent_id=agent.id,
        owner_id=owner.id,
        cluster_id=cluster.id,
        trigger_type="schedule",
        dedupe_key="manual-owner-check",
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    owner.is_active = False
    db.commit()
    agent_automation.execute_run(db, run, Settings(auth_secret="x" * 32, database_url="sqlite:///:memory:", worker_enabled=False))
    assert run.status == "failed"
    assert run.result_code == "permission_denied"


def test_retention_removes_only_terminal_old_runs(database) -> None:
    db, owner, cluster, agent = database
    old = datetime.now(timezone.utc) - timedelta(days=40)
    db.add_all([
        AIAgentRun(agent_id=agent.id, owner_id=owner.id, cluster_id=cluster.id, trigger_type="schedule", dedupe_key="old-terminal", status="succeeded", completed_at=old),
        AIAgentRun(agent_id=agent.id, owner_id=owner.id, cluster_id=cluster.id, trigger_type="schedule", dedupe_key="active-run", status="running"),
    ])
    db.commit()
    assert agent_automation.cleanup_runs(db, now=datetime.now(timezone.utc)) == 1
    assert db.scalar(select(AIAgentRun).where(AIAgentRun.dedupe_key == "old-terminal")) is None
    assert db.scalar(select(AIAgentRun).where(AIAgentRun.dedupe_key == "active-run")) is not None
