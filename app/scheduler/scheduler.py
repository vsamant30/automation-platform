import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.db.database import SessionLocal
from app.db.models import Job, JobExecution
from app.services.job_runner import execute_job

from app.services.execution_logger import write_execution_log

from app.services.agent_job_service import (
    mark_stale_agent_jobs_failed,
)

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(
    timezone="Asia/Kolkata",
)


def scheduler_job_id(job_id: int) -> str:
    """Return a unique APScheduler ID for a database job."""
    return f"database_job_{job_id}"


def update_next_run(job_id: int) -> None:
    """Save the APScheduler next-run time into SQLite."""
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            return

        scheduled_job = scheduler.get_job(
            scheduler_job_id(job_id)
        )

        if scheduled_job and scheduled_job.next_run_time:
            next_run = scheduled_job.next_run_time

            # Store UTC without timezone information,
            # matching the current database timestamps.
            job.next_run = (
                next_run
                .astimezone(timezone.utc)
                .replace(tzinfo=None)
            )
        else:
            job.next_run = None

        db.commit()

    except Exception:
        db.rollback()
        logger.exception(
            "Failed to update next run for job %s",
            job_id,
        )

    finally:
        db.close()


def execute_scheduled_job(job_id: int) -> None:
    """Execute a database job and save its execution history."""
    db = SessionLocal()
    execution = None

    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            logger.error(
                "Scheduled job %s was not found.",
                job_id,
            )
            return

        if not job.schedule_enabled:
            logger.info(
                "Job %s is no longer enabled.",
                job_id,
            )
            return
        
        if job.schedule_paused:
            logger.info(
                "Job %s schedule is paused.",
                job_id,
            )
            return
        
        if not job.is_enabled:
            logger.info(
                "Job %s is disabled.",
                job_id,
            )
            return

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

        logger.info(
            "Automatically executing job: %s",
            job.name,
        )

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

        logger.info(
            "Scheduled job completed successfully: %s",
            job.name,
        )

    except Exception as error:
        db.rollback()

        completed_at = datetime.utcnow()

        try:
            job = db.query(Job).filter(
                Job.id == job_id
            ).first()

            if job:
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

                if job:
                    execution.duration = job.duration

            db.commit()

            if execution is not None and job is not None:
                db.refresh(execution)
                write_execution_log(job, execution)

        except Exception:
            db.rollback()
            logger.exception(
                "Could not save failure details for job %s",
                job_id,
            )

        logger.exception(
            "Scheduled job failed: %s",
            job_id,
        )

    finally:
        db.close()
        update_next_run(job_id)


def build_trigger(job: Job):
    """Build an APScheduler trigger from database values."""
    schedule_type = job.schedule_type
    schedule_value = job.schedule_value

    if schedule_type == "interval":
        minutes = int(schedule_value)

        return IntervalTrigger(
            minutes=minutes,
            timezone="Asia/Kolkata",
        )

    if schedule_type == "hourly":
        _, minute = schedule_value.split(":")

        return CronTrigger(
            minute=int(minute),
            timezone="Asia/Kolkata",
        )

    if schedule_type == "daily":
        hour, minute = schedule_value.split(":")

        return CronTrigger(
            hour=int(hour),
            minute=int(minute),
            timezone="Asia/Kolkata",
        )

    if schedule_type == "weekly":
        day, execution_time = schedule_value.split("|")
        hour, minute = execution_time.split(":")

        return CronTrigger(
            day_of_week=day,
            hour=int(hour),
            minute=int(minute),
            timezone="Asia/Kolkata",
        )

    if schedule_type == "cron":
        return CronTrigger.from_crontab(
            schedule_value,
            timezone="Asia/Kolkata",
        )

    raise ValueError(
        f"Unsupported schedule type: {schedule_type}"
    )


def remove_scheduled_job(job_id: int) -> None:
    """Remove a job from APScheduler."""
    apscheduler_id = scheduler_job_id(job_id)

    scheduled_job = scheduler.get_job(apscheduler_id)

    if scheduled_job:
        scheduler.remove_job(apscheduler_id)

        logger.info(
            "Removed scheduled job: %s",
            apscheduler_id,
        )

    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if job:
            job.next_run = None
            db.commit()

    finally:
        db.close()


def pause_scheduled_job(job_id: int) -> None:
    """Pause a scheduled job without deleting its schedule configuration."""
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        if not job.schedule_enabled:
            raise ValueError(
                "This job does not have scheduling enabled."
            )

        job.schedule_paused = True
        

        db.commit()

        remove_scheduled_job(job_id)

        logger.info(
            "Paused scheduled job: %s",
            job_id,
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def resume_scheduled_job(job_id: int) -> None:
    """Resume a previously paused scheduled job."""
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            raise ValueError(
                f"Job not found: {job_id}"
            )

        if not job.schedule_enabled:
            raise ValueError(
                "This job does not have scheduling enabled."
            )

        if job.schedule_type == "manual":
            raise ValueError(
                "Manual jobs cannot be resumed as scheduled jobs."
            )

        job.schedule_paused = False

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    sync_job_schedule(job_id)

    logger.info(
        "Resumed scheduled job: %s",
        job_id,
    )


def sync_job_schedule(job_id: int) -> None:
    """Create, replace, or remove one database job schedule."""
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            remove_scheduled_job(job_id)
            return

        if (
            not job.is_enabled
            or not job.schedule_enabled
            or job.schedule_paused
            or job.schedule_type == "manual"
        ):
            remove_scheduled_job(job_id)
            return
            


        trigger = build_trigger(job)

        scheduler.add_job(
            execute_scheduled_job,
            trigger=trigger,
            args=[job.id],
            id=scheduler_job_id(job.id),
            name=job.name,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        logger.info(
            "Scheduled database job: %s",
            job.name,
        )

    finally:
        db.close()

    update_next_run(job_id)


def load_enabled_jobs() -> None:
    """Load all enabled SQLite schedules on application startup."""
    db = SessionLocal()

    try:
        enabled_job_ids = [
            job.id
            for job in (
                db.query(Job)
                .filter(
                    Job.schedule_enabled.is_(True),
                    Job.schedule_paused.is_(False),
                )
                
                .all()
            )
        ]

    finally:
        db.close()

    for job_id in enabled_job_ids:
        try:
            sync_job_schedule(job_id)

        except Exception:
            logger.exception(
                "Could not load schedule for job %s",
                job_id,
            )


def recover_stale_remote_jobs() -> None:
    """
    Recover remote jobs that have been
    stuck for too long.
    """

    try:
        recovered = mark_stale_agent_jobs_failed()

        if recovered:
            logger.warning(
                "Recovered %s stale remote job(s).",
                recovered,
            )

    except Exception:
        logger.exception(
            "Failed to recover stale remote jobs."
        )


def start_scheduler() -> None:
    """Start APScheduler and restore saved schedules."""

    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started successfully.")

    load_enabled_jobs()

    scheduler.add_job(
        recover_stale_remote_jobs,
        trigger=IntervalTrigger(minutes=5),
        id="recover_stale_remote_jobs",
        replace_existing=True,
    )

    logger.info(
        "Stale remote job recovery scheduled."
    )