import importlib
import os
import shutil
import subprocess
import sys
from typing import Union

from app.db.database import SessionLocal
from app.db.models import Job


DEFAULT_TIMEOUT_SECONDS = 300


def _get_job(job_reference: Union[Job, str]) -> Job:
    """
    Accept either a Job object or a job name.

    Supporting job names keeps existing scheduler calls working.
    """

    if isinstance(job_reference, Job):
        return job_reference

    db = SessionLocal()

    try:
        job = (
            db.query(Job)
            .filter(Job.name == job_reference)
            .first()
        )

        if not job:
            raise ValueError(
                f"Job not found: {job_reference}"
            )

        # Detach the object before closing the temporary session.
        db.expunge(job)

        return job

    finally:
        db.close()


def _run_python_module(script_path: str) -> str:
    """
    Run an existing Python module:function job.

    Example:
    app.jobs.sample_job:run_sample_job
    """

    module_name, function_name = script_path.rsplit(":", 1)

    module = importlib.import_module(module_name)

    function = getattr(module, function_name, None)

    if function is None:
        raise AttributeError(
            f"Function '{function_name}' was not found "
            f"in module '{module_name}'."
        )

    result = function()

    if result is None:
        return "Python job completed successfully."

    return str(result)


def _run_subprocess(
    command: list[str],
    script_directory: str,
) -> str:
    """
    Execute a command and capture console output.
    """

    completed_process = subprocess.run(
        command,
        cwd=script_directory,
        capture_output=True,
        text=True,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        check=False,
    )

    standard_output = completed_process.stdout.strip()
    standard_error = completed_process.stderr.strip()

    if completed_process.returncode != 0:
        error_details = (
            standard_error
            or standard_output
            or "No error output was returned."
        )

        raise RuntimeError(
            f"Script failed with exit code "
            f"{completed_process.returncode}.\n"
            f"{error_details}"
        )

    if standard_output:
        return standard_output

    if standard_error:
        return standard_error

    return "Script completed successfully with no console output."


def _run_uploaded_python(script_path: str) -> str:
    return _run_subprocess(
        command=[
            sys.executable,
            script_path,
        ],
        script_directory=os.path.dirname(script_path),
    )


def _run_powershell(script_path: str) -> str:
    powershell_executable = (
        shutil.which("pwsh")
        or shutil.which("powershell")
        or shutil.which("powershell.exe")
    )

    if not powershell_executable:
        raise RuntimeError(
            "PowerShell was not found on this computer."
        )

    return _run_subprocess(
        command=[
            powershell_executable,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script_path,
        ],
        script_directory=os.path.dirname(script_path),
    )


def _run_batch(script_path: str) -> str:
    command_processor = os.environ.get(
        "COMSPEC",
        "cmd.exe",
    )

    return _run_subprocess(
        command=[
            command_processor,
            "/d",
            "/c",
            script_path,
        ],
        script_directory=os.path.dirname(script_path),
    )


def execute_job(job_reference: Union[Job, str]) -> str:
    """
    Execute a registered automation job.

    Supported formats:

    Existing Python module:
        app.jobs.sample_job:run_sample_job

    Uploaded Python file:
        C:\\...\\uploads\\script.py

    PowerShell:
        C:\\...\\uploads\\script.ps1

    Batch:
        C:\\...\\uploads\\script.bat
    """

    job = _get_job(job_reference)

    script_type = (job.script_type or "").strip().lower()
    script_path = (job.script_path or "").strip()

    if not script_path:
        raise ValueError(
            f"No script path is configured for job '{job.name}'."
        )

    # Existing module:function Python jobs
    if (
        script_type == "python"
        and ":" in script_path
        and not os.path.isfile(script_path)
    ):
        return _run_python_module(script_path)

    absolute_script_path = os.path.abspath(script_path)

    if not os.path.isfile(absolute_script_path):
        raise FileNotFoundError(
            f"Script file was not found: "
            f"{absolute_script_path}"
        )

    if script_type == "python":
        return _run_uploaded_python(
            absolute_script_path
        )

    if script_type == "powershell":
        return _run_powershell(
            absolute_script_path
        )

    if script_type == "batch":
        return _run_batch(
            absolute_script_path
        )

    raise ValueError(
        f"Unsupported script type: {script_type}"
    )