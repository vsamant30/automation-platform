import importlib
import os
import shutil
import subprocess
import sys
from threading import Lock
from typing import Union

from app.db.database import SessionLocal
from app.db.models import Job


DEFAULT_TIMEOUT_SECONDS = 300

_active_processes: dict[int, subprocess.Popen] = {}
_active_processes_lock = Lock()

_cancellation_requested_ids: set[int] = set()


class JobExecutionCancelled(RuntimeError):
    """
    Raised when a running subprocess is intentionally stopped.
    """


def _register_active_process(
    execution_id: int,
    process: subprocess.Popen,
) -> None:
    """
    Register the child process for a running execution.
    """
    with _active_processes_lock:
        _active_processes[execution_id] = process


def _unregister_active_process(
    execution_id: int,
    process: subprocess.Popen,
) -> None:
    """
    Remove the process only when it is still the process
    registered for this execution.
    """
    with _active_processes_lock:
        registered_process = _active_processes.get(
            execution_id
        )

        if registered_process is process:
            _active_processes.pop(
                execution_id,
                None,
            )


def _consume_cancellation_request(
    execution_id: int,
) -> bool:
    """
    Return and clear the cancellation request for an execution.
    """
    with _active_processes_lock:
        if execution_id not in _cancellation_requested_ids:
            return False

        _cancellation_requested_ids.discard(execution_id)
        return True


def stop_active_execution(execution_id: int) -> bool:
    """
    Request termination of the child process associated
    with a running execution.

    Return True when a live process was found and a
    termination request was sent. Otherwise return False.
    """
    with _active_processes_lock:
        process = _active_processes.get(execution_id)

        if process is None:
            return False

        if process.poll() is not None:
            _active_processes.pop(
                execution_id,
                None,
            )
            return False

        process.terminate()
        _cancellation_requested_ids.add(execution_id)

        return True


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
    execution_id: int | None = None,
) -> str:
    """
    Execute a command and capture console output.

    When an execution ID is provided, register the child
    process so a running execution can be stopped.
    """
    process = subprocess.Popen(
        command,
        cwd=script_directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if execution_id is not None:
        _register_active_process(
            execution_id,
            process,
        )

    try:
        try:
            standard_output, standard_error = process.communicate(
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            process.kill()

            standard_output, standard_error = (
                process.communicate()
            )

            raise RuntimeError(
                f"Script timed out after "
                f"{DEFAULT_TIMEOUT_SECONDS} seconds."
            )

    finally:
        if execution_id is not None:
            _unregister_active_process(
                execution_id,
                process,
            )

    if (
        execution_id is not None
        and _consume_cancellation_request(execution_id)
    ):
        raise JobExecutionCancelled(
            "Execution cancelled by user."
        )

    standard_output = standard_output.strip()
    standard_error = standard_error.strip()

    if process.returncode != 0:
        error_details = (
            standard_error
            or standard_output
            or "No error output was returned."
        )

        raise RuntimeError(
            f"Script failed with exit code "
            f"{process.returncode}.\n"
            f"{error_details}"
        )

    if standard_output:
        return standard_output

    if standard_error:
        return standard_error

    return "Script completed successfully with no console output."

def _run_uploaded_python(
    script_path: str,
    execution_id: int | None = None,
) -> str:
    return _run_subprocess(
        command=[
            sys.executable,
            script_path,
        ],
        script_directory=os.path.dirname(script_path),
        execution_id=execution_id,
    )


def _run_powershell(
    script_path: str,
    execution_id: int | None = None,
) -> str:
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
        execution_id=execution_id,

    )


def _run_batch(
    script_path: str,
    execution_id: int | None = None,
) -> str:
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
        execution_id=execution_id,

    )


def execute_job(
    job_reference: Union[Job, str],
    execution_id: int | None = None,
) -> str:
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
        and not script_path.lower().endswith(".py")
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
            absolute_script_path,
            execution_id=execution_id,
        )

    if script_type == "powershell":
        return _run_powershell(
            absolute_script_path,
            execution_id=execution_id,
        )

    if script_type == "batch":
        return _run_batch(
            absolute_script_path,
            execution_id=execution_id,
        )

    raise ValueError(
        f"Unsupported script type: {script_type}"
    )