from datetime import datetime

from app.db.models import Job, JobExecution
from app.services.execution_logger import write_execution_log
from app.services.job_runner import execute_job


def execute_job_with_history(db, job: Job) -> JobExecution:
    """
    Execute a job and automatically create/update
    the execution history.
    """

    execution = None

    try:
        started_at = datetime.utcnow()

        job.status = "Running"
        job.started_at = started_at
        job.completed_at = None
        job.duration = None
        job.result = None
        job.error_message = None

        execution = JobExecution(
            job_id=job.id,
            job_name=job.name,
            status="Running",
            started_at=started_at,
        )

        db.add(execution)
        db.commit()

        db.refresh(job)
        db.refresh(execution)

        result = execute_job(job)

        completed_at = datetime.utcnow()

        duration = (
            completed_at - started_at
        ).total_seconds()

        job.status = "Completed"
        job.result = result
        job.error_message = None
        job.completed_at = completed_at
        job.duration = duration

        execution.status = "Completed"
        execution.result = result
        execution.error_message = None
        execution.completed_at = completed_at
        execution.duration = duration

        db.commit()
        db.refresh(execution)

        write_execution_log(job, execution)

    except Exception as error:

        completed_at = datetime.utcnow()

        job.status = "Failed"
        job.result = None
        job.error_message = str(error)
        job.completed_at = completed_at

        if job.started_at:
            job.duration = (
                completed_at - job.started_at
            ).total_seconds()

        if execution is not None:
            execution.status = "Failed"
            execution.result = None
            execution.error_message = str(error)
            execution.completed_at = completed_at
            execution.duration = job.duration

        db.commit()

        if execution is not None:
            db.refresh(execution)
            write_execution_log(job, execution)

    return execution