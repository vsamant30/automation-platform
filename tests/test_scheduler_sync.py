from collections.abc import Generator
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
    """
    Use a clean in-memory database for every scheduler test.

    The real automation_platform.db file is not modified.
    """

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(
        scheduler_module,
        "SessionLocal",
        TestSessionLocal,
    )

    yield

    Base.metadata.drop_all(bind=test_engine)


def create_test_job(
    *,
    name: str = "Scheduler Test Job",
    is_enabled: bool = True,
    schedule_enabled: bool = True,
    schedule_paused: bool = False,
    schedule_type: str = "interval",
    schedule_value: str = "15",
) -> Job:
    db: Session = TestSessionLocal()

    try:
        job = Job(
            name=name,
            status="Pending",
            is_enabled=is_enabled,
            schedule_enabled=schedule_enabled,
            schedule_paused=schedule_paused,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        job_id = job.id

    finally:
        db.close()

    db = TestSessionLocal()

    try:
        return db.query(Job).filter(Job.id == job_id).first()

    finally:
        db.close()


def test_enabled_scheduled_job_is_added(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = create_test_job(
        schedule_type="interval",
        schedule_value="15",
    )

    add_job_mock = MagicMock()
    update_next_run_mock = MagicMock()
    remove_job_mock = MagicMock()

    monkeypatch.setattr(
        scheduler_module.scheduler,
        "add_job",
        add_job_mock,
    )

    monkeypatch.setattr(
        scheduler_module,
        "update_next_run",
        update_next_run_mock,
    )

    monkeypatch.setattr(
        scheduler_module,
        "remove_scheduled_job",
        remove_job_mock,
    )

    scheduler_module.sync_job_schedule(job.id)

    add_job_mock.assert_called_once()
    update_next_run_mock.assert_called_once_with(job.id)
    remove_job_mock.assert_not_called()

    call_arguments = add_job_mock.call_args

    assert call_arguments.args[0] == scheduler_module.execute_scheduled_job
    assert call_arguments.kwargs["args"] == [job.id]
    assert call_arguments.kwargs["id"] == f"database_job_{job.id}"
    assert call_arguments.kwargs["name"] == job.name
    assert call_arguments.kwargs["replace_existing"] is True
    assert call_arguments.kwargs["max_instances"] == 1
    assert call_arguments.kwargs["coalesce"] is True


def test_paused_job_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = create_test_job(
        schedule_paused=True,
    )

    add_job_mock = MagicMock()
    remove_job_mock = MagicMock()
    update_next_run_mock = MagicMock()

    monkeypatch.setattr(
        scheduler_module.scheduler,
        "add_job",
        add_job_mock,
    )

    monkeypatch.setattr(
        scheduler_module,
        "remove_scheduled_job",
        remove_job_mock,
    )

    monkeypatch.setattr(
        scheduler_module,
        "update_next_run",
        update_next_run_mock,
    )

    scheduler_module.sync_job_schedule(job.id)

    remove_job_mock.assert_called_once_with(job.id)
    add_job_mock.assert_not_called()
    update_next_run_mock.assert_not_called()


def test_disabled_job_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = create_test_job(
        is_enabled=False,
    )

    add_job_mock = MagicMock()
    remove_job_mock = MagicMock()
    update_next_run_mock = MagicMock()

    monkeypatch.setattr(
        scheduler_module.scheduler,
        "add_job",
        add_job_mock,
    )

    monkeypatch.setattr(
        scheduler_module,
        "remove_scheduled_job",
        remove_job_mock,
    )

    monkeypatch.setattr(
        scheduler_module,
        "update_next_run",
        update_next_run_mock,
    )

    scheduler_module.sync_job_schedule(job.id)

    remove_job_mock.assert_called_once_with(job.id)
    add_job_mock.assert_not_called()
    update_next_run_mock.assert_not_called()


def test_job_without_scheduling_enabled_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = create_test_job(
        schedule_enabled=False,
    )

    add_job_mock = MagicMock()
    remove_job_mock = MagicMock()
    update_next_run_mock = MagicMock()

    monkeypatch.setattr(
        scheduler_module.scheduler,
        "add_job",
        add_job_mock,
    )

    monkeypatch.setattr(
        scheduler_module,
        "remove_scheduled_job",
        remove_job_mock,
    )

    monkeypatch.setattr(
        scheduler_module,
        "update_next_run",
        update_next_run_mock,
    )

    scheduler_module.sync_job_schedule(job.id)

    remove_job_mock.assert_called_once_with(job.id)
    add_job_mock.assert_not_called()
    update_next_run_mock.assert_not_called()


def test_manual_job_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = create_test_job(
        schedule_type="manual",
        schedule_value=None,
    )

    add_job_mock = MagicMock()
    remove_job_mock = MagicMock()
    update_next_run_mock = MagicMock()

    monkeypatch.setattr(
        scheduler_module.scheduler,
        "add_job",
        add_job_mock,
    )

    monkeypatch.setattr(
        scheduler_module,
        "remove_scheduled_job",
        remove_job_mock,
    )

    monkeypatch.setattr(
        scheduler_module,
        "update_next_run",
        update_next_run_mock,
    )

    scheduler_module.sync_job_schedule(job.id)

    remove_job_mock.assert_called_once_with(job.id)
    add_job_mock.assert_not_called()
    update_next_run_mock.assert_not_called()


def test_missing_job_is_removed_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_job_id = 99999

    add_job_mock = MagicMock()
    remove_job_mock = MagicMock()
    update_next_run_mock = MagicMock()

    monkeypatch.setattr(
        scheduler_module.scheduler,
        "add_job",
        add_job_mock,
    )

    monkeypatch.setattr(
        scheduler_module,
        "remove_scheduled_job",
        remove_job_mock,
    )

    monkeypatch.setattr(
        scheduler_module,
        "update_next_run",
        update_next_run_mock,
    )

    scheduler_module.sync_job_schedule(missing_job_id)

    remove_job_mock.assert_called_once_with(missing_job_id)
    add_job_mock.assert_not_called()
    update_next_run_mock.assert_not_called()