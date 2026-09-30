"""Worker helpers for durable integration delivery jobs."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.audit import AuditEvent, record_audit
from app.core.config import Settings
from app.models.entities import IntegrationDeliveryJob
from app.services.integration_delivery import BACKOFFS, DeliveryDispatchError, dispatch_delivery, source_context


def requeue_running_deliveries(database) -> None:
    database.execute(
        update(IntegrationDeliveryJob)
        .where(IntegrationDeliveryJob.status == "running")
        .values(status="queued", started_at=None, next_attempt_at=_now())
    )
    database.commit()


def claim_next_delivery(database) -> IntegrationDeliveryJob | None:
    now = _now()
    row = database.scalar(
        select(IntegrationDeliveryJob)
        .where(
            IntegrationDeliveryJob.status == "queued",
            IntegrationDeliveryJob.next_attempt_at <= now,
        )
        .order_by(IntegrationDeliveryJob.next_attempt_at, IntegrationDeliveryJob.created_at, IntegrationDeliveryJob.id)
        .limit(1)
    )
    if row is None:
        return None
    result = database.execute(
        update(IntegrationDeliveryJob)
        .where(
            IntegrationDeliveryJob.id == row.id,
            IntegrationDeliveryJob.status == "queued",
            IntegrationDeliveryJob.next_attempt_at <= now,
        )
        .values(
            status="running",
            started_at=now,
            attempt_count=IntegrationDeliveryJob.attempt_count + 1,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        return None
    row.status = "running"
    row.started_at = now
    row.attempt_count += 1
    database.commit()
    return row


def run_pending_deliveries(database, settings: Settings) -> None:
    while True:
        row = claim_next_delivery(database)
        if row is None:
            return
        _process_delivery(database, settings, row)


def _process_delivery(database, settings: Settings, row: IntegrationDeliveryJob) -> None:
    record_audit(
        database,
        AuditEvent.INTEGRATION_DELIVERY_STARTED,
        None,
        "integration_delivery",
        str(row.id),
        result="running",
        context={
            "provider": row.provider,
            "status": "running",
            "attempt_count": row.attempt_count,
            **source_context(row.agent_id, row.agent_destination_id),
        },
    )
    database.commit()
    try:
        dispatch_delivery(database, settings, row)
    except DeliveryDispatchError as error:
        database.rollback()
        if error.outcome_unknown:
            _finish_failure(database, row, error.code, outcome_unknown=True)
            return
        if error.retryable and row.attempt_count < row.max_attempts:
            delay = BACKOFFS[min(row.attempt_count - 1, len(BACKOFFS) - 1)]
            row.status = "queued"
            row.next_attempt_at = _now() + delay
            row.last_error_code = error.code
            row.started_at = None
            database.commit()
            record_audit(
                database,
                AuditEvent.INTEGRATION_DELIVERY_RETRY_SCHEDULED,
                None,
                "integration_delivery",
                str(row.id),
                result="queued",
                context={
                    "provider": row.provider,
                    "status": "queued",
                    "attempt_count": row.attempt_count,
                    "error_code": error.code,
                    **source_context(row.agent_id, row.agent_destination_id),
                },
            )
            database.commit()
            return
        _finish_failure(database, row, error.code)
        return
    except Exception:  # noqa: BLE001
        database.rollback()
        _finish_failure(database, row, "integration_delivery_failed")
        return

    row.status = "succeeded"
    row.last_error_code = None
    row.completed_at = _now()
    database.commit()
    record_audit(
        database,
        AuditEvent.INTEGRATION_DELIVERY_SUCCEEDED,
        None,
        "integration_delivery",
        str(row.id),
        result="success",
        context={
            "provider": row.provider,
            "status": "succeeded",
            "attempt_count": row.attempt_count,
            **source_context(row.agent_id, row.agent_destination_id),
        },
    )
    database.commit()


def _finish_failure(database, row, error_code: str, *, outcome_unknown: bool = False) -> None:
    row.status = "outcome_unknown" if outcome_unknown else "failed"
    row.last_error_code = error_code
    row.completed_at = _now()
    row.started_at = row.started_at or _now()
    database.commit()
    audit_event = (
        AuditEvent.INTEGRATION_DELIVERY_OUTCOME_UNKNOWN
        if outcome_unknown
        else AuditEvent.INTEGRATION_DELIVERY_FAILED
    )
    record_audit(
        database,
        audit_event,
        None,
        "integration_delivery",
        str(row.id),
        result="unknown" if outcome_unknown else "failure",
        context={
            "provider": row.provider,
            "status": row.status,
            "attempt_count": row.attempt_count,
            "error_code": error_code,
            **source_context(row.agent_id, row.agent_destination_id),
        },
    )
    database.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)
