import logging
from datetime import datetime, timedelta

from app.core.time import utc_now

from app.services.email_service import (
    send_job_execution_notification,
)
from app.services.execution_logger import (
    write_execution_log,
)

from app.db.database import SessionLocal
from app.db.models import (
    Agent,
    AgentJob,
    Job,
    JobExecution,
)

logger = logging.getLogger(__name__)


def get_agent_jobs() -> list[AgentJob]:
    """
    Return all remote queue records,
    newest first.
    """

    db = SessionLocal()

    try:
        agent_jobs = (
            db.query(AgentJob)
            .order_by(AgentJob.queued_at.desc())
            .all()
        )

        for agent_job in agent_jobs:
            db.expunge(agent_job)

        return agent_jobs

    finally:
        db.close()


def get_agent_job(
    agent_job_id: int,
) -> AgentJob | None:
    """
    Return one remote queue record by ID.
    """

    db = SessionLocal()

    try:
        agent_job = (
            db.query(AgentJob)
            .filter(
                AgentJob.id == agent_job_id
            )
            .first()
        )

        if agent_job is not None:
            db.expunge(agent_job)

        return agent_job

    finally:
        db.close()


def queue_job_for_agent(
    *,
    agent_id: int,
    job_id: int,
    job_execution_id: int | None = None,
) -> AgentJob:
    """
    Queue one existing platform job for an
    enabled remote agent.
    """

    db = SessionLocal()

    try:
        agent = (
            db.query(Agent)
            .filter(Agent.id == agent_id)
            .first()
        )

        if agent is None:
            raise ValueError(
                f"Agent not found: {agent_id}"
            )

        if not agent.is_enabled:
            raise ValueError(
                f"Agent is disabled: {agent_id}"
            )

        job = (
            db.query(Job)
            .filter(Job.id == job_id)
            .first()
        )

        if job is None:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        if not job.is_enabled:
            raise ValueError(
                f"Job is disabled: {job_id}"
            )

        script_path = (
            job.script_path or ""
        ).strip()

        if not script_path:
            raise ValueError(
                f"Job has no script path: {job_id}"
            )

        if job_execution_id is not None:
            execution = (
                db.query(JobExecution)
                .filter(
                    JobExecution.id
                    == job_execution_id
                )
                .first()
            )

            if execution is None:
                raise ValueError(
                    "Job execution not found: "
                    f"{job_execution_id}"
                )

            if execution.job_id != job.id:
                raise ValueError(
                    "Job execution does not belong "
                    f"to job: {job_id}"
                )

            if execution.status not in {
                "Queued",
                "Pending",
            }:
                raise ValueError(
                    "Job execution must be Queued or "
                    "Pending before remote queueing."
                )

        else:
            execution = JobExecution(
                job_id=job.id,
                job_name=job.name,
                status="Queued",
                result=None,
                error_message=None,
                started_at=None,
                completed_at=None,
                duration=None,
            )

            db.add(execution)
            db.flush()

            job_execution_id = execution.id

        job.status = "Queued"
        job.result = None
        job.error_message = None
        job.started_at = None
        job.completed_at = None
        job.duration = None

        agent_job = AgentJob(
            agent_id=agent.id,
            job_id=job.id,
            job_execution_id=job_execution_id,
            job_name=job.name,
            script_type=job.script_type,
            script_path=script_path,
            status="Queued",
        queued_at=utc_now(),
        )

        db.add(agent_job)
        db.commit()
        db.refresh(agent_job)
        db.expunge(agent_job)

        return agent_job

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def claim_next_agent_job(
    agent_id: int,
) -> AgentJob | None:
    """
    Claim the oldest queued job for an agent.

    Returns None when no queued work exists.
    """

    db = SessionLocal()

    try:
        agent = (
            db.query(Agent)
            .filter(Agent.id == agent_id)
            .first()
        )

        if agent is None:
            raise ValueError(
                f"Agent not found: {agent_id}"
            )

        if not agent.is_enabled:
            raise ValueError(
                f"Agent is disabled: {agent_id}"
            )

        agent_job = (
            db.query(AgentJob)
            .filter(
                AgentJob.agent_id == agent_id,
                AgentJob.status == "Queued",
            )
            .order_by(
                AgentJob.queued_at.asc(),
                AgentJob.id.asc(),
            )
            .first()
        )

        if agent_job is None:
            return None

        agent_job.status = "Claimed"
        agent_job.claimed_at = utc_now()

        db.commit()
        db.refresh(agent_job)
        db.expunge(agent_job)

        return agent_job

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def _get_or_create_linked_execution(
    *,
    db,
    agent_job: AgentJob,
) -> tuple[Job, JobExecution]:
    """
    Return the platform job and standard execution
    linked to a remote-agent queue record.

    Legacy queue records without a linked execution
    receive one automatically.
    """
    job = (
        db.query(Job)
        .filter(Job.id == agent_job.job_id)
        .first()
    )

    if job is None:
        raise ValueError(
            f"Job not found: {agent_job.job_id}"
        )

    execution = None

    if agent_job.job_execution_id is not None:
        execution = (
            db.query(JobExecution)
            .filter(
                JobExecution.id
                == agent_job.job_execution_id
            )
            .first()
        )

        if execution is None:
            raise ValueError(
                "Linked job execution was not found: "
                f"{agent_job.job_execution_id}"
            )

        if execution.job_id != job.id:
            raise ValueError(
                "Linked job execution does not belong "
                f"to job: {job.id}"
            )

    else:
        execution = JobExecution(
            job_id=job.id,
            job_name=agent_job.job_name,
            status=agent_job.status,
            result=agent_job.result,
            error_message=agent_job.error_message,
            started_at=agent_job.started_at,
            completed_at=agent_job.completed_at,
            duration=None,
        )

        db.add(execution)
        db.flush()

        agent_job.job_execution_id = execution.id

    return job, execution


def mark_agent_job_running(
    *,
    agent_job_id: int,
    agent_id: int,
) -> AgentJob:
    """
    Mark a claimed remote job and its linked standard
    execution history as running.
    """
    db = SessionLocal()

    try:
        agent_job = (
            db.query(AgentJob)
            .filter(
                AgentJob.id == agent_job_id,
                AgentJob.agent_id == agent_id,
            )
            .first()
        )

        if agent_job is None:
            raise ValueError(
                f"Agent job not found: {agent_job_id}"
            )

        if agent_job.status != "Claimed":
            raise ValueError(
                "Agent job must be Claimed before "
                "it can be marked Running."
            )

        job, execution = (
            _get_or_create_linked_execution(
                db=db,
                agent_job=agent_job,
            )
        )

        started_at = utc_now()

        agent_job.status = "Running"
        agent_job.started_at = started_at

        job.status = "Running"
        job.started_at = started_at
        job.completed_at = None
        job.duration = None
        job.result = None
        job.error_message = None

        execution.status = "Running"
        execution.started_at = started_at
        execution.completed_at = None
        execution.duration = None
        execution.result = None
        execution.error_message = None

        db.commit()
        db.refresh(agent_job)
        db.expunge(agent_job)

        return agent_job

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def _publish_remote_execution_outputs(
    *,
    job: Job,
    execution: JobExecution,
) -> None:
    """
    Write the standard execution log and send the
    configured notification without making the
    agent callback fail if either output fails.
    """
    try:
        write_execution_log(
            job,
            execution,
        )

    except Exception:
        logger.exception(
            "Could not write execution log for "
            "remote execution %s.",
            execution.id,
        )

    try:
        send_job_execution_notification(
            job=job,
            execution=execution,
        )

    except Exception:
        logger.exception(
            "Could not send notification for "
            "remote execution %s.",
            execution.id,
        )


def complete_agent_job(
    *,
    agent_job_id: int,
    agent_id: int,
    result: str | None = None,
) -> AgentJob:
    """
    Complete a remote job and synchronize its linked
    standard execution history.
    """
    db = SessionLocal()

    try:
        agent_job = (
            db.query(AgentJob)
            .filter(
                AgentJob.id == agent_job_id,
                AgentJob.agent_id == agent_id,
            )
            .first()
        )

        if agent_job is None:
            raise ValueError(
                f"Agent job not found: {agent_job_id}"
            )

        if agent_job.status != "Running":
            raise ValueError(
                "Agent job must be Running before "
                "it can be completed."
            )

        job, execution = (
            _get_or_create_linked_execution(
                db=db,
                agent_job=agent_job,
            )
        )

        completed_at = utc_now()

        started_at = (
            execution.started_at
            or agent_job.started_at
            or agent_job.claimed_at
            or agent_job.queued_at
            or completed_at
        )

        duration = max(
            (
                completed_at - started_at
            ).total_seconds(),
            0,
        )

        agent_job.status = "Completed"
        agent_job.result = result
        agent_job.error_message = None
        agent_job.completed_at = completed_at

        job.status = "Completed"
        job.started_at = started_at
        job.completed_at = completed_at
        job.duration = duration
        job.result = result
        job.error_message = None

        execution.status = "Completed"
        execution.started_at = started_at
        execution.completed_at = completed_at
        execution.duration = duration
        execution.result = result
        execution.error_message = None

        db.commit()

        db.refresh(job)
        db.refresh(execution)
        db.refresh(agent_job)

        _publish_remote_execution_outputs(
            job=job,
            execution=execution,
        )

        db.expunge(agent_job)

        return agent_job

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def fail_agent_job(
    *,
    agent_job_id: int,
    agent_id: int,
    error_message: str,
    result: str | None = None,
) -> AgentJob:
    """
    Fail a claimed or running remote job and synchronize
    its linked standard execution history.
    """
    cleaned_error = error_message.strip()

    if not cleaned_error:
        raise ValueError(
            "Error message is required."
        )

    db = SessionLocal()

    try:
        agent_job = (
            db.query(AgentJob)
            .filter(
                AgentJob.id == agent_job_id,
                AgentJob.agent_id == agent_id,
            )
            .first()
        )

        if agent_job is None:
            raise ValueError(
                f"Agent job not found: {agent_job_id}"
            )

        if agent_job.status not in {
            "Claimed",
            "Running",
        }:
            raise ValueError(
                "Agent job must be Claimed or Running "
                "before it can fail."
            )

        job, execution = (
            _get_or_create_linked_execution(
                db=db,
                agent_job=agent_job,
            )
        )

        completed_at = utc_now()

        started_at = (
            execution.started_at
            or agent_job.started_at
            or agent_job.claimed_at
            or agent_job.queued_at
            or completed_at
        )

        duration = max(
            (
                completed_at - started_at
            ).total_seconds(),
            0,
        )

        agent_job.status = "Failed"
        agent_job.result = result
        agent_job.error_message = cleaned_error
        agent_job.completed_at = completed_at

        job.status = "Failed"
        job.started_at = started_at
        job.completed_at = completed_at
        job.duration = duration
        job.result = result
        job.error_message = cleaned_error

        execution.status = "Failed"
        execution.started_at = started_at
        execution.completed_at = completed_at
        execution.duration = duration
        execution.result = result
        execution.error_message = cleaned_error

        db.commit()

        db.refresh(job)
        db.refresh(execution)
        db.refresh(agent_job)

        _publish_remote_execution_outputs(
            job=job,
            execution=execution,
        )

        db.expunge(agent_job)

        return agent_job

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def mark_stale_agent_jobs_failed(
    *,
    claimed_timeout_minutes: int = 5,
    running_timeout_minutes: int = 60,
) -> int:
    """
    Fail stale Claimed or Running remote jobs and
    synchronize their standard execution histories.

    Claimed jobs use claimed_at.
    Running jobs use started_at.
    """
    if claimed_timeout_minutes <= 0:
        raise ValueError(
            "Claimed timeout must be greater than zero."
        )

    if running_timeout_minutes <= 0:
        raise ValueError(
            "Running timeout must be greater than zero."
        )

    current_time = utc_now()

    claimed_cutoff = (
        current_time
        - timedelta(
            minutes=claimed_timeout_minutes
        )
    )

    running_cutoff = (
        current_time
        - timedelta(
            minutes=running_timeout_minutes
        )
    )

    db = SessionLocal()

    try:
        stale_claimed_jobs = (
            db.query(AgentJob)
            .filter(
                AgentJob.status == "Claimed",
                AgentJob.claimed_at.is_not(None),
                AgentJob.claimed_at < claimed_cutoff,
            )
            .all()
        )

        stale_running_jobs = (
            db.query(AgentJob)
            .filter(
                AgentJob.status == "Running",
                AgentJob.started_at.is_not(None),
                AgentJob.started_at < running_cutoff,
            )
            .all()
        )

        stale_jobs = (
            stale_claimed_jobs
            + stale_running_jobs
        )

        completed_outputs: list[
            tuple[Job, JobExecution]
        ] = []

        for agent_job in stale_jobs:
            previous_status = agent_job.status

            error_message = (
                "Remote job timed out while in "
                f"{previous_status} status."
            )

            job, execution = (
                _get_or_create_linked_execution(
                    db=db,
                    agent_job=agent_job,
                )
            )

            started_at = (
                execution.started_at
                or agent_job.started_at
                or agent_job.claimed_at
                or agent_job.queued_at
                or current_time
            )

            duration = max(
                (
                    current_time - started_at
                ).total_seconds(),
                0,
            )

            agent_job.status = "Failed"
            agent_job.error_message = error_message
            agent_job.completed_at = current_time

            job.status = "Failed"
            job.started_at = started_at
            job.completed_at = current_time
            job.duration = duration
            job.result = agent_job.result
            job.error_message = error_message

            execution.status = "Failed"
            execution.started_at = started_at
            execution.completed_at = current_time
            execution.duration = duration
            execution.result = agent_job.result
            execution.error_message = error_message

            completed_outputs.append(
                (job, execution)
            )

        db.commit()

        for job, execution in completed_outputs:
            db.refresh(job)
            db.refresh(execution)

            _publish_remote_execution_outputs(
                job=job,
                execution=execution,
            )

        return len(stale_jobs)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
