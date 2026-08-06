from datetime import datetime

from sqlalchemy import func

from app.db.database import SessionLocal
from app.db.models import AgentJobLog


def append_agent_job_log(
    *,
    agent_job_id: int,
    message: str,
    stream: str = "stdout",
) -> AgentJobLog:
    """
    Append one log line for a remote job.
    """

    cleaned_message = message.rstrip()

    if not cleaned_message:
        raise ValueError(
            "Log message is required."
        )

    db = SessionLocal()

    try:
        last_sequence = (
            db.query(
                func.max(
                    AgentJobLog.sequence
                )
            )
            .filter(
                AgentJobLog.agent_job_id
                == agent_job_id
            )
            .scalar()
        )

        next_sequence = (
            1
            if last_sequence is None
            else last_sequence + 1
        )

        log = AgentJobLog(
            agent_job_id=agent_job_id,
            stream=stream,
            message=cleaned_message,
            sequence=next_sequence,
            created_at=datetime.utcnow(),
        )

        db.add(log)
        db.commit()
        db.refresh(log)
        db.expunge(log)

        return log

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def get_agent_job_logs(
    agent_job_id: int,
) -> list[AgentJobLog]:
    """
    Return all log lines for one
    remote job.
    """

    db = SessionLocal()

    try:
        logs = (
            db.query(AgentJobLog)
            .filter(
                AgentJobLog.agent_job_id
                == agent_job_id
            )
            .order_by(
                AgentJobLog.sequence.asc()
            )
            .all()
        )

        for log in logs:
            db.expunge(log)

        return logs

    finally:
        db.close()