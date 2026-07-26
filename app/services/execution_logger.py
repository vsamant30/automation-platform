from pathlib import Path

from app.db.models import Job, JobExecution


LOG_DIRECTORY = Path("app/logs")


def get_execution_log_path(execution_id: int) -> Path:
    """Return the log-file path for an execution."""
    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)

    return LOG_DIRECTORY / f"execution_{execution_id}.log"


def write_execution_log(
    job: Job,
    execution: JobExecution,
) -> Path:
    """Write an execution result to a text log file."""
    log_path = get_execution_log_path(execution.id)

    result = execution.result or "No console output was recorded."
    error = execution.error_message or "No error was recorded."

    log_content = f"""Automation Platform Execution Log
=================================

Execution ID : {execution.id}
Job ID       : {job.id}
Job Name     : {job.name}
Script Type  : {job.script_type or "-"}
Script Path  : {job.script_path or "-"}

Status       : {execution.status}
Started      : {execution.started_at or "-"}
Completed    : {execution.completed_at or "-"}
Duration     : {execution.duration or 0} seconds

Console Output
--------------

{result}

Error Details
-------------

{error}
"""

    log_path.write_text(
        log_content,
        encoding="utf-8",
    )

    return log_path