from datetime import datetime

from app.db.database import SessionLocal
from app.db.models import (
    Agent,
    AgentJob,
    Job,
    JobExecution,
)


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

        agent_job = AgentJob(
            agent_id=agent.id,
            job_id=job.id,
            job_execution_id=job_execution_id,
            job_name=job.name,
            script_type=job.script_type,
            script_path=script_path,
            status="Queued",
            queued_at=datetime.utcnow(),
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
        agent_job.claimed_at = datetime.utcnow()

        db.commit()
        db.refresh(agent_job)
        db.expunge(agent_job)

        return agent_job

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def mark_agent_job_running(
    *,
    agent_job_id: int,
    agent_id: int,
) -> AgentJob:
    """
    Mark a claimed remote job as running.
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

        agent_job.status = "Running"
        agent_job.started_at = datetime.utcnow()

        db.commit()
        db.refresh(agent_job)
        db.expunge(agent_job)

        return agent_job

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def complete_agent_job(
    *,
    agent_job_id: int,
    agent_id: int,
    result: str | None = None,
) -> AgentJob:
    """
    Mark a running remote job as completed.
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

        agent_job.status = "Completed"
        agent_job.result = result
        agent_job.error_message = None
        agent_job.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(agent_job)
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
    Mark a claimed or running remote job as failed.
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

        agent_job.status = "Failed"
        agent_job.result = result
        agent_job.error_message = cleaned_error
        agent_job.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(agent_job)
        db.expunge(agent_job)

        return agent_job

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()