from unittest.mock import MagicMock
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.jobs.ownership import LOCK_ID, worker_ownership
from app.jobs.worker import _recover_interrupted_jobs
from app.models.base import Base
from app.models.entities import ClusterConnection, InstallationJob, IntegrationConnection, IntegrationDeliveryJob, UserAccount, AIAgent, AIAgentRun


def test_sqlite_ownership_excludes_second_worker_and_releases_after_failure(tmp_path):
    first = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    second = create_engine(first.url)
    try:
        try:
            with worker_ownership(first) as owned:
                assert owned
                with worker_ownership(second) as other:
                    assert not other
                raise ValueError("worker failed")
        except ValueError:
            pass
        with worker_ownership(second) as other:
            assert other
    finally:
        first.dispose()
        second.dispose()


def test_postgres_keeps_ownership_connection_until_work_finishes():
    connection = MagicMock()
    connection.scalar.return_value = True
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    engine.connect.return_value.__enter__.return_value = connection
    with worker_ownership(engine) as owned:
        assert owned
        connection.execute.assert_not_called()
    assert "pg_advisory_unlock" in str(connection.execute.call_args.args[0])
    assert connection.execute.call_args.args[1] == {"key": LOCK_ID}
    connection.scalar.return_value = False
    connection.execute.reset_mock()
    with worker_ownership(engine) as owned:
        assert not owned
    connection.execute.assert_not_called()


def test_recovery_never_requeues_interrupted_installations():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as database:
        cluster = ClusterConnection(name="in-cluster", endpoint="in-cluster", kubeconfig_ref="")
        database.add(cluster)
        database.flush()
        job = InstallationJob(cluster_id=cluster.id, namespace="default", release_name="test", status="running")
        queued = InstallationJob(cluster_id=cluster.id, namespace="default", release_name="pending", status="queued")
        database.add_all([job, queued])
        database.commit()
        _recover_interrupted_jobs(database)
        database.refresh(job)
        database.refresh(queued)
        assert job.status == "failed" and "unknown" in job.error_message
        assert queued.status == "queued"
        _recover_interrupted_jobs(database)
        assert job.status == "failed"


def test_interrupted_deliveries_and_agent_runs_are_terminal():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as database:
        now = datetime.now(timezone.utc)
        connection = IntegrationConnection(provider="slack", status="connected")
        owner = UserAccount(email="worker@example.com", password_hash="unused", role="operator", is_active=True)
        cluster = ClusterConnection(name="primary", endpoint="in-cluster", kubeconfig_ref="")
        agent = AIAgent(name="worker", description="", instructions="read", enabled=True, updated_at=now)
        database.add_all([connection, owner, cluster, agent])
        database.flush()
        delivery = IntegrationDeliveryJob(connection_id=connection.id, provider="slack", idempotency_key="test", event_type="test", destination_hint="hidden", payload_ciphertext="unused", next_attempt_at=now, status="running")
        run = AIAgentRun(agent_id=agent.id, owner_id=owner.id, cluster_id=cluster.id, trigger_type="schedule", dedupe_key="test", status="running")
        database.add_all([delivery, run])
        database.commit()
        _recover_interrupted_jobs(database)
        database.refresh(delivery)
        database.refresh(run)
        assert delivery.status == "outcome_unknown"
        assert run.status == "failed" and run.result_code == "worker_interrupted"
        assert delivery.completed_at and run.completed_at
