from collections.abc import Generator
from datetime import datetime, timedelta

from app.core.time import utc_now
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.services.agent_job_service as service
from app.db.models import (
    Agent,
    AgentJob,
    Base,
    Job,
    JobExecution,
)


test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture(autouse=True)
def prepare_database(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    monkeypatch.setattr(
        service,
        "SessionLocal",
        TestSessionLocal,
    )

    monkeypatch.setattr(
        service,
        "write_execution_log",
        MagicMock(),
    )

    monkeypatch.setattr(
        service,
        "send_job_execution_notification",
        MagicMock(),
    )

    yield

    Base.metadata.drop_all(bind=test_engine)


def create_agent_and_job() -> tuple[int, int]:
    db: Session = TestSessionLocal()

    try:
        agent = Agent(
            name="Remote History Test Agent",
            platform="windows",
            hostname="test-host",
            base_url="http://127.0.0.1:9000",
            status="Online",
            is_enabled=True,
        )

        job = Job(
            name="Remote History Test Job",
            category="General",
            description="Remote history integration test",
            script_type="python",
            script_path="test_remote_script.py",
            status="Pending",
            is_enabled=True,
        )

        db.add_all([agent, job])
        db.commit()
        db.refresh(agent)
        db.refresh(job)

        return agent.id, job.id

    finally:
        db.close()


def get_records(
    *,
    agent_job_id: int,
) -> tuple[AgentJob, Job, JobExecution]:
    db: Session = TestSessionLocal()

    try:
        agent_job = db.get(
            AgentJob,
            agent_job_id,
        )

        assert agent_job is not None
        assert agent_job.job_execution_id is not None

        job = db.get(
            Job,
            agent_job.job_id,
        )

        execution = db.get(
            JobExecution,
            agent_job.job_execution_id,
        )

        assert job is not None
        assert execution is not None

        db.expunge(agent_job)
        db.expunge(job)
        db.expunge(execution)

        return agent_job, job, execution

    finally:
        db.close()


def queue_and_claim() -> tuple[int, int]:
    agent_id, job_id = create_agent_and_job()

    queued = service.queue_job_for_agent(
        agent_id=agent_id,
        job_id=job_id,
    )

    claimed = service.claim_next_agent_job(
        agent_id,
    )

    assert claimed is not None
    assert claimed.id == queued.id

    return agent_id, queued.id


def test_remote_completion_updates_standard_history() -> None:
    agent_id, agent_job_id = queue_and_claim()

    service.mark_agent_job_running(
        agent_job_id=agent_job_id,
        agent_id=agent_id,
    )

    service.complete_agent_job(
        agent_job_id=agent_job_id,
        agent_id=agent_id,
        result="Remote execution completed.",
    )

    agent_job, job, execution = get_records(
        agent_job_id=agent_job_id,
    )

    assert agent_job.status == "Completed"
    assert agent_job.result == (
        "Remote execution completed."
    )
    assert agent_job.error_message is None

    assert job.status == "Completed"
    assert job.result == (
        "Remote execution completed."
    )
    assert job.error_message is None
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.duration is not None
    assert job.duration >= 0

    assert execution.status == "Completed"
    assert execution.result == (
        "Remote execution completed."
    )
    assert execution.error_message is None
    assert execution.started_at is not None
    assert execution.completed_at is not None
    assert execution.duration is not None
    assert execution.duration >= 0


def test_remote_failure_updates_standard_history() -> None:
    agent_id, agent_job_id = queue_and_claim()

    service.mark_agent_job_running(
        agent_job_id=agent_job_id,
        agent_id=agent_id,
    )

    service.fail_agent_job(
        agent_job_id=agent_job_id,
        agent_id=agent_id,
        error_message="Remote execution failed.",
        result="Partial remote output.",
    )

    agent_job, job, execution = get_records(
        agent_job_id=agent_job_id,
    )

    assert agent_job.status == "Failed"
    assert agent_job.result == "Partial remote output."
    assert agent_job.error_message == (
        "Remote execution failed."
    )

    assert job.status == "Failed"
    assert job.result == "Partial remote output."
    assert job.error_message == (
        "Remote execution failed."
    )
    assert job.completed_at is not None
    assert job.duration is not None
    assert job.duration >= 0

    assert execution.status == "Failed"
    assert execution.result == "Partial remote output."
    assert execution.error_message == (
        "Remote execution failed."
    )
    assert execution.completed_at is not None
    assert execution.duration is not None
    assert execution.duration >= 0


def test_stale_claim_updates_standard_history() -> None:
    _, agent_job_id = queue_and_claim()

    db: Session = TestSessionLocal()

    try:
        agent_job = db.get(
            AgentJob,
            agent_job_id,
        )

        assert agent_job is not None

        agent_job.claimed_at = (
        utc_now()
            - timedelta(minutes=10)
        )

        db.commit()

    finally:
        db.close()

    failed_count = (
        service.mark_stale_agent_jobs_failed(
            claimed_timeout_minutes=5,
            running_timeout_minutes=60,
        )
    )

    assert failed_count == 1

    agent_job, job, execution = get_records(
        agent_job_id=agent_job_id,
    )

    expected_error = (
        "Remote job timed out while in "
        "Claimed status."
    )

    assert agent_job.status == "Failed"
    assert agent_job.error_message == expected_error

    assert job.status == "Failed"
    assert job.error_message == expected_error
    assert job.completed_at is not None
    assert job.duration is not None
    assert job.duration >= 0

    assert execution.status == "Failed"
    assert execution.error_message == expected_error
    assert execution.completed_at is not None
    assert execution.duration is not None
    assert execution.duration >= 0


def test_wrong_agent_cannot_change_remote_job() -> None:
    agent_id, agent_job_id = queue_and_claim()

    with pytest.raises(
        ValueError,
        match="Agent job not found",
    ):
        service.mark_agent_job_running(
            agent_job_id=agent_job_id,
            agent_id=agent_id + 999,
        )

    agent_job, job, execution = get_records(
        agent_job_id=agent_job_id,
    )

    assert agent_job.status == "Claimed"
    assert job.status == "Queued"
    assert execution.status == "Queued"


def test_completion_before_running_is_rejected() -> None:
    agent_id, agent_job_id = queue_and_claim()

    with pytest.raises(
        ValueError,
        match="must be Running",
    ):
        service.complete_agent_job(
            agent_job_id=agent_job_id,
            agent_id=agent_id,
            result="Must not be saved.",
        )

    agent_job, job, execution = get_records(
        agent_job_id=agent_job_id,
    )

    assert agent_job.status == "Claimed"
    assert agent_job.result is None

    assert job.status == "Queued"
    assert job.result is None

    assert execution.status == "Queued"
    assert execution.result is None


def test_output_failures_do_not_rollback_remote_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_id, agent_job_id = queue_and_claim()

    service.mark_agent_job_running(
        agent_job_id=agent_job_id,
        agent_id=agent_id,
    )

    monkeypatch.setattr(
        service,
        "write_execution_log",
        MagicMock(
            side_effect=RuntimeError(
                "Simulated log failure"
            )
        ),
    )

    monkeypatch.setattr(
        service,
        "send_job_execution_notification",
        MagicMock(
            side_effect=RuntimeError(
                "Simulated notification failure"
            )
        ),
    )

    service.fail_agent_job(
        agent_job_id=agent_job_id,
        agent_id=agent_id,
        error_message="Remote process failed.",
        result="Partial output.",
    )

    agent_job, job, execution = get_records(
        agent_job_id=agent_job_id,
    )

    assert agent_job.status == "Failed"
    assert job.status == "Failed"
    assert execution.status == "Failed"

    assert agent_job.error_message == (
        "Remote process failed."
    )
    assert job.error_message == (
        "Remote process failed."
    )
    assert execution.error_message == (
        "Remote process failed."
    )


def test_stale_running_job_updates_all_records() -> None:
    agent_id, agent_job_id = queue_and_claim()

    service.mark_agent_job_running(
        agent_job_id=agent_job_id,
        agent_id=agent_id,
    )

    db: Session = TestSessionLocal()

    try:
        agent_job = db.get(
            AgentJob,
            agent_job_id,
        )

        assert agent_job is not None

        agent_job.started_at = (
        utc_now()
            - timedelta(minutes=90)
        )

        db.commit()

    finally:
        db.close()

    failed_count = (
        service.mark_stale_agent_jobs_failed(
            claimed_timeout_minutes=5,
            running_timeout_minutes=60,
        )
    )

    assert failed_count == 1

    agent_job, job, execution = get_records(
        agent_job_id=agent_job_id,
    )

    expected_error = (
        "Remote job timed out while in "
        "Running status."
    )

    assert agent_job.status == "Failed"
    assert agent_job.error_message == expected_error

    assert job.status == "Failed"
    assert job.error_message == expected_error
    assert job.completed_at is not None

    assert execution.status == "Failed"
    assert execution.error_message == expected_error
    assert execution.completed_at is not None
