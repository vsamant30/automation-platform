import os
import subprocess
import sys

from dataclasses import dataclass


DEFAULT_EXECUTION_TIMEOUT_SECONDS = 900


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
        return [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script_path,
        ]

    if cleaned_script_type == "batch":
        return [
            "cmd.exe",
            "/c",
            script_path,
        ]

    raise ValueError(
        f"Unsupported script type: {script_type}"
    )


def execute_script(
    *,
    script_type: str,
    script_path: str,
    timeout_seconds: int = (
        DEFAULT_EXECUTION_TIMEOUT_SECONDS
    ),
) -> ExecutionResult:
    """
    Execute one local script on the Windows Agent.
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

    try:
        completed_process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

    except subprocess.TimeoutExpired as error:
        output = (
            error.stdout
            if isinstance(error.stdout, str)
            else ""
        )

        error_output = (
            error.stderr
            if isinstance(error.stderr, str)
            else ""
        )

        return ExecutionResult(
            success=False,
            return_code=-1,
            output=output.strip(),
            error=(
                error_output.strip()
                or (
                    "Script execution timed out after "
                    f"{timeout_seconds} seconds."
                )
            ),
        )

    output = (
        completed_process.stdout or ""
    ).strip()

    error_output = (
        completed_process.stderr or ""
    ).strip()

    return ExecutionResult(
        success=(
            completed_process.returncode == 0
        ),
        return_code=(
            completed_process.returncode
        ),
        output=output,
        error=error_output,
    )