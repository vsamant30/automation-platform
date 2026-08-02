from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import app.scheduler.scheduler as scheduler_module


class FakeQuery:
    """Minimal fake SQLAlchemy query used by pause/resume tests."""

    def __init__(self, job):
        self.job = job

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.job


class FakeDatabase:
    """Minimal fake database session used by pause/resume tests."""

    def __init__(self, job):
        self.job = job
        self.commit = Mock()
        self.rollback = Mock()
        self.close = Mock()

    def query(self, model):
        return FakeQuery(self.job)


def create_job(
    *,
    job_id=1,
    schedule_enabled=True,
    schedule_paused=False,
    schedule_type="daily",
):
    """Create a simple job object for testing."""

    return SimpleNamespace(
        id=job_id,
        schedule_enabled=schedule_enabled,
        schedule_paused=schedule_paused,
        schedule_type=schedule_type,
    )


def test_pause_scheduled_job_success(monkeypatch):
    """Pausing should update the database and remove the APScheduler job."""

    job = create_job(
        job_id=10,
        schedule_enabled=True,
        schedule_paused=False,
        schedule_type="daily",
    )

    fake_db = FakeDatabase(job)
    remove_mock = Mock()

    monkeypatch.setattr(
        scheduler_module,
        "SessionLocal",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        scheduler_module,
        "remove_scheduled_job",
        remove_mock,
    )

    scheduler_module.pause_scheduled_job(job.id)

    assert job.schedule_paused is True
    fake_db.commit.assert_called_once()
    fake_db.rollback.assert_not_called()
    fake_db.close.assert_called_once()
    remove_mock.assert_called_once_with(job.id)


def test_pause_scheduled_job_not_found(monkeypatch):
    """Pausing a missing job should raise ValueError."""

    fake_db = FakeDatabase(None)
    remove_mock = Mock()

    monkeypatch.setattr(
        scheduler_module,
        "SessionLocal",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        scheduler_module,
        "remove_scheduled_job",
        remove_mock,
    )

    with pytest.raises(
        ValueError,
        match="Job not found: 999",
    ):
        scheduler_module.pause_scheduled_job(999)

    fake_db.commit.assert_not_called()
    fake_db.rollback.assert_called_once()
    fake_db.close.assert_called_once()
    remove_mock.assert_not_called()


def test_pause_job_without_enabled_schedule(monkeypatch):
    """A job without scheduling enabled cannot be paused."""

    job = create_job(
        job_id=20,
        schedule_enabled=False,
        schedule_paused=False,
        schedule_type="daily",
    )

    fake_db = FakeDatabase(job)
    remove_mock = Mock()

    monkeypatch.setattr(
        scheduler_module,
        "SessionLocal",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        scheduler_module,
        "remove_scheduled_job",
        remove_mock,
    )

    with pytest.raises(
        ValueError,
        match="This job does not have scheduling enabled.",
    ):
        scheduler_module.pause_scheduled_job(job.id)

    assert job.schedule_paused is False
    fake_db.commit.assert_not_called()
    fake_db.rollback.assert_called_once()
    fake_db.close.assert_called_once()
    remove_mock.assert_not_called()


def test_resume_scheduled_job_success(monkeypatch):
    """Resuming should clear paused status and synchronize the schedule."""

    job = create_job(
        job_id=30,
        schedule_enabled=True,
        schedule_paused=True,
        schedule_type="daily",
    )

    fake_db = FakeDatabase(job)
    sync_mock = Mock()

    monkeypatch.setattr(
        scheduler_module,
        "SessionLocal",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        scheduler_module,
        "sync_job_schedule",
        sync_mock,
    )

    scheduler_module.resume_scheduled_job(job.id)

    assert job.schedule_paused is False
    fake_db.commit.assert_called_once()
    fake_db.rollback.assert_not_called()
    fake_db.close.assert_called_once()
    sync_mock.assert_called_once_with(job.id)


def test_resume_scheduled_job_not_found(monkeypatch):
    """Resuming a missing job should raise ValueError."""

    fake_db = FakeDatabase(None)
    sync_mock = Mock()

    monkeypatch.setattr(
        scheduler_module,
        "SessionLocal",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        scheduler_module,
        "sync_job_schedule",
        sync_mock,
    )

    with pytest.raises(
        ValueError,
        match="Job not found: 999",
    ):
        scheduler_module.resume_scheduled_job(999)

    fake_db.commit.assert_not_called()
    fake_db.rollback.assert_called_once()
    fake_db.close.assert_called_once()
    sync_mock.assert_not_called()


def test_resume_job_without_enabled_schedule(monkeypatch):
    """A job without scheduling enabled cannot be resumed."""

    job = create_job(
        job_id=40,
        schedule_enabled=False,
        schedule_paused=True,
        schedule_type="daily",
    )

    fake_db = FakeDatabase(job)
    sync_mock = Mock()

    monkeypatch.setattr(
        scheduler_module,
        "SessionLocal",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        scheduler_module,
        "sync_job_schedule",
        sync_mock,
    )

    with pytest.raises(
        ValueError,
        match="This job does not have scheduling enabled.",
    ):
        scheduler_module.resume_scheduled_job(job.id)

    assert job.schedule_paused is True
    fake_db.commit.assert_not_called()
    fake_db.rollback.assert_called_once()
    fake_db.close.assert_called_once()
    sync_mock.assert_not_called()


def test_resume_manual_job(monkeypatch):
    """A manual job cannot be resumed as a scheduled job."""

    job = create_job(
        job_id=50,
        schedule_enabled=True,
        schedule_paused=True,
        schedule_type="manual",
    )

    fake_db = FakeDatabase(job)
    sync_mock = Mock()

    monkeypatch.setattr(
        scheduler_module,
        "SessionLocal",
        lambda: fake_db,
    )
    monkeypatch.setattr(
        scheduler_module,
        "sync_job_schedule",
        sync_mock,
    )

    with pytest.raises(
        ValueError,
        match="Manual jobs cannot be resumed as scheduled jobs.",
    ):
        scheduler_module.resume_scheduled_job(job.id)

    assert job.schedule_paused is True
    fake_db.commit.assert_not_called()
    fake_db.rollback.assert_called_once()
    fake_db.close.assert_called_once()
    sync_mock.assert_not_called()