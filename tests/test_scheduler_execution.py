from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.scheduler.scheduler as scheduler_module
from app.db.models import Base, Job


TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture(autouse=True)
def prepare_test_database(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(
        scheduler_module,
        "SessionLocal",
        TestSessionLocal,
    )

    yield

    Base.metadata.drop_all(bind=test_engine)


def create_scheduled_job(
    *,
    is_enabled: bool = True,
    schedule_enabled: bool = True,
    schedule_paused: bool = False,
) -> int:
    db: Session = TestSessionLocal()

    try:
        job = Job(
            name="Scheduled Execution Test",
            status="Pending",
            script_type="python",
            is_enabled=is_enabled,
            schedule_enabled=schedule_enabled,
            schedule_paused=schedule_paused,
            schedule_type="interval",
            schedule_value="15",
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        return job.id

    finally:
        db.close()


def test_scheduled_job_uses_common_execution_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = create_scheduled_job()

    common_execution_mock = MagicMock(
        return_value=SimpleNamespace(
            status="Completed",
            error_message=None,
        )
    )
    update_next_run_mock = MagicMock()

    monkeypatch.setattr(
        scheduler_module,
        "execute_job_with_history",
        common_execution_mock,
    )
    monkeypatch.setattr(
        scheduler_module,
        "update_next_run",
        update_next_run_mock,
    )

    scheduler_module.execute_scheduled_job(job_id)

    common_execution_mock.assert_called_once()

    call_arguments = common_execution_mock.call_args

    assert call_arguments.kwargs["job"].id == job_id
    assert call_arguments.kwargs["db"] is not None

    update_next_run_mock.assert_called_once_with(job_id)


@pytest.mark.parametrize(
    (
        "is_enabled",
        "schedule_enabled",
        "schedule_paused",
    ),
    [
        (False, True, False),
        (True, False, False),
        (True, True, True),
    ],
)
def test_ineligible_scheduled_job_is_not_executed(
    monkeypatch: pytest.MonkeyPatch,
    is_enabled: bool,
    schedule_enabled: bool,
    schedule_paused: bool,
) -> None:
    job_id = create_scheduled_job(
        is_enabled=is_enabled,
        schedule_enabled=schedule_enabled,
        schedule_paused=schedule_paused,
    )

    common_execution_mock = MagicMock()
    update_next_run_mock = MagicMock()

    monkeypatch.setattr(
        scheduler_module,
        "execute_job_with_history",
        common_execution_mock,
    )
    monkeypatch.setattr(
        scheduler_module,
        "update_next_run",
        update_next_run_mock,
    )

    scheduler_module.execute_scheduled_job(job_id)

    common_execution_mock.assert_not_called()
    update_next_run_mock.assert_called_once_with(job_id)


def test_missing_scheduled_job_is_handled_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_job_id = 999

    common_execution_mock = MagicMock()
    update_next_run_mock = MagicMock()

    monkeypatch.setattr(
        scheduler_module,
        "execute_job_with_history",
        common_execution_mock,
    )
    monkeypatch.setattr(
        scheduler_module,
        "update_next_run",
        update_next_run_mock,
    )

    scheduler_module.execute_scheduled_job(missing_job_id)

    common_execution_mock.assert_not_called()
    update_next_run_mock.assert_called_once_with(
        missing_job_id
    )


def test_next_run_is_updated_when_common_service_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = create_scheduled_job()

    common_execution_mock = MagicMock(
        side_effect=RuntimeError(
            "Unexpected execution failure"
        )
    )
    update_next_run_mock = MagicMock()

    monkeypatch.setattr(
        scheduler_module,
        "execute_job_with_history",
        common_execution_mock,
    )
    monkeypatch.setattr(
        scheduler_module,
        "update_next_run",
        update_next_run_mock,
    )

    scheduler_module.execute_scheduled_job(job_id)

    common_execution_mock.assert_called_once()
    update_next_run_mock.assert_called_once_with(job_id)
    