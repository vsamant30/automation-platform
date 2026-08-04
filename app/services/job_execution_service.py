from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import (
    Job,
    JobExecution,
)
from app.services.execution_logger import write_execution_log
from app.services.job_runner import execute_job


def _get_dependent_jobs(
    db: Session,
    job: Job,
) -> list[Job]:
    """
    Return all jobs that depend on the
    supplied job.
    """

    return (
        db.query(Job)
        .filter(
            Job.dependency_job_id == job.id
        )
        .all()
    )


def _execute_dependent_job(
    job_id: int,
    visited_job_ids: set[int],
) -> JobExecution | None:
    """
    Execute one dependent job using a separate
    database session.
    """

    db = SessionLocal()

    try:
        job = (
            db.query(Job)
            .filter(Job.id == job_id)
            .first()
        )

        if job is None or not job.is_enabled:
            return None

        return execute_job_with_history(
            db=db,
            job=job,
            visited_job_ids=visited_job_ids,
        )

    finally:
        db.close()


def _get_dependency_block_reason(
    db,
    job: Job,
) -> str | None:
    if job.dependency_job_id is None:
        return None

    if job.dependency_job_id == job.id:
        return "A job cannot depend on itself."

    dependency_job = (
        db.query(Job)
        .filter(Job.id == job.dependency_job_id)
        .first()
    )

    if dependency_job is None:
        return (
            "Dependency job was not found: "
            f"{job.dependency_job_id}"
        )

    latest_dependency_execution = (
        db.query(JobExecution)
        .filter(
            JobExecution.job_id == dependency_job.id
        )
        .order_by(JobExecution.id.desc())
        .first()
    )

    if latest_dependency_execution is None:
        return (
            f"Dependency job '{dependency_job.name}' "
            "has never been executed."
        )

    if latest_dependency_execution.status != "Completed":
        return (
            f"Dependency job '{dependency_job.name}' "
            "has not completed successfully. "
            f"Latest status: "
            f"{latest_dependency_execution.status}."
        )

    condition_block_reason = (
        _get_condition_block_reason(
            job=job,
            dependency_execution=latest_dependency_execution,
        )
    )

    if condition_block_reason:
        return condition_block_reason

    return None


def _get_condition_block_reason(
    job: Job,
    dependency_execution: JobExecution,
) -> str | None:
    """
    Return a reason when the configured condition
    does not match the dependency execution result.
    """

    condition_type = (
        job.condition_type or ""
    ).strip().lower()

    condition_value = (
        job.condition_value or ""
    ).strip()

    if not condition_type:
        return None

    if not condition_value:
        return "Conditional execution requires a condition value."

    dependency_result = (
        dependency_execution.result or ""
    )

    normalized_result = dependency_result.lower()
    normalized_value = condition_value.lower()

    condition_matched = False

    if condition_type == "equals":
        condition_matched = (
            normalized_result == normalized_value
        )

    elif condition_type == "contains":
        condition_matched = (
            normalized_value in normalized_result
        )

    elif condition_type == "starts_with":
        condition_matched = (
            normalized_result.startswith(
                normalized_value
            )
        )

    elif condition_type == "ends_with":
        condition_matched = (
            normalized_result.endswith(
                normalized_value
            )
        )

    else:
        return (
            "Unsupported condition type: "
            f"{job.condition_type}"
        )

    if condition_matched:
        return None

    return (
        f"Condition '{condition_type}' did not match "
        f"value '{condition_value}'."
    )


def execute_job_with_history(
    db,
    job: Job,
    visited_job_ids: set[int] | None = None,
) -> JobExecution:
    """
    Execute a job and automatically create or update
    its execution history.

    A job with a dependency runs only when the latest
    execution of its dependency completed successfully.
    """

    execution = None

    if visited_job_ids is None:
        visited_job_ids = set()

    if job.id in visited_job_ids:
        raise RuntimeError(
            f"Circular job dependency detected at "
            f"job '{job.name}' (ID {job.id})."
        )

    current_visited_job_ids = {
        *visited_job_ids,
        job.id,
    }

    try:
        started_at = datetime.utcnow()

        dependency_block_reason = (
            _get_dependency_block_reason(
                db=db,
                job=job,
            )
        )

        if dependency_block_reason:
            job.status = "Skipped"
            job.started_at = started_at
            job.completed_at = started_at
            job.duration = 0
            job.result = None
            job.error_message = dependency_block_reason

            execution = JobExecution(
                job_id=job.id,
                job_name=job.name,
                status="Skipped",
                result=None,
                error_message=dependency_block_reason,
                started_at=started_at,
                completed_at=started_at,
                duration=0,
            )

            db.add(execution)
            db.commit()
            db.refresh(job)
            db.refresh(execution)

            write_execution_log(
                job,
                execution,
            )

            return execution

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

        write_execution_log(
            job,
            execution,
        )

        dependent_jobs = _get_dependent_jobs(
            db=db,
            job=job,
        )

        enabled_dependent_job_ids = [
            dependent_job.id
            for dependent_job in dependent_jobs
            if dependent_job.is_enabled
        ]

        if enabled_dependent_job_ids:
            max_workers = min(
                len(enabled_dependent_job_ids),
                4,
            )

            with ThreadPoolExecutor(
                max_workers=max_workers,
            ) as executor:
                futures = [
                    executor.submit(
                        _execute_dependent_job,
                        dependent_job_id,
                        current_visited_job_ids,
                    )
                    for dependent_job_id
                    in enabled_dependent_job_ids
                ]

                for future in as_completed(futures):
                    try:
                        future.result()

                    except RuntimeError:
                        continue

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

            write_execution_log(
                job,
                execution,
            )

    return execution