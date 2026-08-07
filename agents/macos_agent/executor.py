import os
import queue
import shutil
import subprocess
import sys
import threading
import time

from collections.abc import Callable
from dataclasses import dataclass


DEFAULT_EXECUTION_TIMEOUT_SECONDS = 900

OutputCallback = Callable[
    [str, str],
    None,
]


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    return_code: int
    output: str
    error: str


def _build_command(
    script_type: str,
    script_path: str,
) -> list[str]:
    cleaned_script_type = (
        script_type.strip().lower()
    )

    if cleaned_script_type == "python":
        return [
            sys.executable,
            script_path,
        ]

    if cleaned_script_type == "powershell":
        powershell_executable = (
            shutil.which("pwsh")
            or shutil.which("powershell")
        )

        if not powershell_executable:
            raise RuntimeError(
                "PowerShell was not found on this macOS host."
            )

        return [
            powershell_executable,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            script_path,
        ]

    if cleaned_script_type == "batch":
        raise ValueError(
            "Batch scripts are not supported "
            "by the macOS Agent."
        )

    raise ValueError(
        f"Unsupported script type: {script_type}"
    )


def _read_process_stream(
    *,
    stream_name: str,
    process_stream,
    output_queue: queue.Queue[
        tuple[str, str]
    ],
) -> None:
    """
    Read one subprocess stream and place each
    line into the shared output queue.
    """

    try:
        for line in iter(
            process_stream.readline,
            "",
        ):
            cleaned_line = line.rstrip(
                "\r\n"
            )

            if cleaned_line:
                output_queue.put(
                    (
                        stream_name,
                        cleaned_line,
                    )
                )

    finally:
        process_stream.close()


def _emit_output(
    *,
    stream_name: str,
    message: str,
    stdout_lines: list[str],
    stderr_lines: list[str],
    on_output: OutputCallback | None,
) -> None:
    """
    Save one output line and optionally send it
    to the caller-provided callback.
    """

    if stream_name == "stderr":
        stderr_lines.append(message)

    else:
        stdout_lines.append(message)

    if on_output is None:
        return

    try:
        on_output(
            stream_name,
            message,
        )

    except Exception:
        # Log delivery must not interrupt
        # execution of the actual automation.
        return


def execute_script(
    *,
    script_type: str,
    script_path: str,
    timeout_seconds: int = (
        DEFAULT_EXECUTION_TIMEOUT_SECONDS
    ),
    on_output: OutputCallback | None = None,
) -> ExecutionResult:
    """
    Execute one local script on the macOS Agent.

    When on_output is provided, each stdout or
    stderr line is sent to the callback while
    the process is running.
    """

    cleaned_script_path = (
        script_path.strip()
    )

    if not cleaned_script_path:
        raise ValueError(
            "Script path is required."
        )

    absolute_script_path = os.path.abspath(
        cleaned_script_path
    )

    if not os.path.isfile(
        absolute_script_path
    ):
        raise FileNotFoundError(
            "Script file not found: "
            f"{absolute_script_path}"
        )

    if timeout_seconds <= 0:
        raise ValueError(
            "Execution timeout must be greater than zero."
        )

    command = _build_command(
        script_type=script_type,
        script_path=absolute_script_path,
    )

    output_queue: queue.Queue[
        tuple[str, str]
    ] = queue.Queue()

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    if (
        process.stdout is None
        or process.stderr is None
    ):
        process.kill()
        process.wait()

        raise RuntimeError(
            "Unable to capture script output."
        )

    stdout_reader = threading.Thread(
        target=_read_process_stream,
        kwargs={
            "stream_name": "stdout",
            "process_stream": process.stdout,
            "output_queue": output_queue,
        },
        daemon=True,
    )

    stderr_reader = threading.Thread(
        target=_read_process_stream,
        kwargs={
            "stream_name": "stderr",
            "process_stream": process.stderr,
            "output_queue": output_queue,
        },
        daemon=True,
    )

    stdout_reader.start()
    stderr_reader.start()

    started_at = time.monotonic()
    timed_out = False

    while True:
        try:
            stream_name, message = (
                output_queue.get(
                    timeout=0.1
                )
            )

            _emit_output(
                stream_name=stream_name,
                message=message,
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
                on_output=on_output,
            )

        except queue.Empty:
            pass

        elapsed_seconds = (
            time.monotonic()
            - started_at
        )

        if (
            process.poll() is None
            and elapsed_seconds
            >= timeout_seconds
        ):
            timed_out = True
            process.kill()
            break

        if (
            process.poll() is not None
            and output_queue.empty()
            and not stdout_reader.is_alive()
            and not stderr_reader.is_alive()
        ):
            break

    process.wait()

    stdout_reader.join(
        timeout=2
    )
    stderr_reader.join(
        timeout=2
    )

    while True:
        try:
            stream_name, message = (
                output_queue.get_nowait()
            )

        except queue.Empty:
            break

        _emit_output(
            stream_name=stream_name,
            message=message,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
            on_output=on_output,
        )

    output = "\n".join(
        stdout_lines
    ).strip()

    error_output = "\n".join(
        stderr_lines
    ).strip()

    if timed_out:
        timeout_message = (
            "Script execution timed out after "
            f"{timeout_seconds} seconds."
        )

        if not error_output:
            error_output = timeout_message

        return ExecutionResult(
            success=False,
            return_code=-1,
            output=output,
            error=error_output,
        )

    return ExecutionResult(
        success=(
            process.returncode == 0
        ),
        return_code=(
            process.returncode
            if process.returncode is not None
            else -1
        ),
        output=output,
        error=error_output,
    )